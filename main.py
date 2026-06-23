"""
Minimal FastAPI -> FastMCP entrypoint.

This file exists so Prefect Horizon can auto-detect `main.py:mcp` during deployment.
The mcp/ package is the FastAPI + FastMCP data server.
"""

from mcp.main import app, mcp  # noqa: F401  (was incorrectly `mcp_server.main`)

__all__ = ["app", "mcp"]

