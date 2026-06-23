"""
digest_runner/config/llm_providers.py
=====================================
Purpose:
  Factory functions for LLM clients used by Instructor (Groq, Gemini, Cerebras, Together, OpenRouter, etc.).

When implemented:
  - Map LLMProvider enum (from digest schemas) to client + model id strings.
  - Implement primary + fallback chain for rate limits.

Notes:
  - Keep provider-specific quirks out of graph nodes; isolate here.
"""
