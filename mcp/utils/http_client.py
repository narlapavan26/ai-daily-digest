"""
mcp/utils/http_client.py
========================
Shared HTTP client configuration for MCP endpoints.
Provides a consistent User-Agent, timeouts, and connection pooling.

Usage:
    from mcp.utils.http_client import get_http_client

    with get_http_client() as client:
        response = client.get("https://api.example.com/data")
"""
from __future__ import annotations

import httpx

# Shared configuration
DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = "AI-Digest-MCP/1.0 (+https://github.com/narlapavan26/ai-daily-digest)"
DEFAULT_LIMITS = httpx.Limits(
    max_connections=20,
    max_keepalive_connections=10,
    keepalive_expiry=30.0,
)


def get_http_client(
    timeout: float = DEFAULT_TIMEOUT,
    extra_headers: dict | None = None,
) -> httpx.Client:
    """
    Create a configured httpx.Client for MCP endpoints.

    Use as a context manager:
        with get_http_client() as client:
            resp = client.get(url)
    """
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)

    return httpx.Client(
        timeout=timeout,
        limits=DEFAULT_LIMITS,
        headers=headers,
        follow_redirects=True,
    )
