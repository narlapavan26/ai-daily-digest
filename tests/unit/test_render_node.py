"""
tests/unit/test_render_node.py
=================================
Tests for render_digest() and render_markdown() in
digest_runner/nodes/render_node.py.
Does NOT require MCP server or LLM API keys.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from digest_runner.nodes.render_node import render_digest, render_markdown


class TestRenderMarkdown:
    def test_render_returns_string(self, mock_final_digest_schema):
        content = render_markdown(mock_final_digest_schema)
        assert isinstance(content, str)
        assert len(content) > 100

    def test_header_contains_date(self, mock_final_digest_schema):
        content = render_markdown(mock_final_digest_schema)
        assert "2026-06-10" in content

    def test_top_story_section_present(self, mock_final_digest_schema):
        content = render_markdown(mock_final_digest_schema)
        assert "Top Story" in content

    def test_top_story_headline_present(self, mock_final_digest_schema):
        content = render_markdown(mock_final_digest_schema)
        assert "LangGraph 0.3.0 ships native streaming support" in content

    def test_section_heading_present(self, mock_final_digest_schema):
        content = render_markdown(mock_final_digest_schema)
        assert "Research" in content

    def test_quick_links_table_present(self, mock_final_digest_schema):
        content = render_markdown(mock_final_digest_schema)
        assert "Quick Links" in content

    def test_stats_table_present(self, mock_final_digest_schema):
        content = render_markdown(mock_final_digest_schema)
        assert "Today's Stats" in content
        assert "arxiv" in content
        assert "hackernews" in content

    def test_footer_contains_provider(self, mock_final_digest_schema):
        content = render_markdown(mock_final_digest_schema)
        assert "groq" in content.lower()

    def test_action_hint_rendered(self, mock_final_digest_schema):
        content = render_markdown(mock_final_digest_schema)
        assert "pip install langgraph==0.3.0" in content

    def test_item_url_present(self, mock_final_digest_schema):
        content = render_markdown(mock_final_digest_schema)
        assert "news.ycombinator.com" in content

    def test_no_top_story_renders_gracefully(self, mock_final_digest_schema):
        mock_final_digest_schema.top_story = None
        content = render_markdown(mock_final_digest_schema)
        assert isinstance(content, str)
        assert len(content) > 50


class TestRenderDigest:
    def test_saves_file_to_disk(self, mock_final_digest_schema, tmp_path):
        env_backup = os.environ.get("DIGEST_OUTPUT_DIR")
        try:
            os.environ["DIGEST_OUTPUT_DIR"] = str(tmp_path)
            state = {"final_digest": mock_final_digest_schema, "run_date": "2026-06-10"}
            result = render_digest(state)
            assert "output_path" in result
            assert Path(result["output_path"]).exists()
        finally:
            if env_backup is not None:
                os.environ["DIGEST_OUTPUT_DIR"] = env_backup
            elif "DIGEST_OUTPUT_DIR" in os.environ:
                del os.environ["DIGEST_OUTPUT_DIR"]

    def test_output_filename_contains_date(self, mock_final_digest_schema, tmp_path):
        env_backup = os.environ.get("DIGEST_OUTPUT_DIR")
        try:
            os.environ["DIGEST_OUTPUT_DIR"] = str(tmp_path)
            state = {"final_digest": mock_final_digest_schema, "run_date": "2026-06-10"}
            result = render_digest(state)
            assert "2026-06-10" in result["output_path"]
        finally:
            if env_backup is not None:
                os.environ["DIGEST_OUTPUT_DIR"] = env_backup
            elif "DIGEST_OUTPUT_DIR" in os.environ:
                del os.environ["DIGEST_OUTPUT_DIR"]

    def test_file_content_is_markdown(self, mock_final_digest_schema, tmp_path):
        env_backup = os.environ.get("DIGEST_OUTPUT_DIR")
        try:
            os.environ["DIGEST_OUTPUT_DIR"] = str(tmp_path)
            state = {"final_digest": mock_final_digest_schema, "run_date": "2026-06-10"}
            result = render_digest(state)
            content = Path(result["output_path"]).read_text(encoding="utf-8")
            assert content.startswith("#")
            assert "AI/ML Daily Digest" in content
        finally:
            if env_backup is not None:
                os.environ["DIGEST_OUTPUT_DIR"] = env_backup
            elif "DIGEST_OUTPUT_DIR" in os.environ:
                del os.environ["DIGEST_OUTPUT_DIR"]

    def test_missing_final_digest_returns_empty_path(self):
        state = {"run_date": "2026-06-10"}
        result = render_digest(state)
        assert result.get("output_path") == "" or result.get("output_path") is None

    def test_creates_output_dir_if_not_exists(self, mock_final_digest_schema, tmp_path):
        nested_dir = tmp_path / "nested" / "subdir"
        env_backup = os.environ.get("DIGEST_OUTPUT_DIR")
        try:
            os.environ["DIGEST_OUTPUT_DIR"] = str(nested_dir)
            state = {"final_digest": mock_final_digest_schema, "run_date": "2026-06-10"}
            result = render_digest(state)
            assert Path(result["output_path"]).exists()
        finally:
            if env_backup is not None:
                os.environ["DIGEST_OUTPUT_DIR"] = env_backup
            elif "DIGEST_OUTPUT_DIR" in os.environ:
                del os.environ["DIGEST_OUTPUT_DIR"]
