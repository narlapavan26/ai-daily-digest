"""
tests/unit/test_fast_fail_node.py
====================================
Tests for apply_fast_fail() in digest_runner/nodes/fast_fail_node.py.
Does NOT require MCP server or LLM API keys.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from digest_runner.nodes.fast_fail_node import apply_fast_fail
from digest_runner.schemas.digest_schemas import (
    FastFailBatch,
    FastFailVerdict,
    NormalizedItem,
    SourceName,
)


class TestApplyFastFail:
    def test_fresh_item_passes(self, make_normalized_item):
        from digest_runner.subgraphs.arxiv_subgraph import ArxivSubgraph
        subgraph = ArxivSubgraph()
        item = make_normalized_item(days_old=1.0)
        batch = apply_fast_fail([item], subgraph)
        assert isinstance(batch, FastFailBatch)
        assert len(batch.passed) == 1
        assert len(batch.dropped) == 0
        assert batch.pass_rate == 1.0

    def test_stale_arxiv_dropped(self, make_normalized_item):
        from digest_runner.subgraphs.arxiv_subgraph import ArxivSubgraph
        subgraph = ArxivSubgraph()
        stale_item = make_normalized_item(days_old=10.0)  # arxiv stale_days=7
        batch = apply_fast_fail([stale_item], subgraph)
        assert len(batch.passed) == 0
        assert len(batch.dropped) == 1
        assert batch.dropped[0].verdict == FastFailVerdict.DROP_STALE

    def test_empty_content_dropped(self, make_normalized_item):
        from digest_runner.subgraphs.arxiv_subgraph import ArxivSubgraph
        subgraph = ArxivSubgraph()
        short_item = make_normalized_item(content="Short here!")  # 12 chars: >= 10 (pydantic min) but < 30
        # Note: is_junk_release() fires first for very short content+title items,
        # returning DROP_LOWSIG (global_junk_filter) instead of DROP_EMPTY.
        batch = apply_fast_fail([short_item], subgraph)
        assert len(batch.passed) == 0
        assert len(batch.dropped) == 1
        assert batch.dropped[0].verdict in (
            FastFailVerdict.DROP_EMPTY,
            FastFailVerdict.DROP_LOWSIG,
        ), f"Expected DROP_EMPTY or DROP_LOWSIG, got {batch.dropped[0].verdict}"

    def test_mix_of_pass_and_drop(self, make_normalized_item):
        from digest_runner.subgraphs.arxiv_subgraph import ArxivSubgraph
        subgraph = ArxivSubgraph()
        fresh = make_normalized_item(item_id="arxiv:001", days_old=1.0)
        stale = make_normalized_item(item_id="arxiv:002", days_old=15.0)
        batch = apply_fast_fail([fresh, stale], subgraph)
        assert len(batch.passed) == 1
        assert len(batch.dropped) == 1
        assert batch.passed[0].id == "arxiv:001"
        assert batch.pass_rate == 0.5

    def test_empty_input_returns_empty_batch(self, make_normalized_item):
        from digest_runner.subgraphs.arxiv_subgraph import ArxivSubgraph
        subgraph = ArxivSubgraph()
        batch = apply_fast_fail([], subgraph)
        assert batch.passed == []
        assert batch.dropped == []
        assert batch.pass_rate == 0.0

    def test_pass_rate_computed_correctly(self, make_normalized_item):
        from digest_runner.subgraphs.arxiv_subgraph import ArxivSubgraph
        subgraph = ArxivSubgraph()
        items = [
            make_normalized_item(item_id=f"arxiv:00{i}", days_old=float(i))
            for i in range(1, 5)  # days_old: 1, 2, 3, 4 — all < 7 (arxiv stale_days)
        ]
        batch = apply_fast_fail(items, subgraph)
        assert batch.pass_rate == 1.0
        assert len(batch.passed) == 4

    def test_rss_stale_threshold(self, make_normalized_item):
        """RSS feeds have stale_days=7.0 by default (raised from 5.0 to match rss_days_back=7)."""
        from digest_runner.subgraphs.rss_subgraph import RssSubgraph
        subgraph = RssSubgraph()
        stale_rss = make_normalized_item(
            item_id="rss:001",
            source=SourceName.RSS_FEEDS,
            days_old=8.0,  # > rss stale_days=7.0
        )
        batch = apply_fast_fail([stale_rss], subgraph)
        assert len(batch.dropped) == 1
        assert batch.dropped[0].verdict == FastFailVerdict.DROP_STALE
