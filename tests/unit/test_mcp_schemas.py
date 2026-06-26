"""
tests/unit/test_mcp_schemas.py
================================
Unit tests for MCP wire-format schemas.
Validates DigestItem and SourceResponse models without network calls.
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timezone

import pytest

# Ensure mcp modules are importable (mcp/ has no __init__.py — it's a standalone app)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp"))

from schemas.common import DigestItem, SourceResponse


class TestDigestItemValidation:
    """Test DigestItem Pydantic validation rules."""

    def _make_valid_item(self, **overrides) -> dict:
        """Base valid item dict; override fields as needed."""
        base = {
            "id": "test:item-001",
            "source": "arxiv",
            "title": "Test Paper Title For Validation",
            "url": "https://arxiv.org/abs/2401.00001",
            "content": "A" * 50,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "category": "article",
            "metadata": {},
        }
        base.update(overrides)
        return base

    def test_valid_item_creates_successfully(self):
        item = DigestItem(**self._make_valid_item())
        assert item.id == "test:item-001"
        assert item.source == "arxiv"

    def test_rejects_extra_fields(self):
        with pytest.raises(Exception):
            DigestItem(**self._make_valid_item(unknown_field="bad"))

    def test_rejects_invalid_source(self):
        with pytest.raises(Exception):
            DigestItem(**self._make_valid_item(source="invalid_source"))

    def test_rejects_short_content(self):
        with pytest.raises(Exception):
            DigestItem(**self._make_valid_item(content="short"))

    def test_rejects_short_id(self):
        with pytest.raises(Exception):
            DigestItem(**self._make_valid_item(id="ab"))

    def test_rejects_invalid_url(self):
        with pytest.raises(Exception):
            DigestItem(**self._make_valid_item(url="not-a-url"))

    def test_metadata_none_becomes_empty_dict(self):
        item = DigestItem(**self._make_valid_item(metadata=None))
        assert item.metadata == {}

    def test_all_valid_sources(self):
        for source in ["arxiv", "github", "hackernews", "reddit",
                       "huggingface", "rss_feeds", "stackoverflow"]:
            item = DigestItem(**self._make_valid_item(source=source))
            assert item.source == source


class TestSourceResponse:
    """Test SourceResponse envelope validation."""

    def test_empty_response(self):
        resp = SourceResponse(
            source="arxiv",
            items=[],
            total_fetched=0,
            fetch_timestamp=datetime.now(timezone.utc),
            errors=[],
        )
        assert resp.source == "arxiv"
        assert len(resp.items) == 0

    def test_error_messages_capped_at_200_chars(self):
        long_error = "E" * 500
        resp = SourceResponse(
            source="rss_feeds",
            items=[],
            total_fetched=0,
            fetch_timestamp=datetime.now(timezone.utc),
            errors=[long_error],
        )
        assert len(resp.errors[0]) <= 200

    def test_model_rebuild_succeeds(self):
        DigestItem.model_rebuild()
        SourceResponse.model_rebuild()
