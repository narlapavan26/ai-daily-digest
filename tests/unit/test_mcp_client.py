"""
tests/unit/test_mcp_client.py
===============================
Unit tests for MCP client transport logic.
Uses mocks — no real HTTP calls.
"""
from __future__ import annotations

import pytest

from digest_runner.utils.mcp_client import _is_local, _normalize_base, _TOOL_NAME_MAP


class TestIsLocal:
    def test_localhost(self):
        assert _is_local("http://localhost:8000") is True

    def test_loopback(self):
        assert _is_local("http://127.0.0.1:8000") is True

    def test_remote_url(self):
        assert _is_local("https://my-server.fastmcp.app") is False

    def test_remote_with_mcp(self):
        assert _is_local("https://my-server.fastmcp.app/mcp") is False


class TestNormalizeBase:
    def test_strips_trailing_slash(self):
        assert _normalize_base("https://example.com/") == "https://example.com"

    def test_strips_mcp_suffix(self):
        assert _normalize_base("https://example.com/mcp") == "https://example.com"

    def test_strips_mcp_with_trailing_slash(self):
        assert _normalize_base("https://example.com/mcp/") == "https://example.com"

    def test_preserves_clean_url(self):
        assert _normalize_base("https://example.com") == "https://example.com"

    def test_localhost(self):
        assert _normalize_base("http://127.0.0.1:8000") == "http://127.0.0.1:8000"


class TestToolNameMap:
    def test_all_sources_have_mappings(self):
        expected_paths = [
            "/fetch/rss", "/fetch/arxiv", "/fetch/github",
            "/fetch/hackernews", "/fetch/huggingface",
            "/fetch/stackoverflow", "/fetch/reddit",
        ]
        for path in expected_paths:
            assert path in _TOOL_NAME_MAP, f"Missing tool mapping for {path}"

    def test_tool_names_are_strings(self):
        for path, tool_name in _TOOL_NAME_MAP.items():
            assert isinstance(tool_name, str)
            assert len(tool_name) > 0
