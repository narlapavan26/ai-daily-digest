"""
tests/unit/test_merger_node.py
=================================
Tests for merge_subgraph_outputs() in digest_runner/nodes/merger_node.py.
Does NOT require MCP server or LLM API keys.
"""
from __future__ import annotations

import pytest

from digest_runner.nodes.merger_node import merge_subgraph_outputs, _normalize_title
from digest_runner.schemas.digest_schemas import (
    DeduplicationResult,
    DigestSectionName,
    LLMProvider,
    NoveltyType,
    SourceName,
    SubgraphOutput,
    TimeSensitivity,
)


def build_state(outputs):
    return {"subgraph_outputs": outputs, "run_date": "2026-06-10", "errors": []}


class TestNormalizeTitle:
    def test_lowercase(self):
        # _normalize_title replaces dots with spaces (via the [^a-z0-9\s] → " " rule)
        # so "LangGraph 0.3.0" → "langgraph 0 3 0" (not "langgraph 030")
        assert _normalize_title("LangGraph 0.3.0") == "langgraph 0 3 0"

    def test_strips_punctuation(self):
        assert _normalize_title("Hello, World!") == "hello world"

    def test_whitespace_collapse(self):
        assert _normalize_title("  too   many   spaces  ") == "too many spaces"

    def test_empty_string(self):
        assert _normalize_title("") == ""


class TestMergeSubgraphOutputs:
    def test_basic_merge(self, two_subgraph_outputs):
        state = build_state(two_subgraph_outputs)
        result = merge_subgraph_outputs(state)
        assert "merged_items" in result
        assert "deduplication_result" in result
        assert len(result["merged_items"]) == 2

    def test_dedup_result_schema(self, two_subgraph_outputs):
        state = build_state(two_subgraph_outputs)
        result = merge_subgraph_outputs(state)
        dedup = result["deduplication_result"]
        assert isinstance(dedup, DeduplicationResult)
        assert dedup.total_before == 2
        assert dedup.total_after == 2
        assert dedup.total_dropped == 0

    def test_id_deduplication(self, make_subgraph_output, make_enriched_item):
        """Same item_id from two sources → keep higher relevance_score."""
        item_low = make_enriched_item(
            item_id="shared:001",
            source=SourceName.ARXIV,
            title="GPT-5 Released by OpenAI",
            relevance_score=0.70,
        )
        item_high = make_enriched_item(
            item_id="shared:001",
            source=SourceName.RSS_FEEDS,
            title="GPT-5 Released by OpenAI",
            relevance_score=0.95,
        )
        out1 = make_subgraph_output(source=SourceName.ARXIV, items=[item_low])
        out2 = make_subgraph_output(source=SourceName.RSS_FEEDS, items=[item_high])
        state = build_state([out1, out2])
        result = merge_subgraph_outputs(state)
        merged = result["merged_items"]
        assert len(merged) == 1
        assert merged[0].relevance_score == 0.95

    def test_title_deduplication(self, make_subgraph_output, make_enriched_item):
        """Same title (normalized), different IDs → keep higher relevance."""
        item_a = make_enriched_item(
            item_id="hn:001",
            source=SourceName.HACKERNEWS,
            title="LangGraph 0.3.0 Released",
            relevance_score=0.80,
        )
        item_b = make_enriched_item(
            item_id="rss:001",
            source=SourceName.RSS_FEEDS,
            title="LangGraph 0.3.0 released",  # same normalized form
            relevance_score=0.92,
        )
        out1 = make_subgraph_output(source=SourceName.HACKERNEWS, items=[item_a])
        out2 = make_subgraph_output(source=SourceName.RSS_FEEDS, items=[item_b])
        state = build_state([out1, out2])
        result = merge_subgraph_outputs(state)
        merged = result["merged_items"]
        assert len(merged) == 1
        assert merged[0].relevance_score == 0.92

    def test_empty_state_returns_empty(self):
        state = build_state([])
        result = merge_subgraph_outputs(state)
        assert result["merged_items"] == []
        assert result["deduplication_result"].total_before == 0

    def test_empty_subgraph_output_skipped(self, make_subgraph_output, make_enriched_item):
        empty_output = make_subgraph_output(source=SourceName.REDDIT, items=[])
        good_item = make_enriched_item(item_id="arxiv:001", source=SourceName.ARXIV)
        good_output = make_subgraph_output(source=SourceName.ARXIV, items=[good_item])
        state = build_state([empty_output, good_output])
        result = merge_subgraph_outputs(state)
        assert len(result["merged_items"]) == 1

    def test_sorted_by_relevance_score(self, make_subgraph_output, make_enriched_item):
        low  = make_enriched_item(item_id="a:001", relevance_score=0.60)
        mid  = make_enriched_item(item_id="b:002", relevance_score=0.80)
        high = make_enriched_item(item_id="c:003", relevance_score=0.95)
        out = make_subgraph_output(source=SourceName.ARXIV, items=[low, high, mid])
        state = build_state([out])
        result = merge_subgraph_outputs(state)
        scores = [item.relevance_score for item in result["merged_items"]]
        assert scores == sorted(scores, reverse=True)

    def test_duplicate_pairs_recorded(self, make_subgraph_output, make_enriched_item):
        dup_a = make_enriched_item(item_id="hn:001", title="Same Title", relevance_score=0.70)
        dup_b = make_enriched_item(item_id="hn:001", title="Same Title", relevance_score=0.85)
        out1 = make_subgraph_output(source=SourceName.HACKERNEWS, items=[dup_a])
        out2 = make_subgraph_output(source=SourceName.HACKERNEWS, items=[dup_b])
        state = build_state([out1, out2])
        result = merge_subgraph_outputs(state)
        dedup = result["deduplication_result"]
        assert len(dedup.duplicate_pairs) >= 1
        assert any(p.kept_id == "hn:001" for p in dedup.duplicate_pairs)
