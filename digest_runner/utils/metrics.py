"""
digest_runner/utils/metrics.py
==============================
Lightweight pipeline metrics — stored as JSON alongside each digest.
Accumulates LLMMetrics across nodes (calls, tokens, retries, fallbacks, latency).

Usage:
    from digest_runner.utils.metrics import PipelineMetrics

    metrics = PipelineMetrics(run_id="abc")
    metrics.record_source_timing("arxiv", 1200.0)
    metrics.record_llm_call()
    metrics.save("outputs/metrics_2026-06-26.json")
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class PipelineMetrics:
    """Accumulates metrics for a single pipeline run."""

    run_id: str = ""
    start_time: float = field(default_factory=time.time)
    source_timings: Dict[str, float] = field(default_factory=dict)
    llm_calls: int = 0
    llm_retries: int = 0
    llm_fallbacks: int = 0
    items_fetched: int = 0
    items_after_fastfail: int = 0
    items_after_dedup: int = 0
    items_in_digest: int = 0
    errors: List[str] = field(default_factory=list)
    providers_used: List[str] = field(default_factory=list)

    def record_source_timing(self, source: str, ms: float) -> None:
        """Record processing time for a source."""
        self.source_timings[source] = ms

    def record_llm_call(self) -> None:
        """Increment LLM call counter."""
        self.llm_calls += 1

    def record_llm_retry(self) -> None:
        """Increment LLM retry counter."""
        self.llm_retries += 1

    def record_llm_fallback(self, provider: str) -> None:
        """Record a provider fallback."""
        self.llm_fallbacks += 1
        if provider not in self.providers_used:
            self.providers_used.append(provider)

    def record_error(self, error: str) -> None:
        """Record a non-fatal error."""
        self.errors.append(error[:200])

    @property
    def elapsed_seconds(self) -> float:
        """Total elapsed time since metrics start."""
        return time.time() - self.start_time

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dict."""
        d = asdict(self)
        d["elapsed_seconds"] = self.elapsed_seconds
        return d

    def save(self, path: str) -> None:
        """Save metrics to a JSON file."""
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, default=str)
            logger.info("Pipeline metrics saved to %s", path)
        except Exception as exc:
            logger.warning("Failed to save pipeline metrics: %s", exc)

    def summary(self) -> str:
        """Return a human-readable summary string."""
        lines = [
            f"Pipeline Metrics (run_id={self.run_id[:8] if self.run_id else 'N/A'})",
            f"  Elapsed: {self.elapsed_seconds:.1f}s",
            f"  Sources: {len(self.source_timings)}",
            f"  Items fetched: {self.items_fetched}",
            f"  After fast-fail: {self.items_after_fastfail}",
            f"  After dedup: {self.items_after_dedup}",
            f"  In digest: {self.items_in_digest}",
            f"  LLM calls: {self.llm_calls} (retries: {self.llm_retries}, fallbacks: {self.llm_fallbacks})",
            f"  Errors: {len(self.errors)}",
        ]
        return "\n".join(lines)
