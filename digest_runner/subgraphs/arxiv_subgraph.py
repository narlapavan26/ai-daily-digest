"""
ArXiv subgraph: MCP POST /fetch/arxiv → normalize → fast-fail → LLM enrich → SubgraphOutput.

Budget: controlled by settings.arxiv_budget (default 5 papers).
Stale threshold: settings.arxiv_stale_days (default 7 days — papers stay relevant longer).

Key design choices:
  - queries is now List[str]: we run EACH query separately and merge+deduplicate results.
    This covers more of the AI/ML space without blowing up the token budget.
  - content_for_llm = cleaned abstract (LaTeX stripped, 2000 chars max).
  - quality_signals = {primary_category, authors_count, pdf_url, citation_count}.
  - Fast-fail extras: drop if no abstract (content < 50 chars), drop if purely theoretical
    (primary_category starts with 'math.' or 'stat.' unless also tagged cs.*).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

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

# ── Default queries — covers the main AI/ML/LLM practitioner space ──────────────
# We run ALL of these and deduplicate by arxiv_id.
DEFAULT_ARXIV_QUERIES: List[str] = [
    "large language models agents tools",
    "llm inference serving optimization quantization",
    "multimodal foundation models vision language",
    "retrieval augmented generation RAG vector search",
    "diffusion models image video generation",
    "reinforcement learning from human feedback RLHF alignment",
    "transformer architecture attention efficiency",
    "ai safety interpretability alignment",
]

# Categories we consider "applied" enough for practitioners
_APPLIED_CATEGORIES = {
    "cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE", "cs.IR",
    "cs.SE", "cs.DC", "stat.ML", "eess.IV",
}


class ArxivSubgraph(BaseSubgraph):
    """
    Fetches recent ArXiv papers across multiple queries and selects the most
    relevant ones for practitioners.

    Usage:
        output = ArxivSubgraph().run()
        output = ArxivSubgraph(queries=["rag retrieval", "vllm serving"]).run()
        output = ArxivSubgraph(queries=["llm agents"], max_results=20).run()
    """

    source     = SourceName.ARXIV

    @property
    def budget(self) -> int:      # type: ignore[override]
        return settings.arxiv_budget

    @property
    def stale_days(self) -> float:  # type: ignore[override]
        return settings.arxiv_stale_days

    def __init__(
        self,
        queries:     Optional[List[str]] = None,
        max_results: Optional[int]       = None,
        days_back:   Optional[int]       = None,
    ) -> None:
        # Support old single-query API too: if a str is passed, wrap it
        if isinstance(queries, str):
            queries = [queries]
        self.queries     = queries or settings.arxiv_queries
        self.max_results = max_results if max_results is not None else settings.arxiv_max_results
        self.days_back   = days_back   if days_back   is not None else settings.arxiv_days_back

    def fetch_from_mcp(self) -> Dict[str, Any]:
        """
        Runs each query separately and merges all items, deduplicating by arxiv ID.
        Returns a synthetic SourceResponse dict with merged items.
        """
        logger.info(
            "ArXiv subgraph: fetching %d queries via MCP (days_back=%d, max_per_query=%d)",
            len(self.queries), self.days_back, self.max_results,
        )
        all_items:  List[Dict[str, Any]] = []
        all_errors: List[str]            = []
        seen_ids:   Set[str]             = set()

        for query in self.queries:
            try:
                resp = post_fetch("/fetch/arxiv", {
                    "query":       query,
                    "max_results": self.max_results,
                    "days_back":   self.days_back,
                })
                all_errors.extend(resp.get("errors") or [])
                for item in (resp.get("items") or []):
                    item_id = str(item.get("id") or "")
                    if item_id and item_id not in seen_ids:
                        seen_ids.add(item_id)
                        all_items.append(item)
            except Exception as exc:
                all_errors.append(f"ArXiv query '{query[:40]}' failed: {exc}")

        logger.info("ArXiv subgraph: %d unique items after dedup across %d queries", len(all_items), len(self.queries))
        return {"items": all_items, "errors": all_errors}

    def normalize(self, raw_items: List[Dict[str, Any]]) -> List[NormalizedItem]:
        """Map MCP DigestItem (arxiv) → NormalizedItem."""
        result: List[NormalizedItem] = []
        for row in raw_items:
            try:
                published_at = parse_utc_dt(row["published_at"])
                import datetime as _dt
                days_old = max(
                    0.0,
                    (_dt.datetime.now(_dt.timezone.utc) - published_at).total_seconds() / 86400.0,
                )
                content  = str(row.get("content") or "")
                md       = row.get("metadata") or {}

                # Prepend title to abstract so LLM has full context even on truncation
                title    = str(row.get("title") or "")
                content_for_llm = f"Title: {title}\n\nAbstract: {content}"
                content_for_llm = content_for_llm[:2400]

                # Authors as comma-separated string for quality_signals
                authors     = md.get("authors") or []
                authors_str = ", ".join(authors[:5]) if authors else "Unknown"
                primary_cat = md.get("primary_category", "")

                result.append(NormalizedItem(
                    id=str(row["id"]),
                    source=SourceName.ARXIV,
                    title=title,
                    url=row["url"],
                    published_at=published_at,
                    content_for_llm=content_for_llm,
                    quality_signals={
                        "primary_category": primary_cat,
                        "authors":          authors_str,
                        "authors_count":    len(authors),
                        "pdf_url":          md.get("pdf_url", ""),
                        "is_applied":       primary_cat in _APPLIED_CATEGORIES,
                    },
                    days_old=days_old,
                ))
            except Exception as exc:
                logger.warning("ArXiv normalize error for %s: %s", row.get("id", "?"), exc)
        return result

    def fast_fail(self, normalized: List[NormalizedItem]) -> FastFailBatch:
        """
        ArXiv-specific fast-fail (extends base stale/empty checks):
          - DROP_EMPTY  if abstract < 50 chars (likely a stub or failed fetch)
          - DROP_STALE  if days_old > stale_days
          - DROP_LOWSIG if NOT in applied categories and no cs.* category
            (pure math/stat papers with no ML/CS connection)
        Items that pass are sorted newest-first.
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

            content_len = len(it.content_for_llm)

            if it.days_old > self.stale_days:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_STALE,
                    reason=f"days_old={it.days_old:.1f} > {self.stale_days}",
                    score=0.0,
                ))
            elif content_len < 50:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_EMPTY,
                    reason=f"abstract too short ({content_len} chars < 50)",
                    score=0.0,
                ))
            elif not it.quality_signals.get("is_applied", True):
                cat = it.quality_signals.get("primary_category", "unknown")
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_LOWSIG,
                    reason=f"non-applied category '{cat}' — unlikely practitioner interest",
                    score=0.0,
                ))
            else:
                passed.append(it)

        # Sort newest-first so the LLM sees the freshest papers first
        passed.sort(key=lambda it: it.days_old)

        n = len(normalized)
        logger.info(
            "ArXiv fast-fail: %d passed, %d dropped (%.0f%% pass rate)",
            len(passed), len(dropped), (len(passed) / n * 100) if n else 0,
        )

        # ── Debug: dump fast-fail results to state/ ──────────────────────────
        from .base import _dump_state
        _dump_state("arxiv_0_fastfail_passed.json", [
            {"id": it.id, "title": it.title, "url": str(it.url),
             "days_old": it.days_old, "content_len": len(it.content_for_llm or ""),
             "quality_signals": it.quality_signals}
            for it in passed
        ])
        _dump_state("arxiv_0_fastfail_dropped.json", [
            {"item_id": d.item_id, "verdict": d.verdict.value if hasattr(d.verdict, 'value') else str(d.verdict),
             "reason": d.reason}
            for d in dropped
        ])

        return FastFailBatch(
            source=SourceName.ARXIV,
            passed=passed,
            dropped=dropped,
            pass_rate=(len(passed) / n) if n else 0.0,
        )
