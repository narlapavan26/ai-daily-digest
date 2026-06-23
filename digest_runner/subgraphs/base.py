"""
digest_runner/subgraphs/base.py
================================
BaseSubgraph: shared protocol and helpers for all source subgraphs.

Every source subgraph (rss, arxiv, github, hackernews …) inherits from or
follows this interface so the master digest_graph.py can call them uniformly:

    output: SubgraphOutput = subgraph.run()
"""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from digest_runner.schemas.digest_schemas import (
    DigestSectionName,
    EnrichedItem,
    FastFailBatch,
    FastFailResult,
    FastFailVerdict,
    InsightExtraction,
    LLMProvider,
    NormalizedItem,
    NoveltyType,
    RelevanceAssessment,
    SourceName,
    SubgraphOutput,
    TimeSensitivity,
    ImpactedAudience,
)
from digest_runner.config.settings import settings
from digest_runner.utils.mcp_client import post_fetch

logger = logging.getLogger(__name__)

# ── Debug state directory ─────────────────────────────────────────────────────
_STATE_DIR = Path(__file__).resolve().parents[2] / "state"


def _dump_state(filename: str, data: Any) -> None:
    """Save intermediate pipeline data to state/ folder for debugging."""
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        path = _STATE_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
        logger.debug("Debug state saved: %s", path)
    except Exception as exc:
        logger.warning("Failed to dump debug state %s: %s", filename, exc)

