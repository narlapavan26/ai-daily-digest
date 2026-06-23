"""
shared/schemas.py
=================
Purpose:
  Optional cross-package Pydantic models identical for MCP JSON and runner parsing (DigestItem, SourceResponse).

When implemented:
  - Define or import-from-single-place models to avoid drift between MCP and LangGraph fetch nodes.

Notes:
  - If deployment constraints forbid a shared package, keep MCP models in mcp/schemas/ and mirror in runner tests only.
"""
