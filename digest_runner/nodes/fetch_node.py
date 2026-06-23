"""
digest_runner/nodes/fetch_node.py
=================================
Contains `run_source_pipeline` — the main LangGraph node function for the
parallel source_pipeline. Each Send() message dispatches here with one
source_name. This calls the appropriate subgraph.run() to execute the full
4-step pipeline (fetch → normalize → fast_fail → llm_enrich).

The node returns a partial DigestRunState update appending to subgraph_outputs.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict

from digest_runner.graph.state import SourceNodeInput, DigestRunState
from digest_runner.schemas.digest_schemas import SubgraphOutput, LLMProvider
from digest_runner.subgraphs.base import BaseSubgraph

logger = logging.getLogger(__name__)

# ── Lazy subgraph factory map ──────────────────────────────────────────────────
# Lambdas prevent import-time instantiation (avoids MCP connections on import).

def _get_subgraph_map() -> Dict[str, Callable[[], BaseSubgraph]]:
    """Build the source→subgraph factory mapping.
    Defined as a function to allow deferred imports and avoid circular refs.
    """
    from digest_runner.subgraphs.arxiv_subgraph import ArxivSubgraph
    from digest_runner.subgraphs.hackernews_subgraph import HackerNewsSubgraph
    from digest_runner.subgraphs.github_subgraph import GithubSubgraph
    from digest_runner.subgraphs.huggingface_subgraph import HuggingFaceSubgraph
    from digest_runner.subgraphs.reddit_subgraph import RedditSubgraph
    from digest_runner.subgraphs.stackoverflow_subgraph import StackOverflowSubgraph
    from digest_runner.subgraphs.rss_subgraph import RssSubgraph

    return {
        "arxiv":         lambda: ArxivSubgraph(),
        "hackernews":    lambda: HackerNewsSubgraph(),
        "github":        lambda: GithubSubgraph(),
        "huggingface":   lambda: HuggingFaceSubgraph(),
        "reddit":        lambda: RedditSubgraph(),
        "stackoverflow": lambda: StackOverflowSubgraph(),
        "rss_feeds":     lambda: RssSubgraph(),
    }


def get_subgraph(source_name: str) -> BaseSubgraph:
    """
    Return an instantiated subgraph for the given source_name.
    Raises ValueError for unknown sources.
    """
    subgraph_map = _get_subgraph_map()
    factory = subgraph_map.get(source_name)
    if factory is None:
        raise ValueError(
            f"Unknown source '{source_name}'. "
            f"Valid sources: {sorted(subgraph_map.keys())}"
        )
    return factory()


def run_source_pipeline(state: SourceNodeInput) -> dict:
    """
    LangGraph node: execute the full 4-step pipeline for ONE source.

    Called once per source via Send() fan-out from init_node.
    Each invocation is independent and can run in parallel.

    Steps (delegated to subgraph.run()):
      1. fetch_from_mcp()  — call MCP HTTP endpoint
      2. normalize()       — source-specific → NormalizedItem
      3. fast_fail()       — cheap rule-based drop
      4. enrich_normalized_items() — LLM relevance + insight

    Returns a dict with:
      - subgraph_outputs: [SubgraphOutput]  (appended via operator.add reducer)
      - errors: [str]                        (appended via operator.add reducer)
    """
    source_name: str = state["source_name"]
    logger.info("source_pipeline starting: source=%s", source_name)

    errors: list[str] = []

    try:
        subgraph = get_subgraph(source_name)
    except ValueError as exc:
        logger.error("Unknown source %r: %s", source_name, exc)
        errors.append(f"[{source_name}] Unknown source: {exc}")
        # Return an empty output so the graph can continue
        # Source must be a valid SourceName enum value — use ARXIV as placeholder
        from digest_runner.schemas.digest_schemas import SourceName as _SN
        empty_output = SubgraphOutput(
            source=_SN.ARXIV,  # placeholder; real source unknown/invalid
            enriched_items=[],
            total_reviewed=0,
            total_selected=0,
            fast_fail_dropped=0,
            llm_dropped=0,
            model_used=LLMProvider.GROQ,
            processing_ms=0.0,
        )
        return {"subgraph_outputs": [empty_output], "errors": errors}

    try:
        output: SubgraphOutput = subgraph.run()
        logger.info(
            "source_pipeline done: source=%s enriched=%d reviewed=%d",
            source_name, output.total_selected, output.total_reviewed,
        )
    except Exception as exc:
        logger.exception("source_pipeline failed for %s: %s", source_name, exc)
        errors.append(f"[{source_name}] Pipeline failed: {exc}")
        output = SubgraphOutput(
            source=subgraph.source,
            enriched_items=[],
            total_reviewed=0,
            total_selected=0,
            fast_fail_dropped=0,
            llm_dropped=0,
            model_used=LLMProvider.GROQ,
            processing_ms=0.0,
        )

    return {
        "subgraph_outputs": [output],
        "errors": errors,
    }
