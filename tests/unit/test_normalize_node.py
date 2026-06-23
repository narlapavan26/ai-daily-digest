"""
tests/unit/test_normalize_node.py
===================================
Tests for normalize_items() in digest_runner/nodes/normalize_node.py.
Does NOT require MCP server or LLM API keys.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List

import pytest

from digest_runner.nodes.normalize_node import normalize_items
from digest_runner.schemas.digest_schemas import NormalizedItem, SourceName
from digest_runner.subgraphs.base import BaseSubgraph, parse_utc_dt


class _MockArxivSubgraph(BaseSubgraph):
    """Minimal concrete subgraph for normalize testing."""
    source = SourceName.ARXIV
    budget = 3
    stale_days = 7.0

    def fetch_from_mcp(self) -> Dict[str, Any]:
        return {}

    def normalize(self, raw_items: List[Dict[str, Any]]) -> List[NormalizedItem]:
        result = []
        for row in raw_items:
            published_at = parse_utc_dt(row.get("published_at", "2026-06-10T00:00:00Z"))
            days_old = max(
                0.0,
                (_dt.datetime.now(_dt.timezone.utc) - published_at).total_seconds() / 86400.0,
            )
            content = str(row.get("content", "Test abstract for LLM agents research."))[:2000]
            min_len = 10
            if len(content) < min_len:
                content = content + " " * (min_len - len(content))
            result.append(NormalizedItem(
                id=str(row["id"]),
                source=SourceName.ARXIV,
                title=str(row.get("title", "Test Paper")),
                url=str(row.get("url", "https://arxiv.org/abs/2401.00001")),
                published_at=published_at,
                content_for_llm=content,
                quality_signals={"category": row.get("category", "cs.AI")},
                days_old=days_old,
            ))
        return result


@pytest.fixture
def mock_subgraph():
    return _MockArxivSubgraph()


@pytest.fixture
def raw_arxiv_items():
    return [
        {
            "id": "arxiv:2401.00001",
            "title": "LLM Agents with Tool Use",
            "url": "https://arxiv.org/abs/2401.00001",
            "published_at": "2026-06-09T12:00:00Z",
            "content": "This paper proposes a novel approach to LLM agent tool use "
                       "that improves accuracy by 15% on standard benchmarks.",
            "category": "cs.AI",
        },
        {
            "id": "arxiv:2401.00002",
            "title": "Efficient Attention for Long Contexts",
            "url": "https://arxiv.org/abs/2401.00002",
            "published_at": "2026-06-08T09:00:00Z",
            "content": "We present a sparse attention mechanism that reduces memory "
                       "usage by 60% for 128K token contexts.",
            "category": "cs.CL",
        },
    ]


class TestNormalizeItems:
    def test_returns_normalized_items(self, mock_subgraph, raw_arxiv_items):
        result = normalize_items(raw_arxiv_items, mock_subgraph)
        assert len(result) == 2

    def test_item_ids_preserved(self, mock_subgraph, raw_arxiv_items):
        result = normalize_items(raw_arxiv_items, mock_subgraph)
        ids = [item.id for item in result]
        assert "arxiv:2401.00001" in ids
        assert "arxiv:2401.00002" in ids

    def test_source_set_correctly(self, mock_subgraph, raw_arxiv_items):
        result = normalize_items(raw_arxiv_items, mock_subgraph)
        for item in result:
            assert item.source == SourceName.ARXIV

    def test_content_for_llm_populated(self, mock_subgraph, raw_arxiv_items):
        result = normalize_items(raw_arxiv_items, mock_subgraph)
        for item in result:
            assert len(item.content_for_llm) >= 10

    def test_days_old_computed(self, mock_subgraph, raw_arxiv_items):
        result = normalize_items(raw_arxiv_items, mock_subgraph)
        for item in result:
            assert item.days_old >= 0.0

    def test_empty_input_returns_empty(self, mock_subgraph):
        result = normalize_items([], mock_subgraph)
        assert result == []

    def test_bad_item_skipped_gracefully(self, mock_subgraph):
        """Items that fail normalize() should be skipped, not raise."""
        bad_item = {"id": None, "title": None, "url": None}
        good_item = {
            "id": "arxiv:2401.00099",
            "title": "Valid Paper Title",
            "url": "https://arxiv.org/abs/2401.00099",
            "published_at": "2026-06-09T00:00:00Z",
            "content": "A valid paper about LLM agents and retrieval augmented generation.",
            "category": "cs.AI",
        }
        result = normalize_items([bad_item, good_item], mock_subgraph)
        assert any(item.id == "arxiv:2401.00099" for item in result)

    def test_quality_signals_populated(self, mock_subgraph, raw_arxiv_items):
        result = normalize_items(raw_arxiv_items, mock_subgraph)
        for item in result:
            assert isinstance(item.quality_signals, dict)
            assert "category" in item.quality_signals
