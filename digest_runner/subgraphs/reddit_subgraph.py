"""
digest_runner/subgraphs/reddit_subgraph.py
==========================================
Reddit subgraph: MCP POST /fetch/reddit → normalize → fast-fail → LLM enrich.

Budget: max 5 posts (community discussion is high-signal but verbose).
Stale threshold: 3 days (Reddit moves very fast).

Fast-fail extras:
  - Drop if score < 10 (too low community validation)
  - Drop if days_old > stale_days

content_for_llm strategy:
  - selftext (post body) if present, cleaned
  - OR title + top 3 comment snippets
  - quality_signals carry: subreddit, score, num_comments
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List,Optional

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

DEFAULT_SUBREDDITS = [
    "MachineLearning", "LocalLLaMA", "artificial", "mlops",
    "LanguageModelEvaluation", "ArtificialIntelligence",
    "learnmachinelearning", "deeplearning",
]


class RedditSubgraph(BaseSubgraph):
    """
    Fetches posts from AI/ML subreddits, scores by community engagement.

    Key signals:
      - score: upvotes (community validation)
      - num_comments: discussion depth
      - subreddit: source community
    """

    source     = SourceName.REDDIT

    @property
    def budget(self) -> int:      # type: ignore[override]
        return settings.reddit_budget

    @property
    def stale_days(self) -> float:  # type: ignore[override]
        return settings.reddit_stale_days

    def __init__(
        self,
        subreddits:        List[str] | None = None,
        max_posts_per_sub: Optional[int]    = None,
        days_back:         Optional[int]    = None,
        min_score:         Optional[int]    = None,
        sort:              str              = "top",
    ) -> None:
        self.subreddits        = subreddits or settings.reddit_subreddits
        self.max_posts_per_sub = max_posts_per_sub if max_posts_per_sub is not None else settings.reddit_max_posts_per_sub
        self.days_back         = days_back          if days_back         is not None else settings.reddit_days_back
        self.min_score         = min_score          if min_score         is not None else settings.reddit_min_score
        self.sort              = sort

    def fetch_from_mcp(self) -> Dict[str, Any]:
        logger.info(
            "Reddit subgraph: fetching via MCP (subreddits=%s, sort=%s, min_score=%d)",
            self.subreddits[:3], self.sort, self.min_score,
        )
        return post_fetch("/fetch/reddit", {
            "subreddits":        self.subreddits,
            "max_posts_per_sub": self.max_posts_per_sub,
            "days_back":         self.days_back,
            "min_score":         self.min_score,
            "sort":              self.sort,
        })

    def normalize(self, raw_items: List[Dict[str, Any]]) -> List[NormalizedItem]:
        """Map MCP DigestItem (reddit) → NormalizedItem."""
        result: List[NormalizedItem] = []
        for row in raw_items:
            try:
                published_at = parse_utc_dt(row["published_at"])
                import datetime as _dt
                days_old = max(
                    0.0,
                    (_dt.datetime.now(_dt.timezone.utc) - published_at).total_seconds() / 86400.0,
                )
                md       = row.get("metadata") or {}
                content  = str(row.get("content") or "").strip()
                title    = str(row.get("title") or "").strip()
                score    = int(md.get("score", 0))
                comments = int(md.get("num_comments", 0))
                sub      = str(md.get("subreddit", "unknown"))

                # Assemble content_for_llm
                parts = [f"r/{sub} | Score: {score} | Comments: {comments}", f"Title: {title}"]
                if content and content not in ("(No story text provided by HN)", ""):
                    parts.append(f"\nPost: {content[:1200]}")

                content_for_llm = "\n".join(parts)

                result.append(NormalizedItem(
                    id=str(row["id"]),
                    source=SourceName.REDDIT,
                    title=title or "Untitled Reddit Post",
                    url=row["url"],
                    published_at=published_at,
                    content_for_llm=content_for_llm[:2400],
                    quality_signals={
                        "score":       score,
                        "num_comments": comments,
                        "subreddit":   sub,
                        "author":      md.get("author", ""),
                        "flair":       md.get("flair", ""),
                    },
                    days_old=days_old,
                ))
            except Exception as exc:
                logger.warning("Reddit normalize error for %s: %s", row.get("id", "?"), exc)
        return result

    def fast_fail(self, normalized: List[NormalizedItem]) -> FastFailBatch:
        """
        Reddit-specific fast-fail:
          - DROP_LOWSIG if score < MIN_SCORE_FAST_FAIL
          - DROP_STALE  if days_old > stale_days
          - DROP_EMPTY  if content_for_llm < 20 chars
        Sort passed items by score descending for LLM context.
        """
        passed:  List[NormalizedItem] = []
        dropped: List[FastFailResult] = []

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

            score   = int(it.quality_signals.get("score", 0))
            min_sc  = settings.reddit_min_score

            if score < min_sc:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_LOWSIG,
                    reason=f"score={score} < {min_sc}",
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
            elif int(it.quality_signals.get("num_comments", 0)) < settings.reddit_min_comments:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_LOWSIG,
                    reason=f"num_comments < {settings.reddit_min_comments}",
                    score=0.0,
                ))
            else:
                passed.append(it)

        # Sort by score descending so LLM sees highest-quality first
        passed.sort(key=lambda it: int(it.quality_signals.get("score", 0)), reverse=True)

        n = len(normalized)
        logger.info(
            "Reddit fast-fail: %d passed, %d dropped (%s%% pass rate)",
            len(passed), len(dropped), f"{len(passed)/n*100:.0f}" if n else "0",
        )

        # ── Debug: dump fast-fail results to state/ ──────────────────────────
        from .base import _dump_state
        _dump_state("reddit_0_fastfail_passed.json", [
            {"id": it.id, "title": it.title, "url": str(it.url),
             "days_old": it.days_old, "content_len": len(it.content_for_llm or ""),
             "quality_signals": it.quality_signals}
            for it in passed
        ])
        _dump_state("reddit_0_fastfail_dropped.json", [
            {"item_id": d.item_id, "verdict": d.verdict.value if hasattr(d.verdict, 'value') else str(d.verdict),
             "reason": d.reason}
            for d in dropped
        ])

        return FastFailBatch(
            source=SourceName.REDDIT,
            passed=passed,
            dropped=dropped,
            pass_rate=(len(passed) / n) if n else 0.0,
        )
