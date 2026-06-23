"""
digest_runner/nodes/normalize_node.py
======================================
Contains `normalize_items` — a pure helper function used by `run_source_pipeline`
in fetch_node.py. It delegates to the subgraph's own normalize() method.

NOT a LangGraph node directly. Called as part of the 4-step pipeline inside
run_source_pipeline. The actual normalization logic is source-specific and lives
in each subgraph's normalize() override.

Design rationale:
  Keeping normalization as a separate importable function allows unit tests to
  validate the mapping logic without running the full subgraph.run() pipeline.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from digest_runner.schemas.digest_schemas import NormalizedItem
from digest_runner.subgraphs.base import BaseSubgraph

logger = logging.getLogger(__name__)


def normalize_items(
    raw_items: List[Dict[str, Any]],
    subgraph: BaseSubgraph,
) -> List[NormalizedItem]:
    """
    Convert a list of raw MCP-fetched dicts into NormalizedItems using
    the given subgraph's normalize() method.

    Used by run_source_pipeline in fetch_node.py as step 2 of the pipeline.

    Args:
        raw_items: List of raw item dicts returned by fetch_from_mcp().
                   Shape varies per source (see RawArxivItem, RawRSSEntry, etc.)
        subgraph:  The instantiated source subgraph (ArxivSubgraph, RssSubgraph, …).
                   Its normalize() method handles source-specific field mapping.

    Returns:
        List of NormalizedItem objects. Items that fail validation are logged
        as warnings and skipped (not raised) to keep the pipeline robust.
    """
    normalized: List[NormalizedItem] = []
    skipped = 0

    for raw in raw_items:
        try:
            items = subgraph.normalize([raw])
            normalized.extend(items)
        except Exception as exc:
            item_id = raw.get("id", raw.get("title", "?"))
            logger.warning(
                "normalize_items: skipping item id=%r source=%s — %s",
                item_id, subgraph.source, exc,
            )
            skipped += 1

    if skipped:
        logger.info(
            "normalize_items: %s — %d/%d items normalized, %d skipped",
            subgraph.source, len(normalized), len(raw_items), skipped,
        )
    return normalized
