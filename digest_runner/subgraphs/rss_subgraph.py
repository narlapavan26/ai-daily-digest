"""
RSS subgraph: MCP POST /fetch/rss → normalize → fast-fail → Instructor LLM enrich → SubgraphOutput.

Pipeline:
  1. fetch_from_mcp()          → raw DigestItem list from MCP /fetch/rss
  2. _to_normalized()          → NormalizedItem (stable id, content_for_llm, quality_signals)
  3. _fast_fail_batch()        → FastFailBatch (drop stale / empty)
  4. _enrich_batch_with_llm()  → list[EnrichedItem] using Instructor + Groq (Gemini fallback)
  5. run()                     → SubgraphOutput with full telemetry

LLM Strategy:
  - Primary:  Groq llama-3.3-70b-versatile  (fast, generous free tier)
  - Fallback: Gemini gemini-2.0-flash-exp    (if Groq rate-limits or errors)
  - Items are processed in batches (default 8) to respect token limits.
  - Each item gets RelevanceAssessment first; irrelevant items are skipped for InsightExtraction.
  - instructor retry: up to 3 attempts on schema-validation failure.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from digest_runner.schemas.digest_schemas import (
    FastFailBatch,
    FastFailResult,
    FastFailVerdict,
    InsightExtraction,
    LLMProvider,
    NormalizedItem,
    NoveltyType,
    SourceName,
    SubgraphOutput,
    TimeSensitivity,
    ImpactedAudience
)
from digest_runner.config.settings import settings
from digest_runner.utils.mcp_client import post_fetch
from .base import BaseSubgraph, parse_utc_dt, enrich_normalized_items, is_junk_release

logger = logging.getLogger(__name__)

# Default feeds (used when none configured and use_verified_catalog=False)
DEFAULT_RSS_FEEDS: List[str] = [
    "https://huggingface.co/blog/feed.xml",
    "https://blog.langchain.com/rss",
    "https://github.com/langchain-ai/langgraph/releases.atom",
]


# ── Context enrichment ──────────────────────────────────────────────────

_BARE_VERSION_RE = re.compile(
    r"^(version|ver|v)?\s*[\d][\d.]+[\w.-]*\s*(released|available|is out|out now|launched)?$",
    re.IGNORECASE,
)
_GITHUB_REPO_RE = re.compile(
    r"github\.com/[^/]+/([^/]+)/releases",
    re.IGNORECASE,
)


def _enrich_title_with_context(title: str, url: str, feed_title: str) -> str:
    """
    If the title is a bare version string (e.g. 'Version 0.30.8 Released') with
    no recognisable framework name, extract the project name from the URL or
    feed_title and prepend it. This prevents the LLM from writing empty summaries
    because it has no idea what framework is being discussed.
    """
    if not _BARE_VERSION_RE.match(title.strip()):
        return title  # title already has meaningful context

    # Try to extract repo name from GitHub release URL
    m = _GITHUB_REPO_RE.search(url)
    if m:
        repo_name = m.group(1).replace("-", " ").replace("_", " ").title()
        return f"{repo_name} {title}"

    # Fall back to feed_title (e.g. 'Ollama Releases')
    if feed_title and len(feed_title) < 60:
        clean = re.sub(r"\s*(releases?|updates?|changelog)\s*$", "", feed_title, flags=re.I).strip()
        if clean:
            return f"{clean}: {title}"

    return title


# ── Normalization ──────────────────────────────────────────────────────────────

def _digest_item_to_normalized(row: Dict[str, Any]) -> NormalizedItem:
    """Map MCP DigestItem dict → NormalizedItem for LLM consumption."""
    published_at = parse_utc_dt(row["published_at"])
    now = time.time()
    days_old = max(0.0, (now - published_at.timestamp()) / 86400.0)
    md = row.get("metadata") or {}
    content = str(row.get("content") or "")
    raw_title = str(row["title"])
    feed_title = md.get("feed_title", "")

    # Enrich bare version titles (e.g. "Version 0.30.8 Released") with repo context
    title = _enrich_title_with_context(raw_title, row["url"], feed_title)

    # RSS content is already cleaned by MCP; just enforce 2400-char limit
    content_for_llm = content[:2400] if len(content) > 2400 else content

    return NormalizedItem(
        id=str(row["id"]),
        source=SourceName.RSS_FEEDS,
        title=title,   # enriched title with repo context if bare version
        url=row["url"],
        published_at=published_at,
        content_for_llm=content_for_llm,
        quality_signals={
            "feed":           md.get("feed", ""),
            "section":        md.get("section", ""),
            "feed_title":     md.get("feed_title", ""),
            "feed_url":       md.get("feed_url", ""),
            "summary_length": len(content),
        },
        days_old=days_old,
    )


# ── Fallback ──────────────────────────────────────────────────────────────────

def _fallback_insight(it: NormalizedItem) -> InsightExtraction:
    """Minimal fallback insight when LLM extraction fails for a relevant item."""
    return InsightExtraction(
        item_id=it.id,
        change_summary=f"{it.title[:200]} — see full post for details.",
        significance=(
            "Relevant to AI/ML practitioners; full insight extraction failed due to LLM error. "
            "Review the source directly."
        ),
        novelty_type="update",
        impacted_audience=["ml_engineers"],
        time_sensitivity="medium",
        actionable_insight=f"Read the full article at the source URL.",
        confidence=0.3,
    )


# ── Main subgraph class ────────────────────────────────────────────────────────

class RssSubgraph(BaseSubgraph):
    """
    Complete RSS data pipeline: MCP fetch → normalize → fast-fail → LLM enrich → SubgraphOutput.
        subgraph = RssSubgraph()                          # uses all verified catalog feeds
        subgraph = RssSubgraph(feed_urls=["https://..."]) # custom feeds
        output: SubgraphOutput = subgraph.run()
    """

    source = SourceName.RSS_FEEDS

    def __init__(
        self,
        feed_urls:            Optional[List[str]] = None,
        use_verified_catalog: bool                = True,
    ) -> None:
        self.feed_urls            = feed_urls or []
        self.use_verified_catalog = use_verified_catalog

    @property
    def budget(self) -> int:  # type: ignore[override]
        return settings.rss_subgraph_budget

    @property
    def stale_days(self) -> float:  # type: ignore[override]
        return settings.rss_fast_fail_stale_days

    def fetch_from_mcp(self) -> Dict[str, Any]:
        """POST /fetch/rss → raw JSON response from MCP server."""
        body: Dict[str, Any] = {
            "max_items_per_feed":   settings.rss_max_items_per_feed,
            "days_back":            settings.rss_days_back,
            "use_verified_catalog": self.use_verified_catalog,
        }
        if self.feed_urls:
            body["feed_urls"]            = self.feed_urls
            body["use_verified_catalog"] = False  # explicit list overrides catalog

        logger.info(
            "RSS subgraph: fetching from MCP (url=%s, catalog=%s, feeds=%s)",
            settings.mcp_base_url,
            body["use_verified_catalog"],
            len(self.feed_urls) if self.feed_urls else "catalog",
        )
        return post_fetch("/fetch/rss", body)

    def normalize(self, raw_items: List[Dict[str, Any]]) -> List[NormalizedItem]:
        """Map MCP DigestItem (RSS) → NormalizedItem."""
        result: List[NormalizedItem] = []
        for row in raw_items:
            try:
                result.append(_digest_item_to_normalized(row))
            except Exception as exc:
                logger.warning("RSS normalize error for %s: %s", row.get("id", "?"), exc)
        return result

    def fast_fail(self, normalized: List[NormalizedItem]) -> FastFailBatch:
        """
        RSS-specific fast-fail:
          - DROP_STALE if days_old > rss_fast_fail_stale_days
          - DROP_EMPTY if content_for_llm < settings.rss_min_content_length chars
          - DROP_EMPTY if title < 3 chars
        """
        passed:  List[NormalizedItem] = []
        dropped: List[FastFailResult] = []
        stale_thr   = settings.rss_fast_fail_stale_days
        min_content = settings.rss_min_content_length

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

            if it.days_old > stale_thr:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_STALE,
                    reason=f"days_old={it.days_old:.1f} > threshold={stale_thr}",
                    score=0.0,
                ))
            elif len(it.content_for_llm) < min_content:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_EMPTY,
                    reason=f"content_for_llm < {min_content} chars",
                    score=0.0,
                ))
            elif len(it.title.strip()) < 3:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_EMPTY,
                    reason="title missing or < 3 chars",
                    score=0.0,
                ))
            else:
                passed.append(it)

        n = len(normalized)
        pass_rate = (len(passed) / n) if n else 0.0
        logger.info(
            "RSS fast-fail: %d passed, %d dropped (%.0f%% pass rate)",
            len(passed), len(dropped), pass_rate * 100,
        )

        # ── Debug: dump fast-fail results to state/ ──────────────────────────
        from .base import _dump_state
        _dump_state("rss_feeds_0_fastfail_passed.json", [
            {"id": it.id, "title": it.title, "url": str(it.url),
             "days_old": it.days_old, "content_len": len(it.content_for_llm or "")}
            for it in passed
        ])
        _dump_state("rss_feeds_0_fastfail_dropped.json", [
            {"item_id": d.item_id, "verdict": d.verdict.value if hasattr(d.verdict, 'value') else str(d.verdict),
             "reason": d.reason}
            for d in dropped
        ])

        return FastFailBatch(
            source=SourceName.RSS_FEEDS,
            passed=passed,
            dropped=dropped,
            pass_rate=pass_rate,
        )

    def run(self) -> SubgraphOutput:
        """Execute the full RSS pipeline and return a SubgraphOutput."""
        t0 = time.perf_counter()
        all_errors: List[str] = []

        # ── 1. Fetch ────────────────────────────────────────────────────────────────
        try:
            raw = self.fetch_from_mcp()
        except Exception as exc:
            logger.error("RSS fetch from MCP failed: %s", exc)
            elapsed = (time.perf_counter() - t0) * 1000.0
            return SubgraphOutput(
                source=SourceName.RSS_FEEDS,
                enriched_items=[],
                total_reviewed=0,
                total_selected=0,
                fast_fail_dropped=0,
                llm_dropped=0,
                model_used=LLMProvider.GROQ,
                processing_ms=elapsed,
                used_fallback=False,
            )

        mcp_errors = raw.get("errors") or []
        all_errors.extend(mcp_errors)
        rows: List[Dict[str, Any]] = list(raw.get("items") or [])
        logger.info("RSS subgraph: MCP returned %d items (%d errors)", len(rows), len(mcp_errors))

        # ── 2. Normalize ────────────────────────────────────────────────────────────
        normalized = self.normalize(rows)

        # ── 3. Fast-fail ────────────────────────────────────────────────────────────
        ff_batch = self.fast_fail(normalized)

        # ── 4. LLM enrichment (via base.py shared function) ───────────────────────────
        enriched = []
        provider = LLMProvider.GROQ
        used_fallback = False

        if ff_batch.passed:
            try:
                enriched, provider, used_fallback, llm_errors = enrich_normalized_items(
                    ff_batch.passed,
                    budget=self.budget,
                    source_name=str(self.source),
                )
                all_errors.extend(llm_errors)
                for err in llm_errors:
                    logger.error("RSS LLM error: %s", err)
            except Exception as exc:
                logger.error("RSS LLM enrichment failed entirely: %s", exc)
                all_errors.append(f"LLM enrichment failed: {exc}")
        else:
            logger.warning("RSS subgraph: no items passed fast-fail — skipping LLM.")

        # ── 5. Build SubgraphOutput ───────────────────────────────────────────
        llm_dropped = len(ff_batch.passed) - len(enriched)
        elapsed_ms  = (time.perf_counter() - t0) * 1000.0

        logger.info(
            "RSS subgraph done: %d enriched | %d ff-dropped | %d llm-dropped | %.0fms",
            len(enriched), len(ff_batch.dropped), llm_dropped, elapsed_ms,
        )

        return SubgraphOutput(
            source=SourceName.RSS_FEEDS,
            enriched_items=enriched,
            total_reviewed=len(normalized),
            total_selected=len(enriched),
            fast_fail_dropped=len(ff_batch.dropped),
            llm_dropped=max(0, llm_dropped),
            model_used=provider,
            processing_ms=elapsed_ms,
            used_fallback=used_fallback,
        )