# ── Provider configuration map ────────────────────────────────────────────────
# Maps each LLMProvider to its endpoint, model, and settings key.
# All providers use the OpenAI-compatible chat completions API.
_PROVIDER_CONFIGS: Dict[LLMProvider, Dict[str, Any]] = {
    LLMProvider.GROQ: {
        "key_field": "groq_api_key",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    LLMProvider.CEREBRAS: {
        "key_field": "cerebras_api_key",
        "base_url": "https://api.cerebras.ai/v1",
        "model": "gpt-oss-120b",
    },
    LLMProvider.OPENROUTER: {
        "key_field": "openrouter_api_key",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
    },
    LLMProvider.GEMINI: {
        "key_field": "gemini_api_key",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash-lite",
    },
    LLMProvider.GITHUB: {
        "key_field": "github_models_api_key",
        "base_url": "https://models.inference.ai.azure.com",
        "model": "gpt-4o-mini",
    },
    LLMProvider.OLLAMA: {
        "key_field": "ollama_api_key",
        "base_url": "https://ollama.com/v1",
        "model": "gemma4:31b",
    },
    LLMProvider.SAMBANOVA: {
        "key_field": "sambanova_api_key",
        "base_url": "https://api.sambanova.ai/v1",
        "model": "Meta-Llama-3.3-70B-Instruct",
    },
}

# Backwards-compatible constants
GROQ_MODEL   = _PROVIDER_CONFIGS[LLMProvider.GROQ]["model"]
GEMINI_MODEL = _PROVIDER_CONFIGS[LLMProvider.GEMINI]["model"]
BATCH_SIZE   = 8   # overridden at runtime from settings.llm_batch_size
MAX_RETRIES  = 3   # overridden at runtime from settings.llm_max_retries

# Novelty → Digest section mapping (shared across all subgraphs)
NOVELTY_TO_SECTION: Dict[NoveltyType, DigestSectionName] = {
    NoveltyType.NEW_RELEASE:  DigestSectionName.FRAMEWORK_RELEASES,
    NoveltyType.MODEL_DROP:   DigestSectionName.MODEL_RELEASES,
    NoveltyType.NEW_REPO:     DigestSectionName.NEW_TOOLS,
    NoveltyType.TOOL_LAUNCH:  DigestSectionName.NEW_TOOLS,
    NoveltyType.BREAKTHROUGH: DigestSectionName.RESEARCH,
    NoveltyType.UPDATE:       DigestSectionName.INFRASTRUCTURE,
    NoveltyType.TRENDING:     DigestSectionName.COMMUNITY_BUZZ,
    NoveltyType.DISCUSSION:   DigestSectionName.COMMUNITY_BUZZ,
    # Extended values — map to most appropriate existing sections
    NoveltyType.NEW_FEATURE:  DigestSectionName.FRAMEWORK_RELEASES,
    NoveltyType.NEW_SERVICE:  DigestSectionName.NEW_TOOLS,
    NoveltyType.NEW_PROJECT:  DigestSectionName.NEW_TOOLS,
    NoveltyType.ARTICLE:      DigestSectionName.COMMUNITY_BUZZ,
    NoveltyType.ANNOUNCEMENT: DigestSectionName.FRAMEWORK_RELEASES,
    NoveltyType.BLOG_POST:    DigestSectionName.COMMUNITY_BUZZ,
    NoveltyType.TUTORIAL:     DigestSectionName.COMMUNITY_BUZZ,
    NoveltyType.SECURITY_FIX: DigestSectionName.INFRASTRUCTURE,
    NoveltyType.DEPRECATION:  DigestSectionName.INFRASTRUCTURE,
    NoveltyType.BENCHMARK:    DigestSectionName.RESEARCH,
}

# ── Global junk-release filter ───────────────────────────────────────────────
# Applied BEFORE source-specific fast_fail. Drops items that are definitively
# noise regardless of source: CI commits, dev builds, subpackage releases, etc.

_JUNK_TITLE_RE = re.compile(
    r"(\.dev\d*|-rc\d*|-alpha\d*|-beta\d*|nightly|pre-release|pre_release)"
    r"|^@[\w/-]+@"                        # scoped npm/monorepo packages: @gradio/uploadbutton
    r"|^\s*(trunk/|viable/strict/|[a-f0-9]{7,}\s*$)"  # hex commit hashes
    r"|(trunk|viable.strict)/.+"         # pytorch/pytorch CI tags
    r"|^b\d{4,}\s*(released|$)"          # llama.cpp build tags: b9619 Released
    r"|release\s+\d+\.\d+\.\d+\.dev"   # explicit dev releases
    r"|^version\s+\d+[\d.]+\s+(released|available)$",  # bare 'Version X.Y.Z Released' with no context
    re.IGNORECASE,
)

# Conventional-commit prefixes — only applied to GitHub source items.
# Avoids false positives on RSS/blog titles like "Build context-rich research agents..."
_CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(fix|chore|ci|test|bump|lint|docs|refactor|style|perf|build)\b\s*[:(/]",
    re.IGNORECASE,
)

_JUNK_URL_RE = re.compile(
    r"/releases/tag/(trunk%2F|viable%2Fstrict%2F|[a-f0-9]{7,}$)"  # CI commit tags in URLs
    r"|/releases/tag/[^/]*%40[^/]*@"     # scoped package URL encoding (@gradio%2Ftimer@)
    r"|\.dev\d*$|-rc\d*$",              # dev/rc in URL tag
    re.IGNORECASE,
)


def is_junk_release(item: "NormalizedItem", source_name: str = "") -> tuple[bool, str]:
    """
    Returns (True, reason) if the item is definitively junk, (False, "") otherwise.

    Catches:
    - .dev / -rc / -alpha / -beta / nightly builds
    - Monorepo subpackage releases (@gradio/uploadbutton)
    - Git commit hash tags (b9619, viable/strict/abc123)
    - CI/CD conventional commit titles (GitHub source only)
    - Bare version strings with no repo context ('Version 0.30.8 Released')
    """
    title = str(item.title or "").strip()
    url   = str(item.url   or "").strip()

    if _JUNK_TITLE_RE.search(title):
        return True, f"junk_title_pattern: {title[:80]}"

    if _JUNK_URL_RE.search(url):
        return True, f"junk_url_pattern: {url[:120]}"

    # Conventional-commit titles — only for GitHub source to avoid false
    # positives on RSS/blog titles like "Build context-rich research agents..."
    is_github = "github" in source_name.lower()
    if is_github and _CONVENTIONAL_COMMIT_RE.search(title):
        return True, f"conventional_commit_title: {title[:80]}"

    # Bare 'Version X.Y.Z Released' — no framework name in title
    bare_version_re = re.compile(
        r"^(version|ver|v)\s+[\d][\d.]+[\w.-]*\s+(released|available|is out|out now)?$",
        re.IGNORECASE,
    )
    if bare_version_re.match(title.strip()):
        return True, f"bare_version_no_context: {title[:80]}"

    # Content too short to be real news (< 30 chars means title-only RSS)
    content = (item.content_for_llm or "").strip()
    if len(content) < 30 and len(title) < 60:
        return True, f"no_content_too_short: content={len(content)}chars title={len(title)}chars"

    return False, ""


_SYSTEM_PROMPT = """You are a thorough editorial AI for a senior ML engineer audience. Your job is quality curation with good coverage.

KEEP — items that deliver concrete technical value:
  - Major framework releases (LangChain, LangGraph, vLLM, Ollama, llama.cpp, CrewAI, AutoGen, Haystack, DSPy, LlamaIndex)
  - New model weights or architectures (LLMs, VLMs, embedding models, diffusion models) — ONLY official announcements
  - Meaningful version bumps with changelog substance (new features, breaking changes, performance wins)
  - Research papers with real benchmarks AND a clear engineering application
  - New developer tools, SDKs, or libraries with demonstrated capability
  - Vector database updates (Qdrant, Chroma, Weaviate, FAISS, Milvus, pgvector)
  - Inference/serving improvements (vLLM, TGI, SGLang, Ray Serve, Triton, BentoML)
  - Blog posts, tutorials, or announcements from authoritative sources (HuggingFace, OpenAI, Google DeepMind, Anthropic, Mistral)

DROP IMMEDIATELY — do not even debate these:
  - CI/CD commits, test skips, lint fixes, dependency bumps (title contains: fix, skip, bump, chore, ci, test)
  - Git commit hash tags or trunk builds (title/URL contains: trunk/, viable/strict/, hex strings like b9619)
  - Nightly/dev/pre-release builds (.dev, -rc, -alpha, -beta, nightly, pre-release in title)
  - Monorepo subpackage releases (@gradio/uploadbutton, @gradio/timer — scoped package names)
  - Items with no technical body — title only, no implementation details
  - GitHub support tickets, issues, or discussions
  - Content where title says only "Version X.Y.Z Released" with no repo/framework name
  - Pure marketing or HR announcements with zero technical content
  - Academic papers with zero practical implementation or benchmark data

QUALITY RULES:
  - Do NOT call inference frameworks (vLLM, llama.cpp, Ollama, PyTorch) a "model". They are frameworks.
  - Do NOT write "full details in linked article" — if you cannot extract substance, set is_relevant=False.
  - A senior ML engineer would find this item useful or interesting — if you doubt it, KEEP it (err on the side of inclusion for borderline cases).
  - IMPORTANT: You MUST provide a specific reject_reason for every item where is_relevant=False. If you cannot articulate WHY an item is irrelevant, set is_relevant=True instead.

is_relevant=True is the default for borderline items. Only drop items that are CLEARLY noise, beginner content, or non-technical."""


# ── Shared LLM utilities ────────────────────────────────────────────────────────

def get_instructor_client(provider: LLMProvider = LLMProvider.GROQ) -> Tuple[Any, str]:
    """
    Returns (instructor_client, model_name) for the requested provider.

    Supports: Groq, Cerebras, OpenRouter, Gemini, Ollama (local).
    Reads API keys from settings (pydantic-settings loads .env reliably).
    Falls back to os.environ for any shell-set environment variables.
    """
    import os
    try:
        import instructor
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(f"Missing: {e}. Run: pip install instructor openai") from e

    cfg = _PROVIDER_CONFIGS.get(provider)
    if cfg is None:
        raise ValueError(f"Unsupported provider: {provider}")

    key_field = cfg["key_field"]
    base_url  = cfg["base_url"]
    model     = cfg["model"]

    # Resolve API key from settings first, then os.environ
    if key_field is not None:
        key = (
            getattr(settings, key_field, None)
            or os.environ.get(key_field.upper(), "")
            or ""
        ).strip()
        if not key:
            raise RuntimeError(f"{key_field.upper()} not set")
    else:
        key = "ollama"  # Ollama accepts any non-empty key string

    # Use JSON mode for providers that return malformed function calls in TOOLS mode.
    # Gemini returns "MALFORMED_FUNCTION_CALL" and triggers
    # "Instructor does not support multiple tool calls" errors.
    # Ollama Cloud also sometimes has this issue.
    if provider in (LLMProvider.GEMINI, LLMProvider.OLLAMA):
        client = instructor.from_openai(
            OpenAI(api_key=key, base_url=base_url, max_retries=0),
            mode=instructor.Mode.JSON,
        )
    else:
        client = instructor.from_openai(
            OpenAI(api_key=key, base_url=base_url, max_retries=0),
        )
    return client, model




def run_relevance_batch(
    batch: List[NormalizedItem],
    client: Any,
    model: str,
    source_hint: str = "",
) -> List[RelevanceAssessment]:
    """LLM relevance assessment for a batch of NormalizedItems."""
    from pydantic import BaseModel as PydanticBase, model_validator as mv

    class RelevanceBatch(PydanticBase):
        assessments: List[RelevanceAssessment]

        @mv(mode="before")
        @classmethod
        def _wrap_flat_response(cls, data: Any) -> Any:
            """If LLM returns a flat assessment dict instead of {'assessments': [...]}, wrap it."""
            if isinstance(data, dict) and "assessments" not in data and ("item_id" in data or "id" in data):
                return {"assessments": [data]}
            return data

    lines = [f"Assess relevance of these {source_hint} items:\n"
             f"STRICT RULES: Set is_relevant=False for any item that (1) has no technical substance, "
             f"(2) is a CI/CD commit/test-skip/lint-fix, (3) is a dev/rc/alpha/beta/nightly build, "
             f"(4) is a monorepo subpackage, (5) has content under 100 chars with no real detail. "
             f"Relevance score 0.0-1.0: use the FULL range — most items should score 0.3-0.6, only groundbreaking news scores 0.9-1.0. Do NOT use integers — use decimal floats between 0.0 and 1.0.\n"
             f"CRITICAL: For every item where is_relevant=False, you MUST provide a specific reject_reason explaining WHY. "
             f"If you cannot articulate a clear reason to reject, set is_relevant=True instead.\n"]
    for i, it in enumerate(batch, 1):
        lines.append(
            f"[{i}] ID={it.id}\n"
            f"    Title: {it.title}\n"
            f"    Published: {it.published_at.strftime('%Y-%m-%d')} ({it.days_old:.1f}d ago)\n"
            f"    Signals: {it.quality_signals}\n"
            f"    Content: {it.content_for_llm[:700]}\n"
        )

    result: RelevanceBatch = client.chat.completions.create(
        model=model,
        response_model=RelevanceBatch,
        max_retries=2,  # Let instructor fix missing fields via validation errors
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": "\n".join(lines)},
        ],
        temperature=0.1,
    )
    return result.assessments


