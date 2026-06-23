"""
scripts/backfill_digest.py
==========================
Purpose:
  Manually generate digests for past dates (replay MCP fetch with historical parameters or archived raw JSON).

When implemented:
  - CLI args for date range; write under digests/YYYY-MM-DD/ without touching publishers if --dry-run.

Notes:
  - Requires stable archival format for raw feeds if replaying without live APIs.
"""
