"""
POST /fetch/huggingface — fetch trending HuggingFace Hub models and blog posts.

Two data sources are queried per request:
  1. **Trending models** – HuggingFace Hub REST API
     ``GET https://huggingface.co/api/models?sort=trending&limit=N``
     Optionally filtered by ``pipeline_tag`` (task).
  2. **HF blog posts** – Atom/RSS feed
     ``https://huggingface.co/blog/feed.xml`` parsed with feedparser.

Both result sets are filtered to the ``days_back`` recency window and
returned as :class:`~schemas.common.DigestItem` rows inside a
:class:`~schemas.common.SourceResponse`.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import feedparser
import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

# pyrefly: ignore [missing-import]
from schemas.common import DigestItem, SourceResponse
# pyrefly: ignore [missing-import]
from utils.text_cleaning import clean_html, truncate_at_sentence

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/fetch", tags=["sources"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HF_API_MODELS_URL = "https://huggingface.co/api/models"
_HF_BLOG_FEED_URL = "https://huggingface.co/blog/feed.xml"
_USER_AGENT = (
    "ai-daily-digest/1.0 (MCP fetch bot; +https://github.com/your-org/ai-daily-digest)"
)
_REQUEST_TIMEOUT = 20.0  # seconds

# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class HuggingFaceFetchRequest(BaseModel):
    """Request body for POST /fetch/huggingface."""

    task_filter: Optional[str] = Field(
        default=None,
        description=(
            "HuggingFace pipeline_tag to restrict model results "
            "(e.g. 'text-generation', 'image-classification'). "
            "When None, all trending models are returned."
        ),
        examples=["text-generation", "image-classification"],
    )
    max_models: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximum number of trending models to fetch.",
    )
    max_blog_posts: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Maximum number of HF blog posts to fetch. Set to 0 to skip.",
    )
    days_back: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Recency window: only items published within this many days are returned.",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime) -> datetime:
    """Return *dt* with UTC timezone; assume UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_hf_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 / RFC-3339 timestamp string from the HF API."""
    if not value:
        return None
    # HF returns strings like "2024-04-12T08:30:00.000Z"
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            return _ensure_utc(dt)
        except ValueError:
            continue
    return None


def _sha256_prefix(text: str, length: int = 20) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _struct_time_to_datetime(st: Any) -> Optional[datetime]:
    """Convert a time.struct_time (from feedparser) to a UTC datetime."""
    if not st:
        return None
    try:
        return datetime(*st[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _build_model_content(model: Dict[str, Any]) -> str:
    """Assemble a readable content string from Hub API model fields."""
    model_id: str = model.get("modelId") or model.get("id") or "unknown"
    downloads: int = model.get("downloads", 0) or 0
    likes: int = model.get("likes", 0) or 0
    pipeline_tag: str = model.get("pipeline_tag") or "unknown"
    author: str = model.get("author") or model_id.split("/")[0]
    tags: List[str] = model.get("tags") or []
    tags_preview = ", ".join(tags[:8]) if tags else "none"
    sha: str = model.get("sha") or ""

    parts = [
        f"Model: {model_id}",
        f"Author: {author}",
        f"Task: {pipeline_tag}",
        f"Downloads (all time): {downloads:,}",
        f"Likes: {likes:,}",
        f"Tags: {tags_preview}",
    ]
    if sha:
        parts.append(f"SHA: {sha[:12]}")

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Models fetcher
# ---------------------------------------------------------------------------


def _fetch_models(
    req: HuggingFaceFetchRequest,
    cutoff: datetime,
    now: datetime,
) -> tuple[List[DigestItem], List[str]]:
    """Fetch trending models from the HuggingFace Hub API.

    Returns ``(items, errors)`` — errors are non-fatal descriptive strings.
    """
    items: List[DigestItem] = []
    errors: List[str] = []

    params: Dict[str, Any] = {
        "sort": "trending",
        "limit": req.max_models,
        "full": "true",  # include tags, downloads, likes
    }
    if req.task_filter:
        params["pipeline_tag"] = req.task_filter.strip()

    try:
        with httpx.Client(
            timeout=_REQUEST_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = client.get(_HF_API_MODELS_URL, params=params)

        if resp.status_code != 200:
            errors.append(
                f"HF Hub API returned HTTP {resp.status_code} for models endpoint"
            )
            return items, errors

        try:
            models_raw: List[Dict[str, Any]] = resp.json()
        except Exception as exc:
            errors.append(f"Failed to parse HF Hub API JSON response: {exc}")
            return items, errors

        if not isinstance(models_raw, list):
            errors.append(
                f"Unexpected HF Hub API response shape: {type(models_raw).__name__}"
            )
            return items, errors

        for model in models_raw:
            if not isinstance(model, dict):
                continue

            model_id: str = (
                model.get("modelId") or model.get("id") or ""
            ).strip()
            if not model_id:
                errors.append("HF model entry missing 'modelId'/'id'; skipped")
                continue

            # ---- published_at ----
            raw_date = model.get("lastModified") or model.get("createdAt")
            published_at = _parse_hf_datetime(raw_date) or now
            if published_at < cutoff:
                continue

            # ---- content ----
            content = _build_model_content(model)
            if len(content) < 50:
                # Pad to satisfy DigestItem min_length=10 and our own floor
                content = f"Model: {model_id} | Trending on HuggingFace Hub."

            # ---- metadata ----
            tags: List[str] = model.get("tags") or []
            metadata: Dict[str, Any] = {
                "pipeline_tag": model.get("pipeline_tag") or "",
                "downloads": model.get("downloads") or 0,
                "likes": model.get("likes") or 0,
                "author": model.get("author") or model_id.split("/")[0],
                "tags": tags[:20],  # cap to avoid metadata bloat
            }

            try:
                items.append(
                    DigestItem(
                        id=f"hf:model:{_sha256_prefix(model_id)}",
                        source="huggingface",
                        title=model_id[:512],
                        url=f"https://huggingface.co/{model_id}",
                        content=content[:12_000],
                        published_at=published_at,
                        category="model",
                        metadata=metadata,
                    )
                )
            except Exception as exc:
                errors.append(
                    f"DigestItem validation failed for model '{model_id[:80]}': {exc}"
                )

    except httpx.HTTPError as exc:
        errors.append(f"HTTP error fetching HF models: {exc}")
    except Exception as exc:
        errors.append(f"Unexpected error fetching HF models: {exc}")

    return items, errors


# ---------------------------------------------------------------------------
# Blog posts fetcher
# ---------------------------------------------------------------------------


def _fetch_blog_posts(
    req: HuggingFaceFetchRequest,
    cutoff: datetime,
    now: datetime,
) -> tuple[List[DigestItem], List[str]]:
    """Fetch recent HuggingFace blog posts via the Atom/RSS feed.

    Returns ``(items, errors)`` — errors are non-fatal descriptive strings.
    """
    items: List[DigestItem] = []
    errors: List[str] = []

    if req.max_blog_posts == 0:
        return items, errors

    try:
        with httpx.Client(
            timeout=_REQUEST_TIMEOUT,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": (
                    "application/atom+xml, application/rss+xml, "
                    "application/xml, text/xml;q=0.9, */*;q=0.8"
                ),
            },
            follow_redirects=True,
        ) as client:
            resp = client.get(_HF_BLOG_FEED_URL)

        if resp.status_code != 200:
            errors.append(
                f"HF blog feed returned HTTP {resp.status_code}"
            )
            return items, errors

        parsed = feedparser.parse(resp.text)

        if getattr(parsed, "bozo", False) and not parsed.entries:
            errors.append(
                "HF blog feed parse error: "
                + str(getattr(parsed, "bozo_exception", "malformed feed"))
            )
            return items, errors

        count = 0
        for entry in parsed.entries:
            if count >= req.max_blog_posts:
                break

            link: str = (getattr(entry, "link", None) or "").strip()
            if not link:
                errors.append("HF blog entry missing link; skipped")
                continue

            # ---- published_at ----
            st = getattr(entry, "published_parsed", None) or getattr(
                entry, "updated_parsed", None
            )
            published_at = _struct_time_to_datetime(st) or now
            if published_at < cutoff:
                continue

            # ---- title ----
            title: str = (getattr(entry, "title", None) or "Untitled").strip()
            if len(title) < 3:
                title = "HuggingFace Blog Post"

            # ---- content ----
            raw_summary = ""
            # feedparser may store full content in entry.content list
            content_list = getattr(entry, "content", None)
            if content_list and isinstance(content_list, list):
                first = content_list[0]
                if isinstance(first, dict) and first.get("value"):
                    raw_summary = str(first["value"])
            if not raw_summary:
                raw_summary = (
                    getattr(entry, "summary", None)
                    or getattr(entry, "description", None)
                    or ""
                )
            content = truncate_at_sentence(clean_html(raw_summary), limit=2000)
            if len(content) < 10:
                content = f"{title}. Read more at {link}"

            # ---- metadata ----
            author: str = ""
            author_detail = getattr(entry, "author_detail", None)
            if isinstance(author_detail, dict):
                author = author_detail.get("name", "") or ""
            if not author:
                author = getattr(entry, "author", None) or ""

            tags_raw = getattr(entry, "tags", None) or []
            tags: List[str] = [
                t.get("term", "") for t in tags_raw if isinstance(t, dict)
            ]

            metadata: Dict[str, Any] = {
                "author": author,
                "tags": [t for t in tags if t],
            }

            try:
                items.append(
                    DigestItem(
                        id=f"hf:blog:{_sha256_prefix(link)}",
                        source="huggingface",
                        title=title[:512],
                        url=link,
                        content=content[:12_000],
                        published_at=published_at,
                        category="blog_post",
                        metadata=metadata,
                    )
                )
                count += 1
            except Exception as exc:
                errors.append(
                    f"DigestItem validation failed for blog post '{link[:80]}': {exc}"
                )

    except httpx.HTTPError as exc:
        errors.append(f"HTTP error fetching HF blog feed: {exc}")
    except Exception as exc:
        errors.append(f"Unexpected error fetching HF blog feed: {exc}")

    return items, errors


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/huggingface", response_model=SourceResponse)
def fetch_huggingface(req: HuggingFaceFetchRequest) -> SourceResponse:
    """Fetch trending HuggingFace models and recent blog posts.

    **Models** are pulled from the HuggingFace Hub REST API, sorted by
    trending score.  Pass ``task_filter`` to restrict results to a specific
    ML task (e.g. ``"text-generation"``).

    **Blog posts** are parsed from the official HuggingFace blog Atom feed.
    Set ``max_blog_posts=0`` to skip the blog entirely.

    Both result sets are filtered to the ``days_back`` recency window.
    Partial failures (e.g. blog feed down) are recorded in ``errors`` but
    do not prevent the other source from returning results.
    """
    now = _utcnow()
    cutoff = now - timedelta(days=req.days_back)

    all_items: List[DigestItem] = []
    all_errors: List[str] = []

    # ---- Trending models ----
    model_items, model_errors = _fetch_models(req, cutoff, now)
    all_items.extend(model_items)
    all_errors.extend(model_errors)

    # ---- Blog posts ----
    blog_items, blog_errors = _fetch_blog_posts(req, cutoff, now)
    all_items.extend(blog_items)
    all_errors.extend(blog_errors)

    # Sort newest-first across both result sets
    all_items.sort(key=lambda item: item.published_at, reverse=True)

    return SourceResponse(
        source="huggingface",
        items=all_items,
        total_fetched=len(all_items),
        fetch_timestamp=now,
        errors=all_errors,
    )
