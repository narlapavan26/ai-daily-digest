"""
digest_runner/nodes/merger_node.py
====================================
Contains `merge_subgraph_outputs` — a LangGraph node that collects all
SubgraphOutput objects produced by the parallel source_pipeline nodes,
deduplicates items, and prepares the merged list for final_llm_node.

Deduplication strategy (three-pass):
  Pass 1: Exact ID dedup (same item fetched by multiple sources)
  Pass 2: URL-based dedup (same URL from github_release vs rss_feeds)
  Pass 3: Fuzzy title dedup — strips version numbers, repo prefix variants
          → keep item with higher relevance_score
          → if tie, prefer item from higher-priority source

Source priority for tie-breaking:
  github_release > rss_feeds > hackernews > huggingface > reddit
  > arxiv > stackoverflow > github_repo > github_trending
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from digest_runner.graph.state import DigestRunState
from digest_runner.schemas.digest_schemas import (
    DeduplicationResult,
    DuplicatePair,
    EnrichedItem,
    SourceName,
    SubgraphOutput,
)

logger = logging.getLogger(__name__)

# Source priority for tie-breaking when relevance scores are equal
_SOURCE_PRIORITY: Dict[str, int] = {
    SourceName.GITHUB_RELEASE:   10,
    SourceName.RSS_FEEDS:         9,
    SourceName.HACKERNEWS:        8,
    SourceName.HUGGINGFACE:       7,
    SourceName.REDDIT:            6,
    SourceName.ARXIV:             5,
    SourceName.STACKOVERFLOW:     4,
    SourceName.GITHUB_REPO:       3,
    SourceName.SEMANTIC_SCHOLAR:  2,
}

# Version patterns to strip for fuzzy matching
_VERSION_RE = re.compile(
    r"\b(v?\d+\.\d+[\d\.\-\w]*)\b"  # v1.2.3, 1.2.3, 1.2.3-rc1
    r"|\b(b\d{4,})\b"                 # b9619 llama.cpp build tags
    r"|\s*(released|release|version|ver|update|updated|fix|fixed|launched)\s*",
    re.IGNORECASE,
)


def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation and version numbers for fuzzy comparison."""
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)  # replace special chars with space
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _fuzzy_title_key(title: str) -> str:
    """
    Strip version numbers and common noise words to create a fuzzy key.
    'Ollama version v0.30.8 released' and 'Ollama v0.30.8' → 'ollama'
    'langgraph Version 1.2.5 Released' and 'Langgraph version 1.2.5 released' → 'langgraph'
    """
    t = title.lower()
    # Remove version strings and common action words
    t = _VERSION_RE.sub(" ", t)
    # Remove special characters
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Return first 3 meaningful words as key (avoids over-collapsing)
    words = [w for w in t.split() if len(w) > 2]
    return " ".join(words[:3])


def _normalize_url(url) -> str:
    """Strip fragments, trailing slashes, and query params for URL comparison."""
    url = str(url).lower().rstrip("/")
    url = re.sub(r"#.*$", "", url)    # strip fragments
    url = re.sub(r"\?.*$", "", url)   # strip query params
    return url


def _pick_winner(a: EnrichedItem, b: EnrichedItem) -> Tuple[EnrichedItem, EnrichedItem]:
    """Return (winner, loser) based on relevance_score then source priority."""
    if a.relevance_score > b.relevance_score:
        return a, b
    if b.relevance_score > a.relevance_score:
        return b, a
    pri_a = _SOURCE_PRIORITY.get(a.source, 0)
    pri_b = _SOURCE_PRIORITY.get(b.source, 0)
    if pri_a >= pri_b:
        return a, b
    return b, a