def run_insight_batch(
    batch: List[NormalizedItem],
    client: Any,
    model: str,
    source_hint: str = "",
) -> List[InsightExtraction]:
    """LLM insight extraction for a batch of relevant NormalizedItems."""
    from pydantic import BaseModel as PydanticBase, model_validator as mv

    class InsightBatch(PydanticBase):
        insights: List[InsightExtraction]

        @mv(mode="before")
        @classmethod
        def _wrap_flat_response(cls, data: Any) -> Any:
            """If LLM returns a flat insight dict instead of {'insights': [...]}, wrap it."""
            if isinstance(data, dict) and "insights" not in data and ("item_id" in data or "id" in data):
                return {"insights": [data]}
            return data

    lines = [f"Extract insights for these {source_hint} items.\n"
             f"STRICT RULES: (1) Never write 'full details in linked article' — extract real substance from the content. "
             f"(2) Never call inference frameworks (vLLM, llama.cpp, Ollama, PyTorch, TGI) a 'model' — they are frameworks. "
             f"(3) change_summary must state WHAT specifically changed, not just 'was released'. "
             f"(4) actionable_insight must be concrete: upgrade command, API change, benchmark number, or architecture detail. "
             f"(5) If the item has no extractable substance, set confidence=0.1 and note it in significance.\n"]
    for i, it in enumerate(batch, 1):
        lines.append(
            f"[{i}] ID={it.id}\n"
            f"    Title: {it.title}\n"
            f"    Signals: {it.quality_signals}\n"
            f"    Content:\n{it.content_for_llm[:1400]}\n"
        )

    result: InsightBatch = client.chat.completions.create(
        model=model,
        response_model=InsightBatch,
        max_retries=2,  # Let instructor fix missing fields via validation errors
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": "\n".join(lines)},
        ],
        temperature=0.2,
    )
    return result.insights


