"""
MCP wire schemas — shared by all /fetch/* endpoints.

Strict Pydantic v2 validation for API responses (DigestItem, SourceResponse).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

# Canonical MCP source literal (must match FastMCP / LangGraph runner expectations).
SourceName = Literal[
    "arxiv",
    "github",
    "hackernews",
    "reddit",
    "huggingface",
    "rss_feeds",
    "stackoverflow",
]


class DigestItem(BaseModel):
    """One normalized item returned by any MCP fetch tool."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    id: Annotated[
        str,
        Field(
            min_length=4,
            max_length=256,
            description="Stable identifier, typically <source>:<opaque_key>.",
            examples=["rss:a1b2c3d4e5f678901234"],
        ),
    ]
    source: Annotated[
        SourceName,
        Field(description="MCP source key for this item."),
    ]
    title: Annotated[
        str,
        Field(
            min_length=3,
            max_length=512,
            description="Human-readable title; RSS entry title or similar.",
        ),
    ]
    url: Annotated[
        HttpUrl,
        Field(description="Canonical HTTP(S) URL for the resource."),
    ]
    content: Annotated[
        str,
        Field(
            min_length=10,
            max_length=12_000,
            description="Cleaned excerpt or body for LLM consumption (HTML stripped).",
        ),
    ]
    published_at: Annotated[
        datetime,
        Field(description="Publication datetime; timezone-aware UTC preferred."),
    ]
    category: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="High-level type, e.g. article, paper, post.",
            examples=["article"],
        ),
    ]
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific metadata (feed title, tags, etc.).",
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def _metadata_none_to_empty(cls, v: Any) -> Dict[str, Any]:
        if v is None:
            return {}
        return v


class SourceResponse(BaseModel):
    """Standard response envelope for every fetch endpoint."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    source: Annotated[
        SourceName,
        Field(description="Which source produced this response."),
    ]
    items: List[DigestItem] = Field(
        default_factory=list,
        description="Successfully normalized items.",
    )
    total_fetched: Annotated[
        int,
        Field(
            ge=0,
            description="Count of items in `items` after successful normalization.",
        ),
    ] = 0
    fetch_timestamp: Annotated[
        datetime,
        Field(description="UTC time when the fetch completed."),
    ]
    errors: List[str] = Field(
        default_factory=list,
        description="Per-feed or per-item error messages; empty if none.",
    )

    @field_validator("errors", mode="after")
    @classmethod
    def _cap_error_length(cls, v: List[str]) -> List[str]:
        return [e[:200] if len(e) > 200 else e for e in v]
