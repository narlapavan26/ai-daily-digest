"""
digest_runner/utils/metrics.py
==============================
Purpose:
  Accumulate LLMMetrics across nodes (calls, tokens, retries, fallbacks, latency).

When implemented:
  - Simple dataclass or TypedDict merge; log at end of run.

Notes:
  - Feed into DigestMetadata.source_counts / logging only; optional OpenTelemetry later.
"""
