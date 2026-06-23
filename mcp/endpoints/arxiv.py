"""
mcp/endpoints/arxiv.py
======================
FastAPI router for POST /fetch/arxiv.

Fetches recent ArXiv papers matching a query, normalizes them to DigestItem,
returns SourceResponse. Uses the official arxiv Python client.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import arxiv
from fastapi import APIRouter
from pydantic import BaseModel, Field

# pyrefly: ignore [missing-import]
from schemas.common import DigestItem, SourceResponse
# pyrefly: ignore [missing-import]
from utils.text_cleaning import clean_html, clean_latex, truncate_at_sentence

router = APIRouter(prefix="/fetch", tags=["sources"])


class ArxivFetchRequest(BaseModel):
    query: str = Field(
        default="large language models agents",
        description="ArXiv search query string.",
    )
    max_results: int = Field(default=20, ge=1, le=100, description="Max papers to fetch.")
    days_back: int = Field(default=7, ge=1, le=30, description="Only include papers within this many days.")


@router.post("/arxiv", response_model=SourceResponse)
def fetch_arxiv(req: ArxivFetchRequest) -> SourceResponse:
    """
    Fetch recent ArXiv papers matching the query, normalize to DigestItem list.

    Uses SubmittedDate sort so newest papers come first; breaks early once
    papers are older than the days_back window.
    """
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=req.days_back)

    items:  List[DigestItem] = []
    errors: List[str]        = []

    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=req.query,
            max_results=req.max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

        for paper in client.results(search):
            try:
                published = paper.published
                if getattr(published, "tzinfo", None) is None:
                    published = published.replace(tzinfo=timezone.utc)

                if published < cutoff:
                    break  # Sorted newest-first; safe to stop

                entry_id = getattr(paper, "entry_id", "") or ""
                if not entry_id:
                    errors.append("Missing paper.entry_id; skipping")
                    continue

                arxiv_id = entry_id.split("/")[-1] or ""
                if not arxiv_id:
                    errors.append(f"Could not extract arxiv_id from {entry_id}; skipping")
                    continue

                abstract = clean_latex(clean_html(getattr(paper, "summary", "") or ""))
                content  = truncate_at_sentence(abstract, 2500)
                if len(content) < 10:
                    errors.append(f"Abstract too short for {arxiv_id}; skipping")
                    continue

                authors = [a.name for a in getattr(paper, "authors", [])]

                items.append(DigestItem(
                    id=f"arxiv:{arxiv_id}",
                    source="arxiv",
                    title=str(getattr(paper, "title", "") or ""),
                    url=entry_id,
                    content=content,
                    published_at=published,
                    category="paper",
                    metadata={
                        "authors":          authors,
                        "primary_category": str(getattr(paper, "primary_category", "") or ""),
                        "pdf_url":          str(getattr(paper, "pdf_url", "") or ""),
                    },
                ))
            except Exception as exc:
                errors.append(f"Paper parse error: {exc}")
                continue

    except Exception as exc:
        return SourceResponse(
            source="arxiv",
            items=[],
            total_fetched=0,
            fetch_timestamp=now,
            errors=[f"ArXiv fetch error: {exc}"],
        )

    return SourceResponse(
        source="arxiv",
        items=items,
        total_fetched=len(items),
        fetch_timestamp=now,
        errors=errors,
    )
