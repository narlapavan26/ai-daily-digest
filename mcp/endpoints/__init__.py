"""
mcp/endpoints/__init__.py
=========================
Purpose:
  Package marker for per-source FastAPI route modules.

When implemented:
  - Re-export APIRouter instances or a registry used by mcp/main.py.

Notes:
  - One module per MCP source (arxiv, github, hackernews, reddit, huggingface, rss, stackoverflow).
"""
