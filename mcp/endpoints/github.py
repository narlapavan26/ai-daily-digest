"""
mcp/endpoints/github.py
========================
FastAPI router for POST /fetch/github.

Fetches trending AI/ML repositories from the GitHub REST API, plus recent
releases from a fixed set of major frameworks. Returns SourceResponse.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

# pyrefly: ignore [missing-import]
from schemas.common import DigestItem, SourceResponse
# pyrefly: ignore [missing-import]
from utils.text_cleaning import clean_markdown_excerpt, truncate_at_sentence

router = APIRouter(prefix="/fetch", tags=["sources"])


class GithubFetchRequest(BaseModel):
    topics: List[str] = Field(
        default=["llm", "agent", "rag", "langchain", "langgraph"],
        description="GitHub topic keywords to search for.",
    )
    max_results: int = Field(default=15, ge=1, le=50, description="Max total items to return.")
    days_back: int = Field(default=7, ge=1, le=30, description="Only include repos/releases within this many days.")


def _parse_iso_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@router.post("/github", response_model=SourceResponse)
def fetch_github(req: GithubFetchRequest) -> SourceResponse:
    """
    Fetch trending GitHub repositories and recent framework releases.

    1. Searches GitHub repositories by topic with stars>50 and recent activity.
    2. Fetches latest releases from major AI framework repos.
    3. Attempts to enrich repo descriptions with README excerpts.
    """
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=req.days_back)

    items:  List[DigestItem] = []
    errors: List[str]        = []

    token = (os.environ.get("GH_PAT_TOKEN") or "").strip()
    headers: Dict[str, str] = {
        "Accept":             "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        topics_clean = [t.strip() for t in req.topics if t and t.strip()] or ["llm", "agent"]
        query    = f"({' OR '.join(topics_clean)}) stars:>50 pushed:>{cutoff.date().isoformat()}"
        per_page = max(1, min(req.max_results, 10))

        with httpx.Client(timeout=20.0) as client:
            # ── 1. Trending repos ────────────────────────────────────────────
            resp = client.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc", "per_page": per_page},
                headers=headers,
            )
            if resp.status_code != 200:
                errors.append(f"GitHub repo search failed: {resp.status_code} {resp.text[:200]}")
            else:
                for r in resp.json().get("items", []):
                    if len(items) >= req.max_results:
                        break
                    try:
                        full_name    = (r.get("full_name") or "").strip()
                        url          = r.get("html_url") or ""
                        description  = (r.get("description") or "").strip()
                        stars        = int(r.get("stargazers_count") or 0)
                        forks        = int(r.get("forks_count") or 0)
                        language     = (r.get("language") or "").strip()
                        repo_topics  = r.get("topics") or []

                        if not full_name or not url:
                            continue

                        raw_dt       = r.get("pushed_at") or r.get("created_at") or ""
                        published_at = _parse_iso_dt(raw_dt) if raw_dt else now

                        content = description
                        # Enrich with README excerpt
                        try:
                            rm_headers = {"Accept": "application/vnd.github.raw+json"}
                            if token:
                                rm_headers["Authorization"] = f"Bearer {token}"
                            rm = client.get(
                                f"https://api.github.com/repos/{full_name}/readme",
                                headers=rm_headers, timeout=15.0,
                            )
                            if rm.status_code == 200:
                                excerpt = clean_markdown_excerpt(rm.text, max_chars=2000)
                                if excerpt and len(excerpt) > 10:
                                    content = f"{description}\n\n{excerpt}" if description else excerpt
                        except Exception as exc:
                            errors.append(f"README fetch failed for {full_name}: {exc}")

                        if len(content) < 10:
                            continue

                        items.append(DigestItem(
                            id=f"gh:repo:{full_name}",
                            source="github",
                            title=full_name,
                            url=url,
                            content=truncate_at_sentence(content, 4000),
                            published_at=published_at,
                            category="repo",
                            metadata={"stars": stars, "forks": forks, "language": language, "topics": repo_topics},
                        ))
                    except Exception as exc:
                        errors.append(f"Repo parse error for {r.get('full_name', '?')}: {exc}")

            # ── 2. Framework releases ────────────────────────────────────────
            frameworks = [
                "langchain-ai/langchain",
                "langchain-ai/langgraph",
                "run-llama/llama_index",
                "joaomdmoura/crewai",
                "microsoft/autogen",
                "deepset-ai/haystack",
                "vllm-project/vllm",
                "ollama/ollama",
            ]
            for repo_name in frameworks:
                if len(items) >= req.max_results:
                    break
                try:
                    rel = client.get(
                        f"https://api.github.com/repos/{repo_name}/releases/latest",
                        headers=headers, timeout=20.0,
                    )
                    if rel.status_code != 200:
                        continue
                    release = rel.json()

                    raw_dt = release.get("published_at") or ""
                    if not raw_dt:
                        continue
                    published_at = _parse_iso_dt(raw_dt)
                    if published_at < cutoff:
                        continue

                    tag  = release.get("tag_name") or ""
                    url  = release.get("html_url") or ""
                    if not url:
                        continue

                    notes       = release.get("body") or ""
                    notes_clean = clean_markdown_excerpt(notes, max_chars=2000)
                    if len(notes_clean) < 10:
                        continue

                    framework = repo_name.split("/", 1)[1] if "/" in repo_name else repo_name
                    items.append(DigestItem(
                        id=f"gh:release:{repo_name}:{tag}",
                        source="github",
                        title=f"{framework} {tag}".strip(),
                        url=url,
                        content=truncate_at_sentence(notes_clean, 4000),
                        published_at=published_at,
                        category="release",
                        metadata={"framework": framework, "repo": repo_name, "version": tag},
                    ))
                except Exception as exc:
                    errors.append(f"Release fetch failed for {repo_name}: {exc}")

    except Exception as exc:
        return SourceResponse(
            source="github", items=[], total_fetched=0, fetch_timestamp=now,
            errors=[f"GitHub fetch error: {exc}"],
        )

    return SourceResponse(
        source="github",
        items=items,
        total_fetched=len(items),
        fetch_timestamp=now,
        errors=errors,
    )
