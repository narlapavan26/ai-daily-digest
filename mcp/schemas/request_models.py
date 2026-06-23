"""
Strict request bodies for MCP POST endpoints.
"""

from __future__ import annotations

from typing import Annotated, Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

# pyrefly: ignore [missing-import]
from rss_feed_catalog import VERIFIED_CATALOG_FEED_COUNT, catalog_urls


class RssFetchRequest(BaseModel):
    """
    Request body for POST /fetch/rss.

    All strings are stripped; unknown fields are rejected (extra='forbid').

    **Default feeds:** When ``use_verified_catalog`` is true and ``feed_urls`` is omitted or empty,
    the server uses the same verified list as ``tests/test_rss_feeds.py`` /
    ``mcp/rss_feed_catalog.py`` (currently {n} sources).
    """.format(n=VERIFIED_CATALOG_FEED_COUNT)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    feed_urls: Annotated[
        Optional[List[HttpUrl]],
        Field(
            default=None,
            max_length=200,
            description=(
                "Explicit RSS/Atom URLs. If null or empty and use_verified_catalog is true, "
                f"the verified catalog is used ({VERIFIED_CATALOG_FEED_COUNT} feeds)."
            ),
        ),
    ] = None

    use_verified_catalog: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "If true and feed_urls is null or empty, expand to the verified AI/ML digest "
                "catalog (same URLs/sections as tests/test_rss_feeds.py feeds_to_collect)."
            ),
        ),
    ] = True

    max_items_per_feed: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=50,
            description="Maximum entries to process per feed after date filter.",
        ),
    ] = 10

    max_total_items: Annotated[
        int,
        Field(
            default=5000,
            ge=10,
            le=20_000,
            description="Hard cap on total DigestItem rows returned (safety for large catalog runs).",
        ),
    ] = 5000

    fetch_concurrency: Annotated[
        int,
        Field(
            default=16,
            ge=1,
            le=32,
            description="Parallel HTTP workers when fetching multiple feeds (matches test suite style).",
        ),
    ] = 16

    days_back: Annotated[
        int,
        Field(
            default=7,
            ge=1,
            le=30,
            description="Only include entries published within this many days (UTC window).",
        ),
    ] = 7

    request_timeout_seconds: Annotated[
        float,
        Field(
            default=30.0,
            ge=5.0,
            le=120.0,
            description="HTTP timeout per feed request.",
        ),
    ] = 30.0

    max_redirects: Annotated[
        int,
        Field(
            default=5,
            ge=1,
            le=10,
            description="Maximum redirects when fetching feed XML.",
        ),
    ] = 5

    user_agent: Annotated[
        str,
        Field(
            default="AIDigest-MCP-RSS/1.0 (+https://github.com/ai-daily-digest)",
            min_length=16,
            max_length=256,
            description="User-Agent sent when downloading feeds (many servers require a descriptive UA).",
        ),
    ] = "AIDigest-MCP-RSS/1.0 (+https://github.com/ai-daily-digest)"

    @model_validator(mode="before")
    @classmethod
    def _apply_verified_catalog(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        use_cat = data.get("use_verified_catalog", True)
        raw_urls = data.get("feed_urls")
        empty = raw_urls is None or (isinstance(raw_urls, list) and len(raw_urls) == 0)
        if use_cat and empty:
            data["feed_urls"] = catalog_urls()
        elif not use_cat and empty:
            raise ValueError(
                "feed_urls must be non-empty when use_verified_catalog is false."
            )
        return data

    @field_validator("feed_urls", mode="after")
    @classmethod
    def _unique_feed_urls(cls, v: Optional[List[HttpUrl]]) -> List[HttpUrl]:
        if not v:
            raise ValueError("feed_urls resolved empty after catalog expansion.")
        seen: set[str] = set()
        ordered: List[HttpUrl] = []
        for url in v:
            key = str(url).strip().rstrip("/").lower()
            if key in seen:
                raise ValueError(f"Duplicate feed URL after normalization: {url}")
            seen.add(key)
            ordered.append(url)
        return ordered
