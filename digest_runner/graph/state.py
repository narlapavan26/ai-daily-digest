"""
digest_runner/graph/state.py
============================
LangGraph state definition for the AI Daily Digest pipeline.

Uses TypedDict with Annotated reducers so parallel Send() fan-out
can safely write to the same state key from multiple concurrent nodes.
"""
from __future__ import annotations

import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict

from digest_runner.schemas.digest_schemas import (
    SubgraphOutput,
    EnrichedItem,
    FinalDigestSchema,
    DeduplicationResult,
    LLMMetrics,
    PublishStatus,
)


class SourceNodeInput(TypedDict):
    """Input sent to each parallel source_pipeline node via Send()."""
    source_name: str  # e.g. "arxiv", "hackernews", etc.


class DigestRunState(TypedDict, total=False):
    """
    Master LangGraph state.
    subgraph_outputs uses operator.add reducer so parallel branches
    each append their SubgraphOutput without overwriting each other.
    """
    run_date: str        # "YYYY-MM-DD"
    run_id: str          # UUID
    active_sources: list[str]  # source names to process

    # Parallel fan-out results — each source appends to this list
    subgraph_outputs: Annotated[list[SubgraphOutput], operator.add]

    # After merger
    deduplication_result: Optional[DeduplicationResult]
    merged_items: list[EnrichedItem]

    # After final LLM
    final_digest: Optional[FinalDigestSchema]

    # After render
    output_path: str  # path to saved Markdown file

    # Telemetry
    errors: Annotated[list[str], operator.add]
    llm_metrics: Optional[LLMMetrics]
    publish_status: Optional[str]