def enrich_normalized_items(
    passed: List[NormalizedItem],
    budget: int,
    source_name: str = "items",
) -> Tuple[List[EnrichedItem], LLMProvider, bool, List[str]]:
    """
    Shared 2-step LLM enrichment for any subgraph:
      Step 1: Relevance screening (batched)
      Step 2: Insight extraction for relevant items (batched)
    Returns: (enriched_items, provider_used, used_fallback, errors)
    """
    enriched:  List[EnrichedItem] = []
    errors:    List[str]          = []
    used_fallback = False

    # ── Initialise LLM client via ProviderPool (auto-rotates on 429) ──────────
    from digest_runner.utils.provider_pool import ProviderPool, is_rate_limit_error, is_provider_broken
    try:
        # Check if providers are available and get a default one for the return statement
        _, _, initial_provider = ProviderPool.get_client()
    except RuntimeError as exc:
        errors.append(f"All LLM providers unavailable: {exc}")
        # All providers unavailable — use fallback insights for top-budget items
        logger.warning(
            "%s: all LLM providers unavailable — using static fallback insights for top %d items",
            source_name, budget,
        )
        for it in passed[:budget]:
            fallback_insight = _minimal_fallback_insight(it)
            # Convert str → enum (InsightExtraction now uses str)
            try:
                fb_novelty = NoveltyType(fallback_insight.novelty_type)
            except (ValueError, KeyError):
                fb_novelty = NoveltyType.UPDATE
            try:
                fb_time_sens = TimeSensitivity(fallback_insight.time_sensitivity)
            except (ValueError, KeyError):
                fb_time_sens = TimeSensitivity.MEDIUM
            fb_audience = []
            for aud_str in fallback_insight.impacted_audience:
                try:
                    fb_audience.append(ImpactedAudience(aud_str))
                except (ValueError, KeyError):
                    pass
            if not fb_audience:
                fb_audience = [ImpactedAudience.ML_ENGINEERS]

            section = NOVELTY_TO_SECTION.get(fb_novelty, DigestSectionName.QUICK_LINKS)
            try:
                enriched.append(EnrichedItem(
                    id=it.id, source=it.source, title=it.title, url=it.url,
                    published_at=it.published_at, days_old=it.days_old,
                    quality_signals=it.quality_signals,
                    is_relevant=True, relevance_score=0.5, reject_reason=None,
                    change_summary=fallback_insight.change_summary,
                    significance=fallback_insight.significance,
                    novelty_type=fb_novelty,
                    impacted_audience=fb_audience,
                    time_sensitivity=fb_time_sens,
                    actionable_insight=fallback_insight.actionable_insight,
                    confidence=fallback_insight.confidence,
                    digest_section=section,
                    enriched_by=LLMProvider.GROQ,
                    selection_rank=len(enriched) + 1,
                ))
            except Exception as build_exc:
                errors.append(f"Fallback EnrichedItem build failed for {it.id}: {build_exc}")
        return enriched, LLMProvider.GROQ, False, errors

    assessment_map: Dict[str, RelevanceAssessment] = {}
    insight_map:    Dict[str, InsightExtraction]   = {}

    batch_size  = settings.llm_batch_size
    sleep_secs  = 0.5  # Minimal delay; ProviderPool.acquire() handles rate pacing

    # ── Cap items for LLM screening (free-tier budget optimisation) ────────────
    # Screen budget*8 items — with 7 providers doing per-batch round-robin,
    # this costs ~12 batches = ~2 calls per provider, well within free-tier limits.
    max_to_screen = max(budget * 8, batch_size * 2)  # At least 2 full batches
    capped_items = []
    if len(passed) > max_to_screen:
        logger.info(
            "%s: capping LLM screening from %d to %d items (budget=%d)",
            source_name, len(passed), max_to_screen, budget,
        )
        capped_items = passed[max_to_screen:]  # items that won't be screened
        passed = passed[:max_to_screen]

    # ── Debug: dump items entering LLM screening ──────────────────────────────
    src_tag = source_name.replace('SourceName.', '').lower()
    _dump_state(f"{src_tag}_1_items_for_llm.json", [
        {"id": it.id, "title": it.title, "url": str(it.url),
         "days_old": it.days_old, "content_preview": (it.content_for_llm or "")[:200]}
        for it in passed
    ])
    if capped_items:
        _dump_state(f"{src_tag}_1b_capped_items_not_screened.json", [
            {"id": it.id, "title": it.title, "url": str(it.url),
             "days_old": it.days_old, "content_preview": (it.content_for_llm or "")[:200]}
            for it in capped_items
        ])

    # ── Step 1: relevance ─────────────────────────────────────────────────────

    for start in range(0, len(passed), batch_size):
        if start > 0:
            time.sleep(sleep_secs)
        batch = passed[start : start + batch_size]
        try:
            client, model, provider = ProviderPool.get_client()
            logger.debug("%s: relevance batch %d using %s", source_name, start, provider.value)
            ProviderPool.acquire(provider)
            try:
                for a in run_relevance_batch(batch, client, model, source_name):
                    assessment_map[a.item_id] = a
            finally:
                ProviderPool.release()
            ProviderPool.mark_success(provider)
        except Exception as exc:
            errors.append(f"Relevance[{start}] {provider.value} failed: {exc}")
            if is_provider_broken(exc):
                ProviderPool.mark_rate_limited(provider, cooldown_secs=600)  # 10 min for 404/auth
                logger.error("%s: provider %s broken (404/auth) — skipping for 10min", source_name, provider.value)
            elif is_rate_limit_error(exc):
                ProviderPool.mark_rate_limited(provider)
            # Try next available provider
            try:
                client, model, provider = ProviderPool.get_client()
                used_fallback = True
                logger.info("%s: switched to %s for relevance batch %d", source_name, provider.value, start)
                ProviderPool.acquire(provider)
                try:
                    for a in run_relevance_batch(batch, client, model, source_name):
                        assessment_map[a.item_id] = a
                finally:
                    ProviderPool.release()
                ProviderPool.mark_success(provider)
            except Exception as exc2:
                errors.append(f"Relevance[{start}] fallback also failed: {exc2}")

    # ── Debug: dump all relevance assessments ─────────────────────────────────
    _dump_state(f"{src_tag}_2_relevance_results.json", [
        {"item_id": a.item_id, "is_relevant": a.is_relevant,
         "relevance_score": a.relevance_score, "reject_reason": a.reject_reason}
        for a in assessment_map.values()
    ])

    # ── Step 2: insights for relevant items ───────────────────────────────────
    relevant = [it for it in passed if assessment_map.get(it.id) and assessment_map[it.id].is_relevant]
    logger.info("%s: %d/%d items relevant after LLM screening", source_name, len(relevant), len(passed))

    for start in range(0, len(relevant), batch_size):
        if start > 0:
            time.sleep(sleep_secs)
        batch = relevant[start : start + batch_size]
        try:
            client, model, provider = ProviderPool.get_client()
            logger.debug("%s: insight batch %d using %s", source_name, start, provider.value)
            ProviderPool.acquire(provider)
            try:
                for ins in run_insight_batch(batch, client, model, source_name):
                    insight_map[ins.item_id] = ins
            finally:
                ProviderPool.release()
            ProviderPool.mark_success(provider)
        except Exception as exc:
            errors.append(f"Insight[{start}] {provider.value} failed: {exc}")
            if is_provider_broken(exc):
                ProviderPool.mark_rate_limited(provider, cooldown_secs=600)  # 10 min for 404/auth
                logger.error("%s: provider %s broken (404/auth) — skipping for 10min", source_name, provider.value)
            elif is_rate_limit_error(exc):
                ProviderPool.mark_rate_limited(provider)
            # Try next available provider
            try:
                client, model, provider = ProviderPool.get_client()
                used_fallback = True
                logger.info("%s: switched to %s for insight batch %d", source_name, provider.value, start)
                ProviderPool.acquire(provider)
                try:
                    for ins in run_insight_batch(batch, client, model, source_name):
                        insight_map[ins.item_id] = ins
                finally:
                    ProviderPool.release()
                ProviderPool.mark_success(provider)
            except Exception as exc2:
                errors.append(f"Insight[{start}] fallback also failed: {exc2}")

    # ── Debug: dump insight results ───────────────────────────────────────────
    _dump_state(f"{src_tag}_3_insight_results.json", [
        {"item_id": ins.item_id, "change_summary": ins.change_summary,
         "significance": ins.significance, "novelty_type": ins.novelty_type.value if hasattr(ins.novelty_type, 'value') else str(ins.novelty_type),
         "time_sensitivity": ins.time_sensitivity.value if hasattr(ins.time_sensitivity, 'value') else str(ins.time_sensitivity),
         "actionable_insight": ins.actionable_insight, "confidence": ins.confidence}
        for ins in insight_map.values()
    ])

    # ── Step 3: assemble EnrichedItems ────────────────────────────────────────
    rank = 0
    for it in relevant:
        if rank >= budget:
            break
        assessment = assessment_map.get(it.id)
        insight    = insight_map.get(it.id)
        if not assessment or not assessment.is_relevant:
            continue
        if not insight:
            errors.append(f"No insight for {it.id}; using fallback")
            insight = _minimal_fallback_insight(it)

        rank += 1
        # Convert str → NoveltyType enum (InsightExtraction uses str to avoid
        # API-level 400 errors, but downstream code needs the enum).
        try:
            novelty_enum = NoveltyType(insight.novelty_type)
        except (ValueError, KeyError):
            novelty_enum = NoveltyType.UPDATE
        section = NOVELTY_TO_SECTION.get(novelty_enum, DigestSectionName.QUICK_LINKS)

        # Similarly convert impacted_audience and time_sensitivity strings
        try:
            time_sens_enum = TimeSensitivity(insight.time_sensitivity)
        except (ValueError, KeyError):
            time_sens_enum = TimeSensitivity.MEDIUM
        audience_enums = []
        for aud_str in insight.impacted_audience:
            try:
                audience_enums.append(ImpactedAudience(aud_str))
            except (ValueError, KeyError):
                pass
        if not audience_enums:
            audience_enums = [ImpactedAudience.ML_ENGINEERS]

        try:
            enriched.append(EnrichedItem(
                id=it.id, source=it.source, title=it.title, url=it.url,
                published_at=it.published_at, days_old=it.days_old,
                quality_signals=it.quality_signals,
                is_relevant=True,
                relevance_score=assessment.relevance_score,
                reject_reason=assessment.reject_reason,
                change_summary=insight.change_summary,
                significance=insight.significance,
                novelty_type=novelty_enum,
                impacted_audience=audience_enums,
                time_sensitivity=time_sens_enum,
                actionable_insight=insight.actionable_insight,
                confidence=insight.confidence,
                digest_section=section,
                enriched_by=provider,
                selection_rank=rank,
            ))
        except Exception as exc:
            errors.append(f"EnrichedItem build failed for {it.id}: {exc}")
            rank -= 1

    return enriched, initial_provider, used_fallback, errors


