"""
mcp/utils/http_client.py
========================
Purpose:
  Shared HTTP client configuration for MCP (timeouts, headers, optional retries).

When implemented:
  - Factory for httpx.Client or httpx.AsyncClient with consistent User-Agent and timeouts.

Notes: MCP server may stay sync in FastAPI handlers; use the style that matches your endpoint implementations.
"""
