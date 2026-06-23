"""
HTTP client for MCP `POST /fetch/*` endpoints. Returns parsed JSON dicts.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from ..config.settings import settings


def post_fetch(
    path_suffix: str,
    json_body: Dict[str, Any],
    *,
    bearer_token: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """
    POST to `{mcp_base_url}{path_suffix}` with JSON body.

    path_suffix example: `/fetch/rss`
    """
    base = str(settings.mcp_base_url).rstrip("/")
    path = path_suffix if path_suffix.startswith("/") else f"/{path_suffix}"
    url = f"{base}{path}"
    token = bearer_token if bearer_token is not None else settings.mcp_bearer_token
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    t = timeout if timeout is not None else settings.mcp_request_timeout_seconds
    with httpx.Client(timeout=t, follow_redirects=True) as client:
        resp = client.post(url, json=json_body, headers=headers)
        resp.raise_for_status()
        return resp.json()
