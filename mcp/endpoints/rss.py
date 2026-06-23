"""
POST /fetch/rss — fetch RSS/Atom feeds via httpx + feedparser, return SourceResponse.

Uses the same verified URL catalog as ``tests/test_rss_feeds.py`` (see ``mcp/rss_feed_catalog.py``)
when ``use_verified_catalog`` is true (default).
"""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, List, Tuple

import feedparser
import httpx
from fastapi import APIRouter

# pyrefly: ignore [missing-import]
from rss_feed_catalog import catalog_lookup_by_url
# pyrefly: ignore [missing-import]
from schemas.common import DigestItem, SourceResponse
# pyrefly: ignore [missing-import]
from schemas.request_models import RssFetchRequest
# pyrefly: ignore [missing-import]
from utils.text_cleaning import clean_html, clean_latex, truncate_at_sentence

router = APIRouter(prefix="/fetch", tags=["sources"])

_CATALOG_LOOKUP = catalog_lookup_by_url()


def _normalize_link(entry: Any) -> str:
    link = (getattr(entry, "link", None) or "").strip()
    if link:
        return link
    links = getattr(entry, "links", None) or []
    if links and isinstance(links, list):
        href = links[0].get("href") if isinstance(links[0], dict) else None
        if href:
            return str(href).strip()
    return ""


def _entry_raw_summary(entry: Any) -> str:
    content = getattr(entry, "content", None)
    if content and isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and first.get("value"):
            return str(first["value"])
    for key in ("summary", "description"):
        val = getattr(entry, key, None)
        if val:
            return str(val)
    return ""


def _struct_time_to_datetime(st: Any) -> datetime | None:
    if not st:
        return None
    try:
        return datetime(*st[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _parse_published(entry: Any) -> datetime | None:
    st = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    dt = _struct_time_to_datetime(st)
    if dt is not None:
        return dt
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if not raw or not isinstance(raw, str):
            continue
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (TypeError, ValueError):
            continue
    return None


def _stable_item_id(link: str) -> str:
    norm = link.split("#", 1)[0].strip()
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:20]
    return f"rss:{digest}"


def _meta_for_feed_url(url_str: str) -> Tuple[str, str]:
    key = url_str.strip().rstrip("/").lower()
    return _CATALOG_LOOKUP.get(key, ("Unknown", "Unknown"))


def _process_one_feed(
    url_str: str,
    req: RssFetchRequest,
    cutoff: datetime,
    now: datetime,
) -> Tuple[List[DigestItem], List[str]]:
    """Fetch one feed XML and emit DigestItem rows (or errors). Thread-safe: own httpx client."""
    catalog_feed, section = _meta_for_feed_url(url_str)
    items_local: List[DigestItem] = []
    errors_local: List[str] = []

    headers = {
        "User-Agent": req.user_agent,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, application/rdf+xml, text/xml;q=0.9, */*;q=0.8",
    }

    try:
        with httpx.Client(
            timeout=req.request_timeout_seconds,
            headers=headers,
            follow_redirects=True,
            max_redirects=req.max_redirects,
            limits=httpx.Limits(max_connections=5),
        ) as client:
            resp = client.get(url_str)
            if resp.status_code != 200:
                errors_local.append(f"{url_str}: HTTP {resp.status_code}")
                return items_local, errors_local

            parsed = feedparser.parse(resp.text)
            if getattr(parsed, "bozo", False) and not parsed.entries:
                errors_local.append(
                    f"{url_str}: feedparse error — {getattr(parsed, 'bozo_exception', 'malformed XML')}"
                )
                return items_local, errors_local

            feed_title = ""
            if getattr(parsed, "feed", None):
                feed_title = (getattr(parsed.feed, "title", None) or "").strip() or "Unknown feed"

            seen_in_feed: set[str] = set()
            count = 0

            for entry in parsed.entries:
                if count >= req.max_items_per_feed:
                    break

                link = _normalize_link(entry)
                if not link:
                    errors_local.append(f"{url_str}: entry missing link; skipped")
                    continue

                dedupe = link.lower().rstrip("/")
                if dedupe in seen_in_feed:
                    continue
                seen_in_feed.add(dedupe)

                published_at = _parse_published(entry)
                if published_at is None:
                    published_at = now
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
                if published_at < cutoff:
                    continue

                title = (getattr(entry, "title", None) or "Untitled").strip()
                if len(title) < 3:
                    title = (title + "…") if title else "Untitled"
                    if len(title) < 3:
                        title = "Untitled"

                raw_summary = _entry_raw_summary(entry)
                cleaned = clean_latex(clean_html(raw_summary))
                content = truncate_at_sentence(cleaned, limit=2400)

                if len(content) < 10:
                    filler = clean_html((getattr(entry, "title", None) or "") + ". " + link)
                    content = truncate_at_sentence(filler, limit=500)
                if len(content) < 10:
                    errors_local.append(
                        f"{url_str}: entry content too short after cleaning; link={link[:80]}"
                    )
                    continue

                try:
                    items_local.append(
                        DigestItem(
                            id=_stable_item_id(link),
                            source="rss_feeds",
                            title=title[:512],
                            url=link,
                            content=content[:12_000],
                            published_at=published_at,
                            category="article",
                            metadata={
                                "feed": catalog_feed[:256],
                                "section": section[:128],
                                "feed_title": feed_title[:256],
                                "feed_url": url_str,
                                "entry_id": (getattr(entry, "id", None) or link)[:512],
                            },
                        )
                    )
                    count += 1
                except Exception as exc:
                    errors_local.append(
                        f"{url_str}: DigestItem validation failed for {link[:80]}: {exc}"
                    )

    except httpx.HTTPError as exc:
        errors_local.append(f"{url_str}: HTTP error: {exc}")
    except Exception as exc:
        errors_local.append(f"{url_str}: unexpected error: {exc}")

    return items_local, errors_local


@router.post("/rss", response_model=SourceResponse)
def fetch_rss(req: RssFetchRequest) -> SourceResponse:
    """
    Download feeds (parallel workers), parse entries, normalize to DigestItem.

    Default: all URLs in ``rss_feed_catalog.RSS_VERIFIED_FEEDS`` (same as ``tests/test_rss_feeds.py``).
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=req.days_back)

    items: List[DigestItem] = []
    errors: List[str] = []

    feed_urls = [str(u) for u in req.feed_urls]
    workers = min(req.fetch_concurrency, max(1, len(feed_urls)))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_process_one_feed, url_str, req, cutoff, now): url_str
            for url_str in feed_urls
        }
        for fut in as_completed(futures):
            try:
                batch_items, batch_errs = fut.result()
                items.extend(batch_items)
                errors.extend(batch_errs)
            except Exception as exc:
                errors.append(f"{futures[fut]}: worker error: {exc}")

    items.sort(key=lambda i: i.published_at, reverse=True)
    if len(items) > req.max_total_items:
        items = items[: req.max_total_items]
        errors.append(
            f"Truncated to max_total_items={req.max_total_items} after merge (newest first)."
        )

    return SourceResponse(
        source="rss_feeds",
        items=items,
        total_fetched=len(items),
        fetch_timestamp=now,
        errors=errors,
    )
