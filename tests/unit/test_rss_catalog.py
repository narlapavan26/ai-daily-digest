"""
tests/unit/test_rss_catalog.py
================================
Validate RSS feed catalog integrity — no network calls.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp"))

from rss_feed_catalog import RSS_VERIFIED_FEEDS


class TestRssCatalogIntegrity:
    def test_catalog_is_list(self):
        assert isinstance(RSS_VERIFIED_FEEDS, list)

    def test_minimum_feed_count(self):
        assert len(RSS_VERIFIED_FEEDS) >= 50, (
            f"Expected at least 50 feeds, got {len(RSS_VERIFIED_FEEDS)}"
        )

    def test_all_entries_are_tuples_of_three(self):
        for i, entry in enumerate(RSS_VERIFIED_FEEDS):
            assert isinstance(entry, tuple), f"Entry {i} is not a tuple"
            assert len(entry) == 3, f"Entry {i} has {len(entry)} elements"

    def test_all_urls_start_with_http(self):
        for name, url, section in RSS_VERIFIED_FEEDS:
            assert url.startswith("http"), f"Bad URL for '{name}': {url}"

    def test_no_duplicate_urls(self):
        urls = [url for _, url, _ in RSS_VERIFIED_FEEDS]
        dupes = [u for u in urls if urls.count(u) > 1]
        assert len(set(dupes)) == 0, f"Duplicate feed URLs: {set(dupes)}"

    def test_all_names_non_empty(self):
        for name, url, section in RSS_VERIFIED_FEEDS:
            assert name.strip(), f"Empty feed name for URL: {url}"

    def test_all_sections_non_empty(self):
        for name, url, section in RSS_VERIFIED_FEEDS:
            assert section.strip(), f"Empty section for feed: {name}"

    def test_known_sections_exist(self):
        sections = {section for _, _, section in RSS_VERIFIED_FEEDS}
        assert "Company Blogs" in sections
