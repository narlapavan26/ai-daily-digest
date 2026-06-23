"""
scripts/test_mcp_local.py
=========================
Purpose:
  Dev script to smoke-test a running MCP server locally (health, sample fetch_rss/fetch_arxiv calls).

When implemented:
  - Parse CLI args for base URL and bearer token; exit 0/1 for CI-style checks.

Notes:
  - Do not hardcode secrets; read from environment.
"""
