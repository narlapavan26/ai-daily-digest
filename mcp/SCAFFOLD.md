# MCP package scaffold

This folder follows the split layout (`endpoints/`, `schemas/`, `utils/`).

**Current state:** `main.py` remains the deployed FastAPI + FastMCP entrypoint with live endpoint code.

**Next step (implementation):** Move route handlers into `endpoints/*.py` and import routers or register routes from `main.py`, without changing Horizon’s entrypoint filename if your host expects `main.py`.