def _minimal_fallback_insight(it: NormalizedItem) -> InsightExtraction:
    """Fallback when LLM insight extraction fails for a relevant item."""
    return InsightExtraction(
        item_id=it.id,
        change_summary=f"{it.title[:200]} — full detail in linked article.",
        significance="Relevant to AI/ML practitioners; visit source for details.",
        novelty_type="update",
        impacted_audience=["ml_engineers"],
        time_sensitivity="medium",
        actionable_insight="Read the full article at the source URL.",
        confidence=0.3,
    )


def parse_utc_dt(value: Any) -> datetime:
    """Parse any datetime-like value to UTC-aware datetime."""
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ── Abstract base class ────────────────────────────────────────────────────────

class BaseSubgraph(ABC):
    """
    Every source subgraph must implement fetch_from_mcp() and normalize().
    The run() method orchestrates: fetch → normalize → fast_fail → llm_enrich → output.
    """

    source: SourceName         # Set in concrete subclass
    budget: int = 10           # Override in subclass
    stale_days: float = 5.0    # Override to change fast-fail threshold

    @abstractmethod
    def fetch_from_mcp(self) -> Dict[str, Any]:
        """Call the relevant MCP endpoint and return the raw JSON response."""
        ...

    @abstractmethod
    def normalize(self, raw_items: List[Dict[str, Any]]) -> List[NormalizedItem]:
        """Convert raw MCP items to NormalizedItems."""
        ...

    def fast_fail(self, normalized: List[NormalizedItem]) -> FastFailBatch:
        """
        Default fast-fail — applies to all subgraphs that don't override.
        Checks (in order):
          1. DROP_STALE  — days_old > stale_days
          2. DROP_EMPTY  — content_for_llm < 20 chars
          3. DROP_NOTITLE — title is missing or < 3 chars
        Override in subclasses to add source-specific rules (e.g. score threshold).
        """
        passed: List[NormalizedItem] = []
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

            if it.days_old > self.stale_days:
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
        return FastFailBatch(
            source=self.source,
            passed=passed,
            dropped=dropped,
            pass_rate=(len(passed) / n) if n else 0.0,
        )

    def run(self) -> SubgraphOutput:
        """Full pipeline: fetch → normalize → fast_fail → llm_enrich → SubgraphOutput."""
        t0 = time.perf_counter()
        all_errors: List[str] = []

        # 1. Fetch
        try:
            raw = self.fetch_from_mcp()
        except Exception as exc:
            logger.error("%s fetch failed: %s", self.source, exc)
            return SubgraphOutput(
                source=self.source, enriched_items=[], total_reviewed=0,
                total_selected=0, fast_fail_dropped=0, llm_dropped=0,
                model_used=LLMProvider.GROQ, processing_ms=0.0, used_fallback=False,
            )

        all_errors.extend(raw.get("errors") or [])
        rows: List[Dict[str, Any]] = list(raw.get("items") or [])
        logger.info("%s: MCP returned %d items", self.source, len(rows))

        # 2. Normalize
        normalized: List[NormalizedItem] = []
        for row in rows:
            try:
                normalized.extend(self.normalize([row]))
            except Exception as exc:
                all_errors.append(f"Normalize error for {row.get('id', '?')}: {exc}")

        # 3. Fast-fail
        ff = self.fast_fail(normalized)

        # 4. LLM enrichment
        enriched: List[EnrichedItem] = []
        provider  = LLMProvider.GROQ
        used_fallback = False

        if ff.passed:
            try:
                enriched, provider, used_fallback, llm_errs = enrich_normalized_items(
                    ff.passed, self.budget, source_name=str(self.source),
                )
                all_errors.extend(llm_errs)
            except Exception as exc:
                logger.error("%s LLM enrichment failed: %s", self.source, exc)
                all_errors.append(f"LLM enrichment failed: {exc}")

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        llm_dropped = max(0, len(ff.passed) - len(enriched))

        logger.info(
            "%s done: %d enriched | %d ff-dropped | %d llm-dropped | %.0fms",
            self.source, len(enriched), len(ff.dropped), llm_dropped, elapsed_ms,
        )

        return SubgraphOutput(
            source=self.source,
            enriched_items=enriched,
            total_reviewed=len(normalized),
            total_selected=len(enriched),
            fast_fail_dropped=len(ff.dropped),
            llm_dropped=llm_dropped,
            model_used=provider,
            processing_ms=elapsed_ms,
            used_fallback=used_fallback,
        )
