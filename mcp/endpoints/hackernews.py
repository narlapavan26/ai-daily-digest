"""
mcp/endpoints/hackernews.py
============================
FastAPI router for POST /fetch/hackernews.

Fetches AI/ML stories from HackerNews via the Algolia search API, enriches
with top comment snippets, returns SourceResponse.

Design notes (2026-06-22 fix):
  - Uses /search_by_date (not /search) to ensure recent stories are found.
  - Splits the query into multiple targeted sub-queries to avoid Algolia's
    poor handling of complex OR expressions.
  - Deduplicates by objectID across sub-queries.
  - Python-side points filtering with progressive fallback.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

# pyrefly: ignore [missing-import]
from schemas.common import DigestItem, SourceResponse
# pyrefly: ignore [missing-import]
from utils.text_cleaning import clean_html, truncate_at_sentence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fetch", tags=["sources"])

# ---------------------------------------------------------------------------
# Sub-queries: Each is a focused search that Algolia handles well individually.
# We run each, merge, and deduplicate by objectID.
# ---------------------------------------------------------------------------
_AI_QUERIES = [
    "AI",
    "LLM",
    "GPT",
    "machine learning",
    "language model",
    "deep learning",
    "neural network",
    "transformer model",
    "ChatGPT",
    "Claude",
    "Gemini AI",
    "agent AI",
    "RAG retrieval",
    "fine-tuning",
    "open source model",
]


class HackerNewsFetchRequest(BaseModel):
    category: str = Field(
        default="AI OR LLM OR machine learning OR agent",
        description="Search query for HN Algolia API (used as fallback if sub-queries fail).",
    )
    max_results: int = Field(default=30, ge=1, le=50, description="Max stories to return.")
    min_score: int = Field(default=10, ge=0, description="Minimum HN points to include.")
    days_back: int = Field(default=3, ge=1, le=14, description="Only include stories within this many days.")


def _search_by_date(
    client: httpx.Client,
    query: str,
    cutoff_ts: int,
    hits_per_page: int,
    errors: List[str],
) -> List[Dict[str, Any]]:
    """Run a single Algolia search_by_date query. Returns list of hit dicts."""
    try:
        resp = client.get(
            "https://hn.algolia.com/api/v1/search_by_date",
            params={
                "query": query,
                "tags": "story",
                "hitsPerPage": hits_per_page,
                "numericFilters": f"created_at_i>{cutoff_ts}",
            },
        )
        if resp.status_code != 200:
            errors.append(f"HN Algolia returned {resp.status_code} for query '{query}'")
            return []
        return resp.json().get("hits", []) or []
    except Exception as exc:
        errors.append(f"HN Algolia error for query '{query}': {exc}")
        return []


@router.post("/hackernews", response_model=SourceResponse)
def fetch_hackernews(req: HackerNewsFetchRequest) -> SourceResponse:
    """
    Fetch AI/ML HackerNews stories via Algolia API.

    Strategy:
      1. Run multiple focused sub-queries via /search_by_date (sorted by date).
      2. Merge all hits and deduplicate by objectID.
      3. Python-side points filtering with progressive fallback.
      4. Enrich each story with up to 3 top comment snippets.
    """
    now = datetime.now(timezone.utc)
    cutoff_ts = int((now - timedelta(days=req.days_back)).timestamp())

    items: List[DigestItem] = []
    errors: List[str] = []
    seen_ids: Set[str] = set()
    all_hits: List[Dict[str, Any]] = []

    try:
        with httpx.Client(timeout=25.0) as client:
            # ── Step 1: Run multiple targeted sub-queries ────────────────────
            for query in _AI_QUERIES:
                hits = _search_by_date(client, query, cutoff_ts, 20, errors)
                for hit in hits:
                    oid = str(hit.get("objectID") or "")
                    if oid and oid not in seen_ids:
                        seen_ids.add(oid)
                        all_hits.append(hit)

            logger.info("HN: %d unique hits from %d sub-queries", len(all_hits), len(_AI_QUERIES))

            # If sub-queries yielded nothing, try the original category query as fallback
            if not all_hits:
                fallback_q = req.category.strip() if req.category else "AI"
                hits = _search_by_date(client, fallback_q, cutoff_ts, 50, errors)
                for hit in hits:
                    oid = str(hit.get("objectID") or "")
                    if oid and oid not in seen_ids:
                        seen_ids.add(oid)
                        all_hits.append(hit)
                logger.info("HN: fallback query yielded %d hits", len(all_hits))

            # ── Step 2: Python-side points filter with progressive fallback ─
            if req.min_score > 0:
                filtered = [h for h in all_hits if int(h.get("points") or 0) >= req.min_score]
                if len(filtered) < 3 and req.min_score > 5:
                    filtered = [h for h in all_hits if int(h.get("points") or 0) >= 5]
                if not filtered:
                    filtered = all_hits
                all_hits = filtered

            # Sort by points descending (best stories first)
            all_hits.sort(key=lambda h: int(h.get("points") or 0), reverse=True)

            # ── Step 3: Build DigestItems with comment enrichment ───────────
            for hit in all_hits:
                if len(items) >= req.max_results:
                    break
                try:
                    object_id = str(hit.get("objectID") or "")
                    title = (hit.get("title") or "").strip()
                    if not object_id or len(title) < 3:
                        continue

                    story_url = f"https://news.ycombinator.com/item?id={object_id}"
                    external = (hit.get("url") or "").strip()
                    canon_url = external if external and external != story_url else story_url

                    points = int(hit.get("points") or 0)
                    num_comments = int(hit.get("num_comments") or 0)
                    author = (hit.get("author") or "").strip()
                    story_text = (hit.get("story_text") or "")[:2000]

                    try:
                        published_at = datetime.fromisoformat(
                            str(hit.get("created_at") or "").replace("Z", "+00:00")
                        )
                    except Exception:
                        published_at = now

                    # Enrich with top comments (only for high-signal stories)
                    top_comments: List[str] = []
                    if num_comments > 0 and points >= 5:
                        try:
                            item_resp = client.get(
                                f"https://hn.algolia.com/api/v1/items/{object_id}", timeout=15.0
                            )
                            if item_resp.status_code == 200:
                                for child in (item_resp.json().get("children", []) or [])[:5]:
                                    text = clean_html((child.get("text") or "").strip())[:600]
                                    if len(text) > 20:
                                        top_comments.append(text)
                                    if len(top_comments) >= 3:
                                        break
                        except Exception as exc:
                            errors.append(f"HN comment fetch failed for {object_id}: {exc}")

                    content = story_text if story_text else "(No story text provided by HN)"
                    if top_comments:
                        content += "\n\nTop discussion:\n" + "\n---\n".join(top_comments)
                    content = truncate_at_sentence(content, 4000)

                    if len(content) < 10:
                        continue

                    items.append(DigestItem(
                        id=f"hn:{object_id}",
                        source="hackernews",
                        title=title,
                        url=canon_url,
                        content=content,
                        published_at=published_at,
                        category="post",
                        metadata={
                            "points": points,
                            "num_comments": num_comments,
                            "author": author,
                            "category": req.category,
                        },
                    ))
                except Exception as exc:
                    errors.append(f"HN item parse error: {exc}")

    except Exception as exc:
        return SourceResponse(
            source="hackernews", items=[], total_fetched=0, fetch_timestamp=now,
            errors=[f"HN fetch error: {exc}"],
        )

    logger.info("HN: returning %d items (from %d unique hits)", len(items), len(seen_ids))

    return SourceResponse(
        source="hackernews",
        items=items,
        total_fetched=len(items),
        fetch_timestamp=now,
        errors=errors,
    )
