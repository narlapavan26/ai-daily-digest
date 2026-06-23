"""
HackerNews subgraph: MCP POST /fetch/hackernews → normalize → fast-fail → LLM enrich → SubgraphOutput.

Budget: max 5 HN stories per run.
Stale threshold: 3 days (HN moves fast; >3 days = stale).

IMPORTANT DESIGN NOTE (from actual data analysis):
  story_text is EMPTY for most HN items. The LLM only has:
    - title (primary signal)
    - points (community upvote signal)
    - num_comments (community engagement signal)
    - community_signal = points * log(1 + num_comments)

  content_for_llm = title + points + num_comments + any top_discussion text
  Fast-fail: drop items with points < 10 (too low-signal)
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from digest_runner.schemas.digest_schemas import (
    NormalizedItem,
    SourceName,
    FastFailBatch,
    FastFailResult,
    FastFailVerdict,
)
from digest_runner.config.settings import settings
from digest_runner.utils.mcp_client import post_fetch
from .base import BaseSubgraph, parse_utc_dt, is_junk_release

logger = logging.getLogger(__name__)

DEFAULT_CATEGORY  = "AI OR LLM OR machine learning OR agent"


class HackerNewsSubgraph(BaseSubgraph):
    """
    Fetches AI/ML HN stories and picks the top 5 most community-validated items.

    Key signals used:
      - points: raw upvotes (higher = more validated)
      - num_comments: engagement depth
      - community_signal: points * log(1 + num_comments)
    """

    source     = SourceName.HACKERNEWS

    @property
    def budget(self) -> int:      # type: ignore[override]
        return settings.hackernews_budget

    @property
    def stale_days(self) -> float:  # type: ignore[override]
        return settings.hackernews_stale_days

    def __init__(
        self,
        category:    str          = DEFAULT_CATEGORY,
        max_results: Optional[int] = None,
        min_score:   Optional[int] = None,
        days_back:   Optional[int] = None,
    ) -> None:
        self.category    = category
        self.max_results = max_results if max_results is not None else settings.hackernews_max_results
        self.min_score   = min_score   if min_score   is not None else settings.hackernews_min_score
        self.days_back   = days_back   if days_back   is not None else settings.hackernews_days_back

    def fetch_from_mcp(self) -> Dict[str, Any]:
        logger.info(
            "HackerNews subgraph: fetching via MCP (category=%r, min_score=%d)",
            self.category, self.min_score,
        )
        return post_fetch("/fetch/hackernews", {
            "category":    self.category,
            "max_results": self.max_results,
            "min_score":   self.min_score,
            "days_back":   self.days_back,
        })

    def normalize(self, raw_items: List[Dict[str, Any]]) -> List[NormalizedItem]:
        """
        Map MCP DigestItem (hackernews) → NormalizedItem.

        Since story_text is usually empty, content_for_llm is assembled from
        whatever signals are available: title + points + comments + top_discussion.
        """
        result: List[NormalizedItem] = []
        for row in raw_items:
            try:
                published_at = parse_utc_dt(row["published_at"])
                import datetime as _dt
                days_old = max(
                    0.0,
                    (_dt.datetime.now(_dt.timezone.utc) - published_at).total_seconds() / 86400.0,
                )
                md      = row.get("metadata") or {}
                content = str(row.get("content") or "").strip()
                title   = str(row.get("title") or "").strip()
                points  = int(md.get("points", 0))
                comments = int(md.get("num_comments", 0))

                # community_signal: weighted score used in fast-fail + LLM context
                community_signal = points * math.log(1 + comments) if points > 0 else 0.0

                # Build content_for_llm: title is primary, story content is bonus
                parts = [f"Title: {title}"]
                parts.append(f"Points: {points} | Comments: {comments} | Community signal: {community_signal:.1f}")
                if content and content != "(No story text provided by HN)":
                    parts.append(f"\nStory: {content[:800]}")

                content_for_llm = "\n".join(parts)

                result.append(NormalizedItem(
                    id=str(row["id"]),
                    source=SourceName.HACKERNEWS,
                    title=title or "Untitled HN Story",
                    url=row["url"],
                    published_at=published_at,
                    content_for_llm=content_for_llm[:2400],
                    quality_signals={
                        "points":           points,
                        "num_comments":     comments,
                        "community_signal": round(community_signal, 2),
                        "author":           md.get("author", ""),
                        "category":         md.get("category", ""),
                    },
                    days_old=days_old,
                ))
            except Exception as exc:
                logger.warning("HN normalize error for %s: %s", row.get("id", "?"), exc)
        return result

    def fast_fail(self, normalized: List[NormalizedItem]) -> FastFailBatch:
        """
        HN-specific fast-fail:
          - DROP_LOWSIG if points < MIN_POINTS_FAST_FAIL (too little community validation)
          - DROP_STALE  if days_old > stale_days
          - DROP_EMPTY  if content_for_llm < 20 chars
        """
        passed:  List[NormalizedItem]  = []
        dropped: List[FastFailResult]  = []

        for it in normalized:
            # Global junk filter — applied before any source-specific rules
            is_junk, junk_reason = is_junk_release(it)
            if is_junk:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_LOWSIG,
                    reason=f"global_junk_filter: {junk_reason}",
                ))
                continue

            points = int(it.quality_signals.get("points", 0))
            min_pts = settings.hackernews_min_points_fast_fail

            if points < min_pts:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_LOWSIG,
                    reason=f"points={points} < {min_pts}",
                    score=0.0,
                ))
            elif it.days_old > self.stale_days:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_STALE,
                    reason=f"days_old={it.days_old:.1f} > {self.stale_days}",
                    score=0.0,
                ))
            elif len(it.content_for_llm) < 20:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_EMPTY,
                    reason="content_for_llm < 20 chars",
                    score=0.0,
                ))
            else:
                passed.append(it)

        # Sort passed by community_signal descending before sending to LLM
        passed.sort(
            key=lambda it: float(it.quality_signals.get("community_signal", 0)),
            reverse=True,
        )

        n = len(normalized)
        logger.info(
            "HN fast-fail: %d passed, %d dropped (%.0f%% pass rate)",
            len(passed), len(dropped), (len(passed) / n * 100) if n else 0,
        )

        # ── Debug: dump fast-fail results to state/ ──────────────────────────
        from .base import _dump_state
        _dump_state("hackernews_0_fastfail_passed.json", [
            {"id": it.id, "title": it.title, "url": str(it.url),
             "days_old": it.days_old, "content_len": len(it.content_for_llm or ""),
             "quality_signals": it.quality_signals}
            for it in passed
        ])
        _dump_state("hackernews_0_fastfail_dropped.json", [
            {"item_id": d.item_id, "verdict": d.verdict.value if hasattr(d.verdict, 'value') else str(d.verdict),
             "reason": d.reason}
            for d in dropped
        ])

        return FastFailBatch(
            source=SourceName.HACKERNEWS,
            passed=passed,
            dropped=dropped,
            pass_rate=(len(passed) / n) if n else 0.0,
        )
