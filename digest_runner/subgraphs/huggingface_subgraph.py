"""
digest_runner/subgraphs/huggingface_subgraph.py
===============================================
HuggingFace subgraph: MCP POST /fetch/huggingface → normalize → fast-fail → LLM enrich.

Two item types:
  - model (trending HF Hub models)  → category = 'model'
  - blog_post (HF blog RSS entries) → category = 'blog_post'

Budget: max 5 items (mix of models + blog posts).
Stale threshold: 7 days (model trends can be meaningful for a week).

content_for_llm strategy:
  - models:     "{model_id} | pipeline={pipeline_tag} | downloads={downloads} | likes={likes}\n{tags}"
  - blog posts: cleaned HTML summary (up to 2000 chars)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from digest_runner.schemas.digest_schemas import NormalizedItem, SourceName,FastFailBatch
from digest_runner.config.settings import settings
from digest_runner.utils.mcp_client import post_fetch
from .base import BaseSubgraph, parse_utc_dt, is_junk_release

logger = logging.getLogger(__name__)

DEFAULT_TASK_FILTER = None      # None = all tasks; e.g. "text-generation"


class HuggingFaceSubgraph(BaseSubgraph):
    """
    Fetches trending HuggingFace Hub models and recent HF blog posts.

    Usage:
        output = HuggingFaceSubgraph().run()
        output = HuggingFaceSubgraph(task_filter="text-generation", max_models=5).run()
    """

    source     = SourceName.HUGGINGFACE

    @property
    def budget(self) -> int:      # type: ignore[override]
        return settings.huggingface_budget

    @property
    def stale_days(self) -> float:  # type: ignore[override]
        return settings.huggingface_stale_days

    def __init__(
        self,
        task_filter: str | None    = DEFAULT_TASK_FILTER,
        max_models:  Optional[int] = None,
        max_blogs:   Optional[int] = None,
        days_back:   Optional[int] = None,
    ) -> None:
        self.task_filter = task_filter
        self.max_models  = max_models if max_models is not None else settings.huggingface_max_models
        self.max_blogs   = max_blogs   if max_blogs   is not None else settings.huggingface_max_blogs
        self.days_back   = days_back   if days_back   is not None else settings.huggingface_days_back

    def fetch_from_mcp(self) -> Dict[str, Any]:
        logger.info(
            "HuggingFace subgraph: fetching via MCP (task=%s, models=%d, blogs=%d)",
            self.task_filter or "all", self.max_models, self.max_blogs,
        )
        body: Dict[str, Any] = {
            "max_models":    self.max_models,
            "max_blog_posts": self.max_blogs,
            "days_back":     self.days_back,
        }
        if self.task_filter:
            body["task_filter"] = self.task_filter
        return post_fetch("/fetch/huggingface", body)

    def normalize(self, raw_items: List[Dict[str, Any]]) -> List[NormalizedItem]:
        """Map MCP DigestItem (huggingface model or blog) → NormalizedItem."""
        result: List[NormalizedItem] = []
        for row in raw_items:
            try:
                published_at = parse_utc_dt(row["published_at"])
                import datetime as _dt
                days_old = max(
                    0.0,
                    (_dt.datetime.now(_dt.timezone.utc) - published_at).total_seconds() / 86400.0,
                )
                md       = row.get("metadata") or {}
                category = str(row.get("category") or "model")
                content  = str(row.get("content") or "").strip()
                title    = str(row.get("title") or "").strip()

                if category == "model":
                    # Build rich content for LLM from structured metadata
                    pipeline  = md.get("pipeline_tag") or "unknown"
                    downloads = md.get("downloads") or 0
                    likes     = md.get("likes") or 0
                    tags      = md.get("tags_list") or []
                    tags_str  = ", ".join(str(t) for t in tags[:10]) if tags else "none"

                    content_for_llm = (
                        f"Model: {title}\n"
                        f"Task: {pipeline} | Downloads (month): {downloads:,} | Likes: {likes}\n"
                        f"Tags: {tags_str}\n"
                        f"Description: {content[:800]}"
                    )
                    quality_signals: Dict[str, Any] = {
                        "pipeline_tag": pipeline,
                        "downloads":    downloads,
                        "likes":        likes,
                        "author":       md.get("author", ""),
                        "category":     "model",
                    }
                else:
                    # Blog post — use cleaned summary.
                    # MCP sometimes returns only "Title. Read more at URL" with no body.
                    # In that case, build a richer content string from available metadata.
                    author = md.get("author", "")
                    tags   = md.get("tags", [])
                    tags_str = ", ".join(str(t) for t in tags[:10]) if tags else ""

                    if len(content) < 100:
                        # Shallow content — enrich from metadata
                        parts = [f"HuggingFace Blog: {title}"]
                        if author:
                            parts.append(f"Author: {author}")
                        if tags_str:
                            parts.append(f"Tags: {tags_str}")
                        parts.append(f"URL: {row['url']}")
                        content_for_llm = "\n".join(parts)
                    else:
                        content_for_llm = content[:2000]

                    quality_signals = {
                        "author":   author,
                        "tags":     tags,
                        "category": "blog_post",
                    }

                if len(content_for_llm) < 20:
                    continue

                result.append(NormalizedItem(
                    id=str(row["id"]),
                    source=SourceName.HUGGINGFACE,
                    title=title or "Untitled HuggingFace item",
                    url=row["url"],
                    published_at=published_at,
                    content_for_llm=content_for_llm[:2400],
                    quality_signals=quality_signals,
                    days_old=days_old,
                ))
            except Exception as exc:
                logger.warning("HuggingFace normalize error for %s: %s", row.get("id", "?"), exc)
        return result

    def fast_fail(self, normalized: List[NormalizedItem]) ->FastFailBatch:
        """
        HuggingFace-specific fast-fail (extends base stale/empty checks):
          - DROP_STALE  if days_old > stale_days
          - DROP_EMPTY  if content_for_llm < 20 chars
          - DROP_LOWSIG if category='model' AND downloads < settings.huggingface_min_downloads
            (obscure/stub models with no traction — not useful for practitioners)
        Blog posts are never filtered by the downloads check.
        """
        from digest_runner.schemas.digest_schemas import FastFailBatch, FastFailResult, FastFailVerdict

        passed:  List[NormalizedItem] = []
        dropped: List[FastFailResult] = []
        min_dl = settings.huggingface_min_downloads

        for it in normalized:
            # Global junk filter — applied before any source-specific rules
            is_junk, junk_reason = is_junk_release(it)
            if is_junk:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_LOWSIG,
                    reason=f"global_junk_filter: {junk_reason}",
                ))
                continue

            cat       = it.quality_signals.get("category", "blog_post")
            downloads = int(it.quality_signals.get("downloads", 0))

            if it.days_old > self.stale_days:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_STALE,
                    reason=f"days_old={it.days_old:.1f} > {self.stale_days}",
                    score=0.0,
                ))
            elif len(it.content_for_llm) < 20:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_EMPTY,
                    reason="content_for_llm < 20 chars",
                    score=0.0,
                ))
            elif cat == "model" and downloads < min_dl:
                dropped.append(FastFailResult(
                    item_id=it.id,
                    verdict=FastFailVerdict.DROP_LOWSIG,
                    reason=f"model downloads={downloads:,} < {min_dl:,}",
                    score=0.0,
                ))
            else:
                passed.append(it)

        n = len(normalized)
        logger.info(
            "HuggingFace fast-fail: %d passed, %d dropped (%.0f%% pass rate)",
            len(passed), len(dropped), (len(passed) / n * 100) if n else 0,
        )

        # ── Debug: dump fast-fail results to state/ ──────────────────────────
        from .base import _dump_state
        _dump_state("huggingface_0_fastfail_passed.json", [
            {"id": it.id, "title": it.title, "url": str(it.url),
             "days_old": it.days_old, "content_len": len(it.content_for_llm or ""),
             "quality_signals": it.quality_signals}
            for it in passed
        ])
        _dump_state("huggingface_0_fastfail_dropped.json", [
            {"item_id": d.item_id, "verdict": d.verdict.value if hasattr(d.verdict, 'value') else str(d.verdict),
             "reason": d.reason}
            for d in dropped
        ])

        return FastFailBatch(
            source=SourceName.HUGGINGFACE,
            passed=passed,
            dropped=dropped,
            pass_rate=(len(passed) / n) if n else 0.0,
        )
