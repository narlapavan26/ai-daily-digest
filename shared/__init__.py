"""
shared/__init__.py
==================
Purpose:
  Shared package between mcp and digest_runner (optional single source of truth for wire enums/models).

When implemented:
  - Re-export minimal shared types (e.g. DigestItem, SourceName) if both components import the same code.

Notes:
  - Horizon deploy may only include mcp/; keep shared copy small or vendor duplicates if needed.
"""