def merge_subgraph_outputs(state: DigestRunState) -> dict:
    """
    LangGraph node: collect all SubgraphOutputs and deduplicate.

    Reads:
      state["subgraph_outputs"] — list of SubgraphOutput (one per source)

    Returns:
      {
        "deduplication_result": DeduplicationResult,
        "merged_items": list[EnrichedItem],   # deduplicated, sorted by relevance_score desc
      }
    """
    all_outputs: List[SubgraphOutput] = state.get("subgraph_outputs") or []
    logger.info("merger_node: collecting outputs from %d sources", len(all_outputs))

    # ── Flatten all enriched items ─────────────────────────────────────────────
    all_items: List[EnrichedItem] = []
    for output in all_outputs:
        all_items.extend(output.enriched_items)

    total_before = len(all_items)
    duplicate_pairs: List[DuplicatePair] = []

    # ── Pass 1: deduplicate by exact item ID ──────────────────────────────────
    seen_ids: Dict[str, EnrichedItem] = {}
    after_id_dedup: List[EnrichedItem] = []

    for item in all_items:
        if item.id not in seen_ids:
            seen_ids[item.id] = item
            after_id_dedup.append(item)
        else:
            existing = seen_ids[item.id]
            winner, loser = _pick_winner(existing, item)
            if winner is item:
                seen_ids[item.id] = item
                idx = next(i for i, x in enumerate(after_id_dedup) if x.id == loser.id)
                after_id_dedup[idx] = winner
            duplicate_pairs.append(DuplicatePair(
                kept_id=winner.id, dropped_id=loser.id,
                similarity_score=1.0, merge_strategy="exact_id",
                canonical_id=winner.id,
            ))

    logger.info(
        "merger_node: after ID dedup: %d items (%d dropped)",
        len(after_id_dedup), total_before - len(after_id_dedup),
    )

    # ── Pass 2: deduplicate by normalized URL ─────────────────────────────────
    seen_urls: Dict[str, EnrichedItem] = {}
    after_url_dedup: List[EnrichedItem] = []

    for item in after_id_dedup:
        norm_url = _normalize_url(item.url)
        if not norm_url or norm_url in ("http://", "https://"):
            after_url_dedup.append(item)
            continue
        if norm_url not in seen_urls:
            seen_urls[norm_url] = item
            after_url_dedup.append(item)
        else:
            existing = seen_urls[norm_url]
            winner, loser = _pick_winner(existing, item)
            if winner is item:
                seen_urls[norm_url] = item
                idx = next(i for i, x in enumerate(after_url_dedup) if x.id == loser.id)
                after_url_dedup[idx] = winner
            duplicate_pairs.append(DuplicatePair(
                kept_id=winner.id, dropped_id=loser.id,
                similarity_score=0.98, merge_strategy="url_match",
                canonical_id=winner.id,
            ))
            logger.debug("merger: URL dedup — kept %s, dropped %s (url=%r)", winner.id, loser.id, norm_url)

    logger.info(
        "merger_node: after URL dedup: %d items (%d dropped)",
        len(after_url_dedup), total_before - len(after_url_dedup),
    )

    # ── Pass 3: fuzzy title dedup (strips version numbers) ────────────────────
    seen_fuzzy: Dict[str, EnrichedItem] = {}
    after_fuzzy_dedup: List[EnrichedItem] = []

    for item in after_url_dedup:
        fuzzy_key = _fuzzy_title_key(item.title)
        if not fuzzy_key or len(fuzzy_key) < 3:
            after_fuzzy_dedup.append(item)
            continue
        if fuzzy_key not in seen_fuzzy:
            seen_fuzzy[fuzzy_key] = item
            after_fuzzy_dedup.append(item)
        else:
            existing = seen_fuzzy[fuzzy_key]
            winner, loser = _pick_winner(existing, item)
            if winner is item:
                seen_fuzzy[fuzzy_key] = item
                idx = next(i for i, x in enumerate(after_fuzzy_dedup) if x.id == loser.id)
                after_fuzzy_dedup[idx] = winner
            duplicate_pairs.append(DuplicatePair(
                kept_id=winner.id, dropped_id=loser.id,
                similarity_score=0.85, merge_strategy="fuzzy_title",
                canonical_id=winner.id,
            ))
            logger.debug(
                "merger: fuzzy dedup — kept %s, dropped %s (key=%r)",
                winner.id, loser.id, fuzzy_key,
            )

    # ── Sort by relevance_score descending ────────────────────────────────────
    unique_items = sorted(
        after_fuzzy_dedup,
        key=lambda x: x.relevance_score,
        reverse=True,
    )

    total_after = len(unique_items)
    total_dropped = total_before - total_after

    logger.info(
        "merger_node: final — %d unique items (%d dropped, %d duplicate pairs)",
        total_after, total_dropped, len(duplicate_pairs),
    )

    dedup_result = DeduplicationResult(
        unique_items=unique_items,
        duplicate_pairs=duplicate_pairs,
        total_before=total_before,
        total_after=total_after,
        total_dropped=total_dropped,
    )

    return {
        "deduplication_result": dedup_result,
        "merged_items": unique_items,
    }
