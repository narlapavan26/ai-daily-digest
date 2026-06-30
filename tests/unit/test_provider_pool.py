"""
tests/unit/test_provider_pool.py
==================================
Unit tests for LLM provider rotation and rate limiting.
No real API calls.
"""
from __future__ import annotations

import pytest

from digest_runner.utils.provider_pool import (
    ProviderPool,
    is_rate_limit_error,
    is_provider_broken,
    DEFAULT_PROVIDER_ORDER,
    COOLDOWN_SECONDS,
)
from digest_runner.schemas.digest_schemas import LLMProvider


class TestProviderPoolMechanics:

    def setup_method(self):
        ProviderPool.reset()

    def test_reset_clears_cooldowns(self):
        ProviderPool.mark_rate_limited(LLMProvider.GROQ, cooldown_secs=10)
        ProviderPool.reset()
        available = ProviderPool.available_providers()
        assert LLMProvider.GROQ in available

    def test_mark_rate_limited_removes_from_available(self):
        ProviderPool.mark_rate_limited(LLMProvider.GROQ, cooldown_secs=60)
        available = ProviderPool.available_providers()
        assert LLMProvider.GROQ not in available

    def test_mark_success_clears_cooldown(self):
        ProviderPool.mark_rate_limited(LLMProvider.GROQ, cooldown_secs=60)
        ProviderPool.mark_success(LLMProvider.GROQ)
        available = ProviderPool.available_providers()
        assert LLMProvider.GROQ in available

    def test_available_providers_returns_list(self):
        available = ProviderPool.available_providers()
        assert isinstance(available, list)
        assert len(available) > 0

    def test_status_returns_dict(self):
        status = ProviderPool.status()
        assert isinstance(status, dict)
        assert len(status) > 0

    def test_default_provider_order_not_empty(self):
        assert len(DEFAULT_PROVIDER_ORDER) > 0

    def test_cooldown_seconds_positive(self):
        assert COOLDOWN_SECONDS > 0


class TestRateLimitDetection:

    def test_detects_429(self):
        assert is_rate_limit_error(Exception("Error 429 too many requests"))

    def test_detects_rate_limit(self):
        assert is_rate_limit_error(Exception("rate limit exceeded"))

    def test_detects_quota(self):
        assert is_rate_limit_error(Exception("quota exhausted"))

    def test_normal_error_not_rate_limit(self):
        assert not is_rate_limit_error(Exception("connection refused"))

    def test_empty_error(self):
        assert not is_rate_limit_error(Exception(""))


class TestProviderBrokenDetection:

    def test_detects_404(self):
        assert is_provider_broken(Exception("Error code: 404"))

    def test_detects_401(self):
        assert is_provider_broken(Exception("Error code: 401"))

    def test_detects_invalid_api_key(self):
        assert is_provider_broken(Exception("invalid api key provided"))

    def test_normal_error_not_broken(self):
        assert not is_provider_broken(Exception("timeout"))
