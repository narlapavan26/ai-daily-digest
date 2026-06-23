"""
Smoke-test POST /fetch/rss without starting uvicorn (invokes handler in-process).

Usage (from repo root, conda env `ai`):
  cd mcp && python ../scripts/test_rss_mcp_local.py
"""
from __future__ import annotations

import os
import sys

MCP_DIR = os.path.join(os.path.dirname(__file__), "..", "mcp")
sys.path.insert(0, os.path.abspath(MCP_DIR))

os.chdir(os.path.abspath(MCP_DIR))

# pyrefly: ignore [missing-import]
from endpoints.rss import fetch_rss  # noqa: E402
# pyrefly: ignore [missing-import]
from schemas.request_models import RssFetchRequest  # noqa: E402


def main() -> None:
    body = RssFetchRequest(
        feed_urls=["https://huggingface.co/blog/feed.xml"],
        max_items_per_feed=3,
        days_back=14,
    )
    out = fetch_rss(body)
    print("source:", out.source, "items:", out.total_fetched, "errors:", len(out.errors))
    for it in out.items[:2]:
        print("-", it.title[:72])


if __name__ == "__main__":
    main()
