"""
digest_runner/utils/text_utils.py
=================================
Purpose:
  Runner-side text helpers (extra truncation, token budgeting hints) beyond MCP cleaning.

When implemented:
  - Functions that prepare compact LLM payloads from NormalizedItem lists.

Notes:
  - Do not duplicate MCP hygiene; runner focuses on prompt-size controls.
"""
