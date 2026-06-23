"""
tests/unit/test_fetch_node.py
================================
Tests for run_source_pipeline() and get_subgraph() in
digest_runner/nodes/fetch_node.py.

MCP-dependent tests are marked with pytestmark_mcp and
skipped automatically when MCP_BASE_URL env var is not set.
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch

from digest_runner.nodes.fetch_node import get_subgraph, run_source_pipeline
from digest_runner.schemas.digest_schemas import LLMProvider, SourceName, SubgraphOutput


class TestGetSubgraph:
    @pytest.mark.parametrize("source_name", [
        "arxiv", "hackernews", "github", "huggingface",
        "reddit", "stackoverflow", "rss_feeds",
    ])
    def test_known_sources_return_subgraph(self, source_name):
        """All 7 known sources should return a BaseSubgraph instance."""
        subgraph = get_subgraph(source_name)
        assert subgraph is not None
        from digest_runner.subgraphs.base import BaseSubgraph
        assert isinstance(subgraph, BaseSubgraph)

    def test_unknown_source_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown source"):
            get_subgraph("nonexistent_source")

    def test_arxiv_returns_arxiv_subgraph(self):
        from digest_runner.subgraphs.arxiv_subgraph import ArxivSubgraph
        subgraph = get_subgraph("arxiv")
        assert isinstance(subgraph, ArxivSubgraph)

    def test_rss_returns_rss_subgraph(self):
        from digest_runner.subgraphs.rss_subgraph import RssSubgraph
        subgraph = get_subgraph("rss_feeds")
        assert isinstance(subgraph, RssSubgraph)


class TestRunSourcePipeline:
    def test_returns_dict_with_expected_keys(self, sample_subgraph_output):
        mock_subgraph = MagicMock()
        mock_subgraph.run.return_value = sample_subgraph_output
        mock_subgraph.source = SourceName.ARXIV

        with patch("digest_runner.nodes.fetch_node.get_subgraph", return_value=mock_subgraph):
            result = run_source_pipeline({"source_name": "arxiv"})

        assert "subgraph_outputs" in result
        assert "errors" in result

    def test_output_is_list_of_one(self, sample_subgraph_output):
        mock_subgraph = MagicMock()
        mock_subgraph.run.return_value = sample_subgraph_output
        mock_subgraph.source = SourceName.ARXIV

        with patch("digest_runner.nodes.fetch_node.get_subgraph", return_value=mock_subgraph):
            result = run_source_pipeline({"source_name": "arxiv"})

        assert len(result["subgraph_outputs"]) == 1
        assert isinstance(result["subgraph_outputs"][0], SubgraphOutput)

    def test_unknown_source_returns_empty_output(self):
        result = run_source_pipeline({"source_name": "unknown_xyz"})
        assert len(result["subgraph_outputs"]) == 1
        assert result["subgraph_outputs"][0].total_selected == 0
        assert len(result["errors"]) == 1

    def test_subgraph_run_exception_handled_gracefully(self, sample_subgraph_output):
        mock_subgraph = MagicMock()
        mock_subgraph.run.side_effect = RuntimeError("MCP connection failed")
        mock_subgraph.source = SourceName.ARXIV

        with patch("digest_runner.nodes.fetch_node.get_subgraph", return_value=mock_subgraph):
            result = run_source_pipeline({"source_name": "arxiv"})

        assert len(result["subgraph_outputs"]) == 1
        assert result["subgraph_outputs"][0].total_selected == 0
        assert any("MCP connection failed" in e for e in result["errors"])

    def test_no_errors_on_success(self, sample_subgraph_output):
        mock_subgraph = MagicMock()
        mock_subgraph.run.return_value = sample_subgraph_output
        mock_subgraph.source = SourceName.ARXIV

        with patch("digest_runner.nodes.fetch_node.get_subgraph", return_value=mock_subgraph):
            result = run_source_pipeline({"source_name": "arxiv"})

        assert result["errors"] == []


# ── MCP-live tests (skipped if MCP_BASE_URL not set) ─────────────────────────

@pytest.mark.skipif(
    not os.environ.get("MCP_BASE_URL"),
    reason="MCP_BASE_URL not set — skipping live MCP tests",
)
class TestRunSourcePipelineLive:
    def test_arxiv_live_fetch(self):
        """Actually calls ArxivSubgraph.run() — needs MCP server running."""
        result = run_source_pipeline({"source_name": "arxiv"})
        assert len(result["subgraph_outputs"]) == 1
        output = result["subgraph_outputs"][0]
        assert output.total_reviewed >= 0
        assert isinstance(output.enriched_items, list)
