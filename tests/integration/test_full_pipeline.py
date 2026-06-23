"""
tests/integration/test_full_pipeline.py
=========================================
Integration test: runs the full LangGraph pipeline with source=["arxiv"].

REQUIRES:
  - MCP server running (MCP_BASE_URL env var set, e.g. http://127.0.0.1:8000)
  - GROQ_API_KEY or GEMINI_API_KEY env var set
  - conda env 'ai' activated (or dependencies installed)

Skip conditions:
  - If MCP_BASE_URL is not set, all tests in this module are skipped.

Usage:
    conda run -n ai pytest tests/integration/test_full_pipeline.py -v
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("MCP_BASE_URL"),
    reason="MCP_BASE_URL not set — skipping integration tests (start MCP server first)",
)


@pytest.fixture(scope="module")
def built_graph():
    """Build the digest graph once per module (expensive)."""
    from digest_runner.graph.digest_graph import build_graph
    return build_graph()


@pytest.fixture(scope="module")
def arxiv_result(built_graph):
    """
    Run the full pipeline with arxiv source only.
    Budget is low (max 3 papers) so LLM cost is minimal.
    """
    initial_state = {
        "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "run_id": str(uuid.uuid4()),
        "active_sources": ["arxiv"],
        "subgraph_outputs": [],
        "errors": [],
    }
    return built_graph.invoke(initial_state)


class TestFullPipelineStructure:
    def test_result_is_dict(self, arxiv_result):
        assert isinstance(arxiv_result, dict)

    def test_subgraph_outputs_present(self, arxiv_result):
        assert "subgraph_outputs" in arxiv_result
        assert isinstance(arxiv_result["subgraph_outputs"], list)

    def test_exactly_one_subgraph_output(self, arxiv_result):
        assert len(arxiv_result["subgraph_outputs"]) == 1

    def test_subgraph_output_source(self, arxiv_result):
        from digest_runner.schemas.digest_schemas import SourceName
        output = arxiv_result["subgraph_outputs"][0]
        assert output.source == SourceName.ARXIV

    def test_total_reviewed_non_negative(self, arxiv_result):
        output = arxiv_result["subgraph_outputs"][0]
        assert output.total_reviewed >= 0

    def test_enriched_items_is_list(self, arxiv_result):
        output = arxiv_result["subgraph_outputs"][0]
        assert isinstance(output.enriched_items, list)

    def test_merged_items_present(self, arxiv_result):
        assert "merged_items" in arxiv_result
        assert isinstance(arxiv_result["merged_items"], list)

    def test_pipeline_completed(self, arxiv_result):
        assert "output_path" in arxiv_result or "final_digest" in arxiv_result

    def test_errors_is_list(self, arxiv_result):
        errors = arxiv_result.get("errors") or []
        assert isinstance(errors, list)


class TestSubgraphOutputSchema:
    def test_output_has_processing_ms(self, arxiv_result):
        output = arxiv_result["subgraph_outputs"][0]
        assert output.processing_ms >= 0.0

    def test_output_has_model_used(self, arxiv_result):
        from digest_runner.schemas.digest_schemas import LLMProvider
        output = arxiv_result["subgraph_outputs"][0]
        assert output.model_used in list(LLMProvider)

    def test_enriched_items_schema(self, arxiv_result):
        output = arxiv_result["subgraph_outputs"][0]
        for item in output.enriched_items:
            assert item.id
            assert item.title
            assert str(item.url).startswith("http")
            assert 0.0 <= item.relevance_score <= 1.0
            assert item.change_summary
            assert item.significance


class TestLLMEnrichment:
    @pytest.mark.skipif(
        not os.environ.get("GROQ_API_KEY") and not os.environ.get("GEMINI_API_KEY"),
        reason="No LLM API keys — skipping enrichment assertions",
    )
    def test_enriched_items_non_negative(self, arxiv_result):
        output = arxiv_result["subgraph_outputs"][0]
        assert output.total_selected >= 0

    def test_final_digest_produced_if_items_exist(self, arxiv_result):
        if arxiv_result.get("merged_items"):
            assert arxiv_result.get("final_digest") is not None

    def test_output_path_set_if_render_ran(self, arxiv_result):
        output_path = arxiv_result.get("output_path")
        if output_path:
            assert os.path.exists(output_path)
            assert output_path.endswith(".md")
