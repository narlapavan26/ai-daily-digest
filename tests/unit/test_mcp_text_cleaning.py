"""
tests/unit/test_mcp_text_cleaning.py
======================================
Unit tests for MCP text cleaning utilities.
No network calls.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp"))

from utils.text_cleaning import (
    clean_html,
    clean_latex,
    truncate_at_sentence,
    clean_markdown_excerpt,
)


class TestCleanHtml:
    def test_strips_tags(self):
        result = clean_html("<p>Hello <b>world</b></p>")
        assert "<p>" not in result
        assert "<b>" not in result
        assert "Hello" in result
        assert "world" in result

    def test_decodes_entities(self):
        result = clean_html("&amp; &lt; &gt;")
        assert "&" in result

    def test_empty_string(self):
        assert clean_html("") == ""

    def test_collapses_whitespace(self):
        result = clean_html("  Hello   World  ")
        assert "  " not in result


class TestCleanLatex:
    def test_strips_inline_math(self):
        result = clean_latex("The value $x$ is important")
        assert "$" not in result

    def test_empty_string(self):
        assert clean_latex("") == ""

    def test_preserves_plain_text(self):
        text = "No latex here"
        assert clean_latex(text) == text


class TestTruncateAtSentence:
    def test_short_text_unchanged(self):
        text = "Short text."
        assert truncate_at_sentence(text, 100) == text

    def test_truncates_at_period(self):
        text = "First sentence. Second sentence. Third sentence."
        result = truncate_at_sentence(text, 25)
        assert len(result) <= 25

    def test_adds_ellipsis_when_no_sentence_boundary(self):
        text = "A" * 200
        result = truncate_at_sentence(text, 50)
        assert len(result) <= 55


class TestCleanMarkdownExcerpt:
    def test_strips_code_blocks(self):
        text = 'Before ```python\ncode()\n``` After'
        result = clean_markdown_excerpt(text)
        assert "```" not in result

    def test_strips_image_links(self):
        text = "Text ![alt](http://img.png) more text"
        result = clean_markdown_excerpt(text)
        assert "![" not in result

    def test_preserves_link_text(self):
        text = "See [this link](http://example.com) for details"
        result = clean_markdown_excerpt(text)
        assert "this link" in result

    def test_empty_string(self):
        assert clean_markdown_excerpt("") == ""

    def test_respects_max_chars(self):
        text = "A " * 5000
        result = clean_markdown_excerpt(text, max_chars=100)
        assert len(result) <= 110
