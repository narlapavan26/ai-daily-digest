"""
GitHub subgraph: MCP POST /fetch/github → normalize → fast-fail → LLM enrich → SubgraphOutput.

Budget: max 15 items (releases + trending repos combined).
Stale threshold: 3 days (repos are stale quickly; releases never drop).

Normalize strategy:
  - github_release → content_for_llm = top changelog lines (skip chore/deps lines)
  - github_repo    → content_for_llm = description + truncated readme_excerpt
  - quality_signals carry stars, forks, language, topics for fast-fail and LLM context.

The MCP /fetch/github endpoint returns both repo items (category=repo) and
release items (category=release) in a single response.
"""

from __future__ import annotations

import logging
import re
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

# Default topics now live in settings.github_topics (20 topics covering the full AI/ML space)
# Left here for backward compat with direct instantiation
DEFAULT_TOPICS = [
    "llm", "agent", "rag", "langchain", "langgraph", "llama",
    "openai", "diffusion", "vllm", "ollama", "huggingface",
    "embeddings", "vector-database", "ai-agent", "mcp",
    "crewai", "autogen", "dspy", "llamaindex", "haystack",
]

# Regex patterns to strip noisy changelog lines (chore, deps bumps, CI)
_NOISE_PATTERNS = re.compile(
    r"(?i)^[-*\s]*"
    r"(chore|ci|build|docs?|style|refactor|test|bump|update dep|dependabot|"
    r"pre-commit|autofix|fix typo|fix lint|format code|black|isort|ruff)\b"
)


def _filter_changelog_lines(notes: str, max_lines: int = 15) -> str:
    """Keep only meaningful changelog lines; skip chore/deps/CI noise."""
    lines = notes.splitlines()
    meaningful = [
        ln for ln in lines
        if ln.strip() and not _NOISE_PATTERNS.match(ln)
    ]
    return "\n".join(meaningful[:max_lines])


class GithubSubgraph(BaseSubgraph):
    """
    Fetches trending GitHub repos + framework releases and selects the best 15.

    Repos:     quality_signals = {stars, forks, language, topics}
    Releases:  quality_signals = {framework, repo, version}
    """

    source     = SourceName.GITHUB_RELEASE   # Will handle both release + repo items

    @property
    def budget(self) -> int:      # type: ignore[override]
        return settings.github_budget

    @property
    def stale_days(self) -> float:  # type: ignore[override]
        return settings.github_stale_days

    def __init__(
        self,
        topics:      Optional[List[str]] = None,
        max_results: Optional[int]       = None,
        days_back:   Optional[int]       = None,
    ) -> None:
        self.topics      = topics or settings.github_topics
        self.max_results = max_results if max_results is not None else settings.github_max_results
        self.days_back   = days_back   if days_back   is not None else settings.github_days_back

    def fetch_from_mcp(self) -> Dict[str, Any]:
        logger.info("GitHub subgraph: fetching via MCP (topics=%s)", self.topics[:4])
        return post_fetch("/fetch/github", {
            "topics":      self.topics,
            "max_results": self.max_results,
            "days_back":   self.days_back,
        })

    def normalize(self, raw_items: List[Dict[str, Any]]) -> List[NormalizedItem]:
        """Map MCP DigestItem (github repo OR release) → NormalizedItem."""
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
                category = str(row.get("category") or "repo")
                content  = str(row.get("content") or "")

                if category == "release":
                    # Framework release — extract key changelog lines
                    clean_notes    = _filter_changelog_lines(content, max_lines=15)
                    content_for_llm = clean_notes[:2000] if len(clean_notes) > 2000 else clean_notes
                    source_name     = SourceName.GITHUB_RELEASE
                    quality_signals = {
                        "framework": md.get("framework", ""),
                        "repo":      md.get("repo", ""),
                        "version":   md.get("version", ""),
                        "category":  "release",
                    }
                else:
                    # Trending or new repo
                    stars    = int(md.get("stars", 0))
                    desc     = content[:2000] if len(content) > 2000 else content
                    content_for_llm = desc
                    source_name     = SourceName.GITHUB_REPO
                    quality_signals = {
                        "stars":    stars,
                        "forks":    int(md.get("forks", 0)),
                        "language": md.get("language", ""),
                        "topics":   md.get("topics", []),
                        "category": category,
                    }

                if len(content_for_llm) < 15:
                    continue  # skip items with no useful content

                result.append(NormalizedItem(
                    id=str(row["id"]),
                    source=source_name,
                    title=str(row["title"]),
                    url=row["url"],
                    published_at=published_at,
                    content_for_llm=content_for_llm,
                    quality_signals=quality_signals,
                    days_old=days_old,
                ))
            except Exception as exc:
                logger.warning("GitHub normalize error for %s: %s", row.get("id", "?"), exc)
        return result

    def fast_fail(self, normalized: List[NormalizedItem]) -> FastFailBatch:
        """
        GitHub-specific fast-fail:
          - Releases: never drop (always fresh by definition)
          - Repos:    drop if stars < 50 AND days_old > 1 (too obscure + stale)
          - Any:      drop if content_for_llm < 20 chars
        """
        passed: List[NormalizedItem] = []
        dropped: List[FastFailResult] = []

        for it in normalized:
            # Global junk filter — applied before any source-specific rules
            is_junk, junk_reason = is_junk_release(it, source_name="github")
            if is_junk:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_LOWSIG,
                    reason=f"global_junk_filter: {junk_reason}",
                ))
                continue

            cat = it.quality_signals.get("category", "repo")

            if len(it.content_for_llm) < settings.github_min_content_length:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_EMPTY,
                    reason=f"content_for_llm < {settings.github_min_content_length} chars",
                    score=0.0,
                ))
                continue

            if cat == "release":
                # Releases are always kept — they are by definition fresh
                passed.append(it)
                continue

            stars = int(it.quality_signals.get("stars", 0))
            min_stars = settings.github_min_stars
            if stars < min_stars and it.days_old > 1:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_LOWSIG,
                    reason=f"stars={stars} < {min_stars} AND days_old={it.days_old:.1f} > 1",
                    score=0.0,
                ))
                continue

            if it.days_old > self.stale_days:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_STALE,
                    reason=f"days_old={it.days_old:.1f} > {self.stale_days}",
                    score=0.0,
                ))
                continue

            passed.append(it)

        n = len(normalized)
        logger.info(
            "GitHub fast-fail: %d passed, %d dropped (%.0f%% pass rate)",
            len(passed), len(dropped), (len(passed) / n * 100) if n else 0,
        )

        # ── Debug: dump fast-fail results to state/ ──────────────────────────
        from .base import _dump_state
        _dump_state("github_0_fastfail_passed.json", [
            {"id": it.id, "title": it.title, "url": str(it.url),
             "days_old": it.days_old, "content_len": len(it.content_for_llm or ""),
             "quality_signals": it.quality_signals}
            for it in passed
        ])
        _dump_state("github_0_fastfail_dropped.json", [
            {"item_id": d.item_id, "verdict": d.verdict.value if hasattr(d.verdict, 'value') else str(d.verdict),
             "reason": d.reason}
            for d in dropped
        ])

        return FastFailBatch(
            source=SourceName.GITHUB_RELEASE,
            passed=passed,
            dropped=dropped,
            pass_rate=(len(passed) / n) if n else 0.0,
        )
