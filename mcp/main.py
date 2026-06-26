"""
mcp/main.py
============
AI Digest MCP Data Server — FastAPI application entry point.

Architecture:
    FastAPI app (REST API for local testing via /docs)
        ↓ include_router for each source
    FastMCP.from_fastapi (converts the FastAPI app into an MCP server for Prefect Horizon)

All endpoint logic lives in mcp/endpoints/<source>.py — this file only wires
routers together and exposes `app` (FastAPI) and `mcp` (FastMCP) objects.

Running locally:
    cd mcp
    uvicorn main:app --reload --port 8000
    # Then open: http://127.0.0.1:8000/docs

Deploying to Prefect Horizon:
    The `mcp` object is the entry point Horizon expects.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastmcp import FastMCP

# pyrefly: ignore [missing-import]
from endpoints.arxiv import router as arxiv_router
# pyrefly: ignore [missing-import]
from endpoints.github import router as github_router
# pyrefly: ignore [missing-import]
from endpoints.hackernews import router as hackernews_router
# pyrefly: ignore [missing-import]
from endpoints.huggingface import router as huggingface_router
# pyrefly: ignore [missing-import]
from endpoints.reddit import router as reddit_router
# pyrefly: ignore [missing-import]
from endpoints.rss import router as rss_router
# pyrefly: ignore [missing-import]
from endpoints.stackoverflow import router as stackoverflow_router
# pyrefly: ignore [missing-import]
from schemas.common import DigestItem, SourceResponse

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Digest MCP Data Server",
    description=(
        "Provides structured AI/ML news data from 7 sources: RSS, ArXiv, GitHub, "
        "HackerNews, HuggingFace, Reddit, and StackOverflow. "
        "Each source endpoint returns a SourceResponse with DigestItem list."
    ),
    version="1.0.0",
)

# ── Register all source routers ───────────────────────────────────────────────
app.include_router(rss_router)
app.include_router(arxiv_router)
app.include_router(github_router)
app.include_router(hackernews_router)
app.include_router(huggingface_router)
app.include_router(reddit_router)
app.include_router(stackoverflow_router)

# ── Health check endpoint ─────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    """Lightweight health check for CI, Horizon, and monitoring."""
    return {"status": "ok", "version": "1.0.0", "sources": 7}


# ── FastMCP conversion (required for Prefect Horizon deployment) ───────────────
# FastMCP wraps the FastAPI app into an MCP-compatible server.
# Pydantic v2 + from __future__ import annotations sometimes needs a model_rebuild call.
DigestItem.model_rebuild()
SourceResponse.model_rebuild()

mcp = FastMCP.from_fastapi(app=app, name="AI Digest MCP Server")

__all__ = ["app", "mcp"]
