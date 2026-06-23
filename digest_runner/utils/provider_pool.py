"""
digest_runner/utils/provider_pool.py
=====================================
Thread-safe LLM provider rotation pool with global rate limiting.

Key features:
  - Global semaphore: max 1 concurrent LLM call at a time (serializes across all 7 parallel subgraphs)
  - Per-provider rate window: tracks calls in a sliding window, enforces RPM limits
  - 429 cooldown: rate-limited providers are skipped for a cooldown period
  - Priority rotation: Groq → Cerebras → OpenRouter → Gemini

Usage:
    from digest_runner.utils.provider_pool import ProviderPool

    client, model, provider = ProviderPool.get_client()
    try:
        result = call_llm(client, model, ...)
        ProviderPool.mark_success(provider)
    except RateLimitError:
        ProviderPool.mark_rate_limited(provider)
        client, model, provider = ProviderPool.get_client()
        result = call_llm(client, model, ...)
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, List, Optional, Tuple

from digest_runner.schemas.digest_schemas import LLMProvider

logger = logging.getLogger(__name__)

# Priority order — Groq is the most reliable for structured output,
# Cerebras as fallback, OpenRouter last (free tier is highly constrained).
# Gemini is EXCLUDED — the free-tier API key hit permanent quota exhaustion.
DEFAULT_PROVIDER_ORDER: List[LLMProvider] = [
    LLMProvider.OLLAMA,
    LLMProvider.GITHUB,
    LLMProvider.GROQ,
    LLMProvider.GEMINI,
    LLMProvider.CEREBRAS,
    LLMProvider.OPENROUTER,
    LLMProvider.SAMBANOVA,
]

# Per-provider RPM limits (requests per minute)
_PROVIDER_RPM: dict[LLMProvider, int] = {
    LLMProvider.OLLAMA: 20,
    LLMProvider.GITHUB: 15,
    LLMProvider.GROQ: 28,        # Groq free = 30 RPM, leave 2 headroom
    LLMProvider.GEMINI: 15,
    LLMProvider.CEREBRAS: 25,    # Cerebras free = 30 RPM
    LLMProvider.OPENROUTER: 15,  # OpenRouter free = 20 RPM
    LLMProvider.SAMBANOVA: 15,   # SambaNova free tier
}

_round_robin_index = 0

# How long to wait before retrying a rate-limited provider (seconds)
COOLDOWN_SECONDS = 65

# Minimum seconds between ANY two LLM calls globally (prevents burst)
MIN_CALL_INTERVAL_SECONDS = 3.0


class ProviderPool:
    """
    Thread-safe provider rotation with per-provider 429 cooldown tracking
    AND global rate limiting to prevent parallel subgraphs from overwhelming
    free-tier API limits.
    """

    _lock = threading.Lock()
    # Global semaphore: only 1 LLM call at a time across all threads
    _semaphore = threading.Semaphore(1)
    # Timestamp of last LLM call (any provider)
    _last_call_time: float = 0.0
    # provider -> timestamp after which it can be retried
    _cooldowns: dict[LLMProvider, float] = {}
    # provider -> deque of call timestamps (sliding window for RPM tracking)
    _call_windows: dict[LLMProvider, deque] = {
        p: deque() for p in LLMProvider
    }

    @classmethod
    def _wait_for_rate_window(cls, provider: LLMProvider) -> None:
        """Wait if we'd exceed the provider's RPM limit."""
        rpm = _PROVIDER_RPM.get(provider, 20)
        window = cls._call_windows.get(provider)
        if window is None:
            cls._call_windows[provider] = deque()
            window = cls._call_windows[provider]

        now = time.time()
        # Purge entries older than 60 seconds
        while window and window[0] < now - 60:
            window.popleft()

        if len(window) >= rpm:
            # Must wait until the oldest call in the window expires
            wait = window[0] + 60 - now + 0.5  # +0.5s buffer
            if wait > 0:
                logger.info(
                    "ProviderPool: %s at RPM limit (%d/%d), waiting %.1fs",
                    provider.value, len(window), rpm, wait,
                )
                time.sleep(wait)
                # Re-purge after sleep
                now = time.time()
                while window and window[0] < now - 60:
                    window.popleft()

    @classmethod
    def _enforce_min_interval(cls) -> None:
        """Ensure minimum time between any two LLM calls globally."""
        now = time.time()
        elapsed = now - cls._last_call_time
        if elapsed < MIN_CALL_INTERVAL_SECONDS:
            sleep_time = MIN_CALL_INTERVAL_SECONDS - elapsed
            time.sleep(sleep_time)

    @classmethod
    def acquire(cls, provider: LLMProvider) -> None:
        """Acquire the global semaphore and wait for rate limits."""
        cls._semaphore.acquire()
        try:
            with cls._lock:
                cls._enforce_min_interval()
                cls._wait_for_rate_window(provider)
                # Record the call
                now = time.time()
                cls._last_call_time = now
                cls._call_windows.setdefault(provider, deque()).append(now)
        except Exception:
            cls._semaphore.release()
            raise

    @classmethod
    def release(cls) -> None:
        """Release the global semaphore after an LLM call completes."""
        cls._semaphore.release()

    @classmethod
    def available_providers(cls, order: Optional[List[LLMProvider]] = None) -> List[LLMProvider]:
        """Return providers not currently in cooldown, in priority order."""
        now = time.time()
        with cls._lock:
            return [
                p for p in (order or DEFAULT_PROVIDER_ORDER)
                if cls._cooldowns.get(p, 0) <= now
            ]

    @classmethod
    def get_client(
        cls,
        order: Optional[List[LLMProvider]] = None,
    ) -> Tuple[Any, str, LLMProvider]:
        """
        Try providers in round-robin order, skipping any in cooldown.
        Returns (instructor_client, model_name, provider_enum).
        Raises RuntimeError if all providers are unavailable.
        """
        from digest_runner.subgraphs.base import get_instructor_client
        global _round_robin_index

        base_order = order or DEFAULT_PROVIDER_ORDER
        
        with cls._lock:
            # Shift order to start at current round robin index
            shifted_order = base_order[_round_robin_index:] + base_order[:_round_robin_index]
            _round_robin_index = (_round_robin_index + 1) % len(base_order)
            
        available = [p for p in shifted_order if cls._cooldowns.get(p, 0) <= time.time()]
        
        if not available:
            with cls._lock:
                soonest = min(cls._cooldowns.values(), default=0)
            wait = max(0, soonest - time.time())
            if wait > 0:
                logger.warning("ProviderPool: all providers in cooldown, waiting %.0fs", wait)
                time.sleep(wait)
            available = [p for p in shifted_order if cls._cooldowns.get(p, 0) <= time.time()]

        errors = []
        for provider in available:
            try:
                client, model = get_instructor_client(provider)
                logger.debug("ProviderPool: using %s (%s)", provider.value, model)
                return client, model, provider
            except Exception as exc:
                errors.append(f"{provider.value}: {exc}")
                continue

        raise RuntimeError(
            f"ProviderPool: all providers unavailable. Errors: {'; '.join(errors)}"
        )

    @classmethod
    def mark_rate_limited(cls, provider: LLMProvider, cooldown_secs: float = COOLDOWN_SECONDS) -> None:
        """Mark a provider as rate-limited. Skipped for cooldown_secs seconds."""
        with cls._lock:
            cls._cooldowns[provider] = time.time() + cooldown_secs
        logger.warning(
            "ProviderPool: %s rate-limited — cooling down for %.0fs",
            provider.value, cooldown_secs,
        )

    @classmethod
    def mark_success(cls, provider: LLMProvider) -> None:
        """Clear any cooldown for a provider after a successful call."""
        with cls._lock:
            cls._cooldowns.pop(provider, None)

    @classmethod
    def reset(cls) -> None:
        """Reset all state. Useful between test runs."""
        with cls._lock:
            cls._cooldowns.clear()
            cls._call_windows = {p: deque() for p in LLMProvider}
            cls._last_call_time = 0.0

    @classmethod
    def status(cls) -> dict[str, str]:
        """Return current cooldown status for all providers."""
        now = time.time()
        with cls._lock:
            result = {}
            for p in DEFAULT_PROVIDER_ORDER:
                until = cls._cooldowns.get(p, 0)
                window = cls._call_windows.get(p, deque())
                active = sum(1 for t in window if t > now - 60)
                rpm = _PROVIDER_RPM.get(p, 20)
                if until <= now:
                    result[p.value] = f"available ({active}/{rpm} RPM)"
                else:
                    result[p.value] = f"cooling down ({until - now:.0f}s remaining, {active}/{rpm} RPM)"
            return result


def is_rate_limit_error(exc: Exception) -> bool:
    """Returns True if the exception is a rate limit / quota exhausted / overloaded error."""
    msg = str(exc).lower()
    return any(indicator in msg for indicator in [
        "429",
        "rate limit",
        "rate_limit",
        "quota",
        "resource_exhausted",
        "too many requests",
        "tokens per minute",
        "requests per minute",
        "high traffic",
        "503",
        "service unavailable",
        "high demand",
        "overloaded",
    ])


def is_provider_broken(exc: Exception) -> bool:
    """
    Returns True if the exception indicates a permanent provider config error
    (wrong model name, bad endpoint, auth failure) rather than temporary load.
    Only matches HTTP-level errors (Error code: 404/401/403), not schema
    validation failures that happen to contain those keywords.
    """
    msg = str(exc).lower()
    # Match specific HTTP error code patterns from OpenAI client
    return any(indicator in msg for indicator in [
        "error code: 404",
        "error code: 401",
        "error code: 403",
        "model not found",
        "invalid api key",
        "authentication failed",
    ])

