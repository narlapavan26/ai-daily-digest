"""
digest_runner/nodes/fast_fail_node.py
======================================
Contains `apply_fast_fail` — a pure helper function used by `run_source_pipeline`
in fetch_node.py. It delegates to the subgraph's fast_fail() method.

NOT a LangGraph node directly. Called as step 3 of the 4-step pipeline inside
run_source_pipeline after normalize_items().

Fast-fail rules (enforced in BaseSubgraph.fast_fail() and subclass overrides):
  arxiv            → days_old > 7  → DROP_STALE
  github_release   → never drop (always fresh by definition)
  github_repo      → days_old > 3  → DROP_STALE
  hackernews       → points < 10   → DROP_LOWSIG
  huggingface      → downloads < 100 → DROP_LOWSIG
  stackoverflow    → score < 3     → DROP_LOWSIG
  rss_feeds        → days_old > 5  → DROP_STALE
"""
from __future__ import annotations

import logging
from typing import List

from digest_runner.schemas.digest_schemas import FastFailBatch, NormalizedItem
from digest_runner.subgraphs.base import BaseSubgraph

logger = logging.getLogger(__name__)


def apply_fast_fail(
    normalized: List[NormalizedItem],
    subgraph: BaseSubgraph,
) -> FastFailBatch:
    """
    Apply source-specific fast-fail filtering to a list of NormalizedItems.

    Used by run_source_pipeline in fetch_node.py as step 3 of the pipeline.

    Args:
        normalized:  List of NormalizedItem objects from normalize_items().
        subgraph:    The instantiated source subgraph. Its fast_fail() method
                     applies source-specific drop rules (staleness, low signal, etc.)

    Returns:
        FastFailBatch with:
          - passed:     items that survived filtering → go to LLM enrichment
          - dropped:    items dropped with verdict + reason
          - pass_rate:  fraction that survived (0.0–1.0)
    """
    if not normalized:
        logger.debug("apply_fast_fail: no items to filter for source=%s", subgraph.source)
        return FastFailBatch(
            source=subgraph.source,
            passed=[],
            dropped=[],
            pass_rate=0.0,
        )

    batch: FastFailBatch = subgraph.fast_fail(normalized)

    logger.info(
        "apply_fast_fail: %s — %d/%d passed (%.0f%% pass rate), %d dropped",
        subgraph.source,
        len(batch.passed),
        len(normalized),
        batch.pass_rate * 100,
        len(batch.dropped),
    )

    return batch
