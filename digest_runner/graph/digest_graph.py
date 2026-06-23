"""
digest_runner/graph/digest_graph.py
=====================================
Assembles the master LangGraph StateGraph for the AI Daily Digest pipeline.

Graph topology:
    START
      │
    init ──► route_to_sources (conditional edges)
              │  │  │  │  │  │  │
              ▼  ▼  ▼  ▼  ▼  ▼  ▼
            [source_pipeline] × 7  (parallel Send() fan-out)
              │  │  │  │  │  │  │
              ▼  ▼  ▼  ▼  ▼  ▼  ▼
            merger  (fan-in: all branches complete before this runs)
              │
            final_llm
              │
            render
              │
            END

Build the compiled graph with: `build_graph()`
Run the graph with: `build_graph().invoke(initial_state)`
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from digest_runner.graph.state import DigestRunState
from digest_runner.nodes.fetch_node import run_source_pipeline
from digest_runner.nodes.merger_node import merge_subgraph_outputs
from digest_runner.nodes.final_llm_node import run_final_llm
from digest_runner.nodes.render_node import render_digest

logger = logging.getLogger(__name__)

# ── Default sources ────────────────────────────────────────────────────────────
DEFAULT_SOURCES: List[str] = [
    "arxiv",
    "hackernews",
    "github",
    "huggingface",
    # "reddit",  # Disabled: Reddit shut down unauthenticated API access (May 2026)
    "stackoverflow",
    "rss_feeds",
]


# ── Graph nodes ────────────────────────────────────────────────────────────────

def init_node(state: DigestRunState) -> dict:
    """
    Entry node: set run metadata if not already set by the caller.

    The caller (main.py) typically pre-populates run_date, run_id,
    active_sources, etc. in the initial_state dict.
    This node is a no-op pass-through that allows future pre-processing
    (e.g. loading config, validating env vars) without changing the caller.
    """
    updates: dict = {}

    if not state.get("run_date"):
        updates["run_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not state.get("run_id"):
        updates["run_id"] = str(uuid.uuid4())

    if not state.get("active_sources"):
        updates["active_sources"] = DEFAULT_SOURCES

    logger.info(
        "init_node: run_date=%s run_id=%s sources=%s",
        state.get("run_date") or updates.get("run_date"),
        (state.get("run_id") or updates.get("run_id", ""))[:8],
        state.get("active_sources") or updates.get("active_sources"),
    )

    return updates


def route_to_sources(state: DigestRunState) -> List[Send]:
    """
    Conditional edge: fan-out one Send per source to source_pipeline node.

    Each Send delivers a SourceNodeInput dict to the 'source_pipeline' node.
    LangGraph runs all branches in parallel (or pseudo-parallel in sync mode).
    """
    sources = state.get("active_sources") or DEFAULT_SOURCES
    logger.info("route_to_sources: fanning out to %d sources: %s", len(sources), sources)

    return [
        Send("source_pipeline", {"source_name": src})
        for src in sources
    ]


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_graph():
    """
    Build and compile the AI Daily Digest LangGraph pipeline.

    Returns a compiled CompiledGraph ready to call .invoke() or .stream() on.

    Usage:
        graph = build_graph()
        result = graph.invoke({
            "run_date": "2026-06-10",
            "run_id": str(uuid.uuid4()),
            "active_sources": ["arxiv", "hackernews"],
            "subgraph_outputs": [],
            "errors": [],
        })
    """
    # pyrefly: ignore [bad-specialization]
    builder = StateGraph(DigestRunState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("init",            init_node)
    builder.add_node("source_pipeline", run_source_pipeline)   # parallel branches
    builder.add_node("merger",          merge_subgraph_outputs)
    builder.add_node("final_llm",       run_final_llm)
    builder.add_node("render",          render_digest)

    # ── Wire edges ────────────────────────────────────────────────────────────
    builder.add_edge(START, "init")

    # Fan-out: init → route_to_sources → [source_pipeline × N]
    builder.add_conditional_edges(
        "init",
        route_to_sources,
        ["source_pipeline"],  # declares which node(s) the Send() targets
    )

    # Fan-in: all source_pipeline branches merge into merger
    builder.add_edge("source_pipeline", "merger")

    # Sequential tail
    builder.add_edge("merger",    "final_llm")
    builder.add_edge("final_llm", "render")
    builder.add_edge("render",    END)

    compiled = builder.compile()
    logger.info("build_graph: graph compiled successfully")
    return compiled
