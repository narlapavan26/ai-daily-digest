"""
digest_runner/subgraphs/stackoverflow_subgraph.py
=================================================
StackOverflow subgraph: MCP POST /fetch/stackoverflow → normalize → fast-fail → LLM enrich.

Budget: max 3 items (SO questions are very dense; 3 high-quality ones are enough).
Stale threshold: 7 days (a well-answered question remains useful for a week).

Fast-fail extras:
  - DROP_LOWSIG if score < 5 (community hasn't validated it)
  - Standard stale + empty checks

content_for_llm strategy:
  - Question title + cleaned body (HTML stripped)
  - Appended with top accepted/voted answer body if available
  - quality_signals carry: score, answer_count, view_count, is_answered, tags
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

DEFAULT_TAGS = [
    "llm", "langchain", "openai-api", "huggingface", "pytorch",
    "transformers", "langchain-python", "vector-database",
    "rag", "llama-index", "semantic-search", "embeddings",
]


class StackOverflowSubgraph(BaseSubgraph):
    """
    Fetches high-scoring AI/ML questions from StackOverflow.

    Key signals:
      - score: net upvotes (community correctness validation)
      - is_answered: whether an accepted answer exists
      - view_count: breadth of community interest
    """

    source     = SourceName.STACKOVERFLOW

    @property
    def budget(self) -> int:      # type: ignore[override]
        return settings.stackoverflow_budget

    @property
    def stale_days(self) -> float:  # type: ignore[override]
        return settings.stackoverflow_stale_days

    def __init__(
        self,
        tags:         List[str] | None = None,
        max_results:  Optional[int]    = None,
        days_back:    Optional[int]    = None,
        min_score:    Optional[int]    = None,
        sort:         str              = "votes",
    ) -> None:
        self.tags        = tags or settings.stackoverflow_tags
        self.max_results = max_results if max_results is not None else settings.stackoverflow_max_results
        self.days_back   = days_back   if days_back   is not None else settings.stackoverflow_days_back
        self.min_score   = min_score   if min_score   is not None else settings.stackoverflow_min_score
        self.sort        = sort

    def fetch_from_mcp(self) -> Dict[str, Any]:
        logger.info(
            "StackOverflow subgraph: fetching via MCP (tags=%s, sort=%s, min_score=%d)",
            self.tags[:4], self.sort, self.min_score,
        )
        return post_fetch("/fetch/stackoverflow", {
            "tags":        self.tags,
            "max_results": self.max_results,
            "days_back":   self.days_back,
            "min_score":   self.min_score,
            "sort":        self.sort,
        })

    def normalize(self, raw_items: List[Dict[str, Any]]) -> List[NormalizedItem]:
        """Map MCP DigestItem (stackoverflow question) → NormalizedItem."""
        result: List[NormalizedItem] = []
        for row in raw_items:
            try:
                published_at = parse_utc_dt(row["published_at"])
                import datetime as _dt
                days_old = max(
                    0.0,
                    (_dt.datetime.now(_dt.timezone.utc) - published_at).total_seconds() / 86400.0,
                )
                md          = row.get("metadata") or {}
                content     = str(row.get("content") or "").strip()
                title       = str(row.get("title") or "").strip()
                score       = int(md.get("score", 0))
                answer_count = int(md.get("answer_count", 0))
                view_count  = int(md.get("view_count", 0))
                is_answered = bool(md.get("is_answered", False))
                tags        = md.get("tags") or []

                # Build rich content_for_llm from question + answer
                tags_str = ", ".join(str(t) for t in tags[:8]) if tags else "none"
                parts = [
                    f"Question: {title}",
                    f"Score: {score} | Views: {view_count:,} | Answers: {answer_count} | Answered: {is_answered}",
                    f"Tags: {tags_str}",
                ]
                if content:
                    parts.append(f"\nBody + Best Answer:\n{content[:1600]}")

                content_for_llm = "\n".join(parts)

                if len(content_for_llm) < 30:
                    continue

                result.append(NormalizedItem(
                    id=str(row["id"]),
                    source=SourceName.STACKOVERFLOW,
                    title=title or "Untitled SO Question",
                    url=row["url"],
                    published_at=published_at,
                    content_for_llm=content_for_llm[:2400],
                    quality_signals={
                        "score":        score,
                        "answer_count": answer_count,
                        "view_count":   view_count,
                        "is_answered":  is_answered,
                        "tags":         tags,
                    },
                    days_old=days_old,
                ))
            except Exception as exc:
                logger.warning("SO normalize error for %s: %s", row.get("id", "?"), exc)
        return result

    def fast_fail(self, normalized: List[NormalizedItem]) -> FastFailBatch:
        """
        SO-specific fast-fail:
          - DROP_LOWSIG if score < MIN_SCORE_FF (unanswered low-score = not useful)
          - DROP_STALE  if days_old > stale_days
          - DROP_EMPTY  if content_for_llm < 30 chars
        Sort passed items by score descending.
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
            min_sc  = settings.stackoverflow_min_score

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
            elif len(it.content_for_llm) < 30:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_EMPTY,
                    reason="content_for_llm < 30 chars",
                    score=0.0,
                ))
            elif settings.stackoverflow_require_answer and not it.quality_signals.get("is_answered", False):
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_LOWSIG,
                    reason="no accepted answer (stackoverflow_require_answer=True)",
                    score=0.0,
                ))
            else:
                passed.append(it)

        # Sort by score descending — highest score means best-validated answer
        passed.sort(key=lambda it: int(it.quality_signals.get("score", 0)), reverse=True)

        n = len(normalized)
        logger.info(
            "SO fast-fail: %d passed, %d dropped (%s%% pass rate)",
            len(passed), len(dropped), f"{len(passed)/n*100:.0f}" if n else "0",
        )

        # ── Debug: dump fast-fail results to state/ ──────────────────────────
        from .base import _dump_state
        _dump_state("stackoverflow_0_fastfail_passed.json", [
            {"id": it.id, "title": it.title, "url": str(it.url),
             "days_old": it.days_old, "content_len": len(it.content_for_llm or ""),
             "quality_signals": it.quality_signals}
            for it in passed
        ])
        _dump_state("stackoverflow_0_fastfail_dropped.json", [
            {"item_id": d.item_id, "verdict": d.verdict.value if hasattr(d.verdict, 'value') else str(d.verdict),
             "reason": d.reason}
            for d in dropped
        ])

        return FastFailBatch(
            source=SourceName.STACKOVERFLOW,
            passed=passed,
            dropped=dropped,
            pass_rate=(len(passed) / n) if n else 0.0,
        )
