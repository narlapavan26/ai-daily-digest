"""
digest_runner/nodes/final_llm_node.py
=======================================
Contains `run_final_llm` — a LangGraph node that converts merged EnrichedItems
into a fully structured FinalDigestSchema using an LLM call (Groq first,
Gemini fallback).

The LLM's tasks:
  1. Select the top_story (time_sensitivity=HIGH AND highest relevance_score)
  2. Write headline, what_happened, why_it_matters, key_takeaway for each item
  3. Generate 2-5 topic tags per item
  4. Produce optional action_hint for releases and model drops
  5. Group items into DigestSection objects
  6. Optionally write section_summary for sections with 3+ items

Fallback behaviour:
  If LLM fails entirely, a deterministic fallback directly maps
  EnrichedItem → FinalDigestItem using existing insight fields.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel as PydanticBase

from digest_runner.graph.state import DigestRunState
from digest_runner.schemas.digest_schemas import (
    DigestMetadata,
    DigestSection,
    DigestSectionName,
    EnrichedItem,
    FinalDigestItem,
    FinalDigestSchema,
    LLMProvider,
    NoveltyType,
    SourceName,
    TimeSensitivity,
)
from digest_runner.subgraphs.base import (
    GROQ_MODEL,
    GEMINI_MODEL,
    get_instructor_client,
)

logger = logging.getLogger(__name__)

MAX_ITEMS_FOR_LLM = 60   # Don't send more than this to final LLM in one call
BATCH_SIZE = 20          # Items per LLM batch

# Section ordering — deterministic
SECTION_ORDER = [
    DigestSectionName.FRAMEWORK_RELEASES,
    DigestSectionName.MODEL_RELEASES,
    DigestSectionName.NEW_TOOLS,
    DigestSectionName.RESEARCH,
    DigestSectionName.INFRASTRUCTURE,
    DigestSectionName.COMMUNITY_BUZZ,
    DigestSectionName.QUICK_LINKS,
]

SECTION_DISPLAY = {
    DigestSectionName.FRAMEWORK_RELEASES: ("🚀 Framework Releases", "🚀"),
    DigestSectionName.MODEL_RELEASES:     ("🧠 Model Releases",    "🧠"),
    DigestSectionName.NEW_TOOLS:          ("🔧 New Tools",         "🔧"),
    DigestSectionName.RESEARCH:           ("📄 Research Worth Noting", "📄"),
    DigestSectionName.INFRASTRUCTURE:     ("⚙️ Infrastructure",    "⚙️"),
    DigestSectionName.COMMUNITY_BUZZ:     ("💬 Community Buzz",    "💬"),
    DigestSectionName.QUICK_LINKS:        ("🔗 Quick Links",       "🔗"),
    DigestSectionName.TOP_STORY:          ("🔥 Top Story",         "🔥"),
}


# ── Inner Pydantic model for instructor-enforced LLM output ───────────────────

from pydantic import model_validator

class _FinalItemLLM(PydanticBase):
    """Instructor-enforced output for one digest item.
    Includes a model_validator to handle free-tier LLMs that omit item_id
    or other required fields (the #1 source of Pydantic validation crashes).
    """
    item_id: str = ""
    headline: str = ""
    what_happened: str = ""
    why_it_matters: str = ""
    key_takeaway: str = ""
    action_hint: Optional[str] = None
    tags: List[str] = []

    @model_validator(mode="before")
    @classmethod
    def _fix_fields(cls, data: Any) -> Any:
        """Auto-fix common LLM output issues to prevent validation crashes."""
        if isinstance(data, dict):
            # LLMs often return 'id' instead of 'item_id'
            if "item_id" not in data and "id" in data:
                data["item_id"] = data.pop("id")
            # Provide defaults for any missing string fields
            if not data.get("item_id"):
                data["item_id"] = "unknown"
            if not data.get("headline"):
                data["headline"] = data.get("what_happened", "Untitled digest item")[:120]
            if not data.get("what_happened"):
                data["what_happened"] = data.get("headline", "No details available.")
            if not data.get("why_it_matters"):
                data["why_it_matters"] = "Relevant to AI/ML practitioners."
            if not data.get("key_takeaway"):
                data["key_takeaway"] = data.get("headline", "See the linked resource for details.")
        return data


class _FinalBatchLLM(PydanticBase):
    """Instructor-enforced batch output."""
    items: List[_FinalItemLLM] = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_top_story(items: List[EnrichedItem]) -> Optional[EnrichedItem]:
    """
    Select the top story: time_sensitivity=HIGH AND highest relevance_score.
    Prefer items with novelty_type in [NEW_RELEASE, MODEL_DROP, BREAKTHROUGH, TOOL_LAUNCH].
    """
    priority_types = {
        NoveltyType.NEW_RELEASE, NoveltyType.MODEL_DROP,
        NoveltyType.BREAKTHROUGH, NoveltyType.TOOL_LAUNCH,
        NoveltyType.NEW_FEATURE, NoveltyType.ANNOUNCEMENT,
        NoveltyType.NEW_SERVICE,
    }

    high_sens = [
        it for it in items
        if it.time_sensitivity == TimeSensitivity.HIGH
    ]

    if not high_sens:
        # Fall back to highest relevance_score overall
        candidates = sorted(items, key=lambda x: x.relevance_score, reverse=True)
        return candidates[0] if candidates else None

    # Among HIGH sensitivity, prefer priority novelty types
    priority = [it for it in high_sens if it.novelty_type in priority_types]
    pool = priority if priority else high_sens
    return max(pool, key=lambda x: x.relevance_score)


def _build_llm_prompt(items: List[EnrichedItem]) -> str:
    """Build the user prompt listing all items for the final LLM to rewrite."""
    lines = [
        f"Rewrite the following {len(items)} items for the AI/ML Daily Digest.\n",
        "For each item produce: headline, what_happened, why_it_matters, key_takeaway,",
        "optional action_hint (only for releases/model drops), and 2-5 lowercase tags.\n",
        "Rules:",
        "  - headline: factual, active voice, no 'Introducing' or 'Announcing'",
        "  - what_happened: past tense, factual (2-3 sentences max)",
        "  - why_it_matters: start with consequence phrase like 'This means...'",
        "  - key_takeaway: single most important sentence, readable standalone",
        "  - tags: short, specific, e.g. ['langchain', 'release', 'memory']\n",
        "Items:\n",
    ]

    for i, it in enumerate(items, 1):
        lines.append(
            f"[{i}] item_id={it.id}\n"
            f"    Title: {it.title}\n"
            f"    Source: {it.source}\n"
            f"    Change: {it.change_summary}\n"
            f"    Significance: {it.significance}\n"
            f"    Actionable: {it.actionable_insight}\n"
            f"    Time sensitivity: {it.time_sensitivity}\n"
        )
    return "\n".join(lines)


_FINAL_SYSTEM_PROMPT = (
    "You are a senior technical writer for an AI/ML newsletter aimed at ML engineers "
    "and AI practitioners. Rewrite digest items in clear, engaging, opinionated prose. "
    "Be concise but insightful. Never use hype words like 'revolutionary', 'game-changing', "
    "'exciting', 'groundbreaking'. Write for a reader who reads code every day. "
    "Additional constraints: "
    "action_hint must be a concrete action (upgrade command, API to try, paper to implement) "
    "— NOT 'Read the full article' or 'Try out the new release'. "
    "what_happened must name the specific framework/tool/model, not say 'The model' or 'The framework'. "
    "If you cannot extract real substance from an item, set action_hint to null."
)


def _call_llm_batch(
    items: List[EnrichedItem],
    client: Any,
    model: str,
    provider_enum: Any = None,
) -> Dict[str, _FinalItemLLM]:
    """Call the LLM for one batch of items, returning {item_id: LLM output}."""
    from digest_runner.utils.provider_pool import ProviderPool

    prompt = _build_llm_prompt(items)

    if provider_enum is not None:
        ProviderPool.acquire(provider_enum)
    try:
        result: _FinalBatchLLM = client.chat.completions.create(
            model=model,
            response_model=_FinalBatchLLM,
            max_retries=0,  # ProviderPool handles rotation; instructor retries waste quota
            messages=[
                {"role": "system", "content": _FINAL_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
        )
    finally:
        if provider_enum is not None:
            ProviderPool.release()

    return {llm_item.item_id: llm_item for llm_item in result.items}


def _fallback_digest_item(item: EnrichedItem) -> FinalDigestItem:
    """
    Direct mapping from EnrichedItem -> FinalDigestItem when LLM fails.
    Uses existing insight fields without further LLM rewriting.
    """
    src_val = item.source.value if hasattr(item.source, 'value') else str(item.source)
    nov_val = item.novelty_type.value if hasattr(item.novelty_type, 'value') else str(item.novelty_type)
    tags = [src_val, nov_val]
    tags = list(dict.fromkeys(tags))[:5]  # deduplicate

    # Guard: headline must be >= 10 chars (FinalDigestItem constraint)
    raw_headline = (item.title or "").strip()
    if len(raw_headline) < 10:
        raw_headline = f"{raw_headline} ({src_val} item)".strip()
    if len(raw_headline) < 10:
        raw_headline = f"[{src_val}] Digest item {item.id[:8]}"
    headline = raw_headline[:120]

    # Guard: what_happened / why_it_matters / key_takeaway must be non-empty
    what_happened  = (item.change_summary or item.title or headline)[:400]
    why_it_matters = (item.significance or "Relevant to AI/ML practitioners.")[:400]
    key_takeaway   = (item.actionable_insight or "Read the full article at the source URL.")[:160]

    return FinalDigestItem(
        id=item.id,
        source=item.source,
        novelty_type=item.novelty_type,
        section=item.digest_section,
        url=item.url,
        published_at=item.published_at,
        tags=tags,
        headline=headline,
        what_happened=what_happened,
        why_it_matters=why_it_matters,
        key_takeaway=key_takeaway,
        action_hint=key_takeaway if item.time_sensitivity == TimeSensitivity.HIGH else None,
        time_sensitivity=item.time_sensitivity,
        confidence_score=item.confidence,
    )


def _enriched_to_final(
    item: EnrichedItem,
    llm_data: Optional[_FinalItemLLM],
) -> FinalDigestItem:
    """Merge LLM output with EnrichedItem metadata to build FinalDigestItem."""
    if llm_data is None:
        return _fallback_digest_item(item)

    tags = [t.lower().strip() for t in (llm_data.tags or []) if t.strip()]
    if not tags:
        src_val = item.source.value if hasattr(item.source, 'value') else str(item.source)
        nov_val = item.novelty_type.value if hasattr(item.novelty_type, 'value') else str(item.novelty_type)
        tags = [src_val, nov_val]
    tags = list(dict.fromkeys(tags))[:5]

    # Guard: headline must be >= 10 chars
    raw_headline = (llm_data.headline or "").strip()
    if len(raw_headline) < 10:
        raw_headline = (item.title or raw_headline or "Digest item")[:120]
    if len(raw_headline) < 10:
        src_val = item.source.value if hasattr(item.source, 'value') else str(item.source)
        raw_headline = f"[{src_val}] {raw_headline or item.id[:8]}"
    headline = raw_headline[:120]

    # Guard: what_happened / why_it_matters / key_takeaway must meet min_length
    what_happened = (llm_data.what_happened or "").strip()[:400]
    if len(what_happened) < 20:
        what_happened = (item.change_summary or item.title or headline)[:400]
    if len(what_happened) < 20:
        what_happened = f"{headline} — details at the source URL."

    why_it_matters = (llm_data.why_it_matters or "").strip()[:400]
    if len(why_it_matters) < 20:
        why_it_matters = (item.significance or "Relevant to AI/ML practitioners building with these frameworks.")[:400]

    key_takeaway = (llm_data.key_takeaway or "").strip()[:160]
    if len(key_takeaway) < 15:
        key_takeaway = (item.actionable_insight or "Read the full article at the source URL.")[:160]

    return FinalDigestItem(
        id=item.id,
        source=item.source,
        novelty_type=item.novelty_type,
        section=item.digest_section,
        url=item.url,
        published_at=item.published_at,
        tags=tags,
        headline=headline,
        what_happened=what_happened,
        why_it_matters=why_it_matters,
        key_takeaway=key_takeaway,
        action_hint=(llm_data.action_hint[:200] if llm_data.action_hint else None),
        time_sensitivity=item.time_sensitivity,
        confidence_score=item.confidence,
    )


# ── Main LangGraph node ────────────────────────────────────────────────────────

def run_final_llm(state: DigestRunState) -> dict:
    """
    LangGraph node: convert merged EnrichedItems into FinalDigestSchema.

    Reads:
      state["merged_items"]   — list[EnrichedItem] from merger_node
      state["subgraph_outputs"] — for metadata (total_reviewed, sources, etc.)
      state["run_date"]

    Returns:
      { "final_digest": FinalDigestSchema }
    """
    merged_items: List[EnrichedItem] = state.get("merged_items") or []
    subgraph_outputs = state.get("subgraph_outputs") or []
    run_date = state.get("run_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info("final_llm_node: processing %d merged items", len(merged_items))

    if not merged_items:
        logger.warning("final_llm_node: no merged items — producing empty digest")

    # ── Select top story ──────────────────────────────────────────────────────
    top_story_enriched: Optional[EnrichedItem] = _pick_top_story(merged_items)
    top_story_id: Optional[str] = top_story_enriched.id if top_story_enriched else None

    items_for_llm = merged_items[:MAX_ITEMS_FOR_LLM]

    # ── Call LLM via ProviderPool (auto-rotates on 429/quota errors) ──────────
    llm_map: Dict[str, _FinalItemLLM] = {}
    provider_used = LLMProvider.GROQ
    used_fallback = False
    errors: list[str] = []

    from digest_runner.utils.provider_pool import ProviderPool, is_rate_limit_error, is_provider_broken
    try:
        client, model, provider_used = ProviderPool.get_client()
        logger.info("final_llm_node: using provider=%s model=%s", provider_used.value, model)
    except RuntimeError as exc:
        errors.append(f"All providers unavailable at final_llm: {exc}")
        client, model = None, None

    if client is not None and items_for_llm:
        for start in range(0, len(items_for_llm), BATCH_SIZE):
            if start > 0:
                time.sleep(1.0)  # Minimal delay; ProviderPool.acquire() handles rate pacing
            batch = items_for_llm[start: start + BATCH_SIZE]
            try:
                batch_result = _call_llm_batch(batch, client, model, provider_enum=provider_used)
                llm_map.update(batch_result)
                ProviderPool.mark_success(provider_used)
            except Exception as exc:
                errors.append(f"final_llm batch[{start}] {provider_used.value} failed: {exc}")
                if is_provider_broken(exc):
                    ProviderPool.mark_rate_limited(provider_used, cooldown_secs=600)
                elif is_rate_limit_error(exc):
                    ProviderPool.mark_rate_limited(provider_used)
                # Rotate to next provider
                try:
                    client, model, provider_used = ProviderPool.get_client()
                    used_fallback = True
                    logger.info("final_llm_node: switched to %s for batch %d", provider_used.value, start)
                    batch_result = _call_llm_batch(batch, client, model, provider_enum=provider_used)
                    llm_map.update(batch_result)
                    ProviderPool.mark_success(provider_used)
                except Exception as exc2:
                    errors.append(f"final_llm batch[{start}] fallback also failed: {exc2}")

    # ── Build FinalDigestItems ────────────────────────────────────────────────
    final_items: Dict[str, FinalDigestItem] = {}
    for item in merged_items:
        final_item = _enriched_to_final(item, llm_map.get(item.id))
        final_items[item.id] = final_item

    # ── Build top_story FinalDigestItem ──────────────────────────────────────
    top_story_final: Optional[FinalDigestItem] = (
        final_items.get(top_story_id) if top_story_id else None
    )

    # ── Group into sections ───────────────────────────────────────────────────
    section_map: Dict[DigestSectionName, List[FinalDigestItem]] = defaultdict(list)
    quick_links: List[FinalDigestItem] = []

    for item_id, fdi in final_items.items():
        if item_id != top_story_id:
            section_map[fdi.section].append(fdi)
            quick_links.append(fdi)

    # Build ordered sections (skip empty ones)
    sections: List[DigestSection] = []
    for sec_name in SECTION_ORDER:
        if sec_name == DigestSectionName.QUICK_LINKS:
            continue
        items_in_section = section_map.get(sec_name, [])
        if not items_in_section:
            continue
        display_title, emoji = SECTION_DISPLAY.get(sec_name, (sec_name.value, ""))
        section_summary: Optional[str] = None
        if len(items_in_section) >= 3:
            # pyrefly: ignore [unnecessary-type-conversion]
            themes = ", ".join({str(it.tags[0]) for it in items_in_section if it.tags})[:200]
            if themes:
                section_summary = f"{len(items_in_section)} items covering: {themes}."

        sections.append(DigestSection(
            section=sec_name,
            title=display_title,
            emoji=emoji,
            items=items_in_section,
            item_count=len(items_in_section),
            section_summary=section_summary,
        ))

    # ── Build metadata ────────────────────────────────────────────────────────
    total_raw = sum(o.total_reviewed for o in subgraph_outputs)
    sources_reviewed = list({o.source for o in subgraph_outputs})
    providers_used = list({o.model_used for o in subgraph_outputs})
    if provider_used not in providers_used:
        providers_used.append(provider_used)

    source_counts: Dict[str, Dict[str, int]] = {}
    for o in subgraph_outputs:
        src_key = o.source.value if hasattr(o.source, 'value') else str(o.source)
        source_counts[src_key] = {
            "raw":      o.total_reviewed,
            "selected": o.total_selected,
            "dropped":  o.fast_fail_dropped + o.llm_dropped,
        }

    metadata = DigestMetadata(
        digest_date=run_date,
        total_raw_items=total_raw,
        total_selected=len(final_items),
        sources_reviewed=sources_reviewed,
        providers_used=providers_used,
        source_counts=source_counts,
    )

    final_digest = FinalDigestSchema(
        metadata=metadata,
        top_story=top_story_final,
        sections=sections,
        quick_links=quick_links,
    )

    logger.info(
        "final_llm_node: produced digest with %d sections, %d quick links, top_story=%s",
        len(sections), len(quick_links),
        top_story_final.headline[:60] if top_story_final else "None",
    )

    return {
        "final_digest": final_digest,
        "errors": errors,
    }
