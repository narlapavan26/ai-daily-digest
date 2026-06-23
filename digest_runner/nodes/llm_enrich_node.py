"""
digest_runner/nodes/llm_enrich_node.py
========================================
Contains `enrich_items` — a thin wrapper around `enrich_normalized_items`
from digest_runner/subgraphs/base.py.

Used by run_source_pipeline in fetch_node.py as step 4 of the 4-step pipeline.
NOT a LangGraph node directly; called inside the source_pipeline node.

LLM enrichment strategy:
  1. Step 1: Relevance screening via Groq (llama-3.3-70b-versatile)
  2. Step 2: Insight extraction for relevant items via Groq
  3. If Groq fails: fallback to Gemini (gemini-2.0-flash-exp)
  4. Budget enforced: only top-N enriched items returned per source
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from digest_runner.schemas.digest_schemas import EnrichedItem, LLMProvider, NormalizedItem
from digest_runner.subgraphs.base import enrich_normalized_items

logger = logging.getLogger(__name__)


def enrich_items(
    passed_items: List[NormalizedItem],
    budget: int,
    source_name: str,
) -> Tuple[List[EnrichedItem], LLMProvider, bool, List[str]]:
    """
    Thin wrapper around enrich_normalized_items from subgraphs/base.py.

    Runs the 2-step LLM enrichment pipeline for a list of NormalizedItems
    that have passed the fast-fail filter:
      1. Relevance screening (batched, BATCH_SIZE=8)
      2. Insight extraction for relevant items (batched)

    Args:
        passed_items: NormalizedItems that passed fast_fail filtering.
        budget:       Maximum number of EnrichedItems to produce.
                      Each subgraph has its own budget (arxiv=5, rss=25, etc.)
        source_name:  Human-readable source label used in LLM prompts and logs.

    Returns:
        (enriched_items, provider_used, used_fallback, errors)
        - enriched_items: List[EnrichedItem] up to `budget` items
        - provider_used:  LLMProvider.GROQ or LLMProvider.GEMINI
        - used_fallback:  True if Gemini was used as fallback
        - errors:         List of error strings (non-fatal)
    """
    if not passed_items:
        logger.debug("enrich_items: no items to enrich for source=%s", source_name)
        return [], LLMProvider.GROQ, False, []

    logger.info(
        "enrich_items: enriching %d items for source=%s (budget=%d)",
        len(passed_items), source_name, budget,
    )

    enriched, provider, used_fallback, errors = enrich_normalized_items(
        passed=passed_items,
        budget=budget,
        source_name=source_name,
    )

    logger.info(
        "enrich_items: %s — %d/%d items enriched via %s%s",
        source_name,
        len(enriched),
        len(passed_items),
        provider,
        " (fallback)" if used_fallback else "",
    )

    if errors:
        logger.warning("enrich_items: %s — %d errors: %s", source_name, len(errors), errors[:3])

    return enriched, provider, used_fallback, errors
