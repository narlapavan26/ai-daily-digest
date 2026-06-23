"""
POST /fetch/stackoverflow
=========================
Fetches recent, high-quality questions from the Stack Exchange API (site=stackoverflow)
filtered by tag(s), score threshold, and a look-back window. Each question is
optionally enriched with its top-voted accepted answer body, then normalised into a
:class:`~schemas.common.DigestItem` before being wrapped in a
:class:`~schemas.common.SourceResponse`.

Stack Exchange API notes
------------------------
* Base URL: ``https://api.stackexchange.com/2.3``
* The API returns gzip-compressed JSON automatically; **httpx** transparently
  decompresses it (``Accept-Encoding: gzip`` is added by default).
* The free, unauthenticated tier permits ~300 requests/day per IP (per-site).
  Quota is embedded in every response under ``quota_remaining``; this module
  logs a warning when it falls below a safety margin.
* ``filter=withbody`` is required to receive HTML ``body`` fields.
* ``fromdate`` / ``todate`` are Unix epoch integers (UTC).
* Multiple tags joined with ``;`` means **AND**-semantics in the ``tagged=``
  param. To get OR-semantics, we make **separate API calls per tag** and
  deduplicate by ``question_id`` in Python.

Error handling
--------------
* Network errors are caught and appended to ``errors``; processing continues
  for remaining questions.
* Items that fail :class:`~schemas.common.DigestItem` validation are skipped
  and their errors are recorded.
* ``quota_remaining`` < 10 appends a warning to ``errors`` but never aborts.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

# pyrefly: ignore [missing-import]
from schemas.common import DigestItem, SourceResponse
# pyrefly: ignore [missing-import]
from utils.text_cleaning import clean_html, truncate_at_sentence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STACKEXCHANGE_API_BASE = "https://api.stackexchange.com/2.3"
_QUESTIONS_URL = f"{_STACKEXCHANGE_API_BASE}/questions"
_ANSWERS_URL_TEMPLATE = f"{_STACKEXCHANGE_API_BASE}/questions/{{question_id}}/answers"

_DEFAULT_TAGS: List[str] = [
    "llm",
    "langchain",
    "openai-api",
    "huggingface",
    "pytorch",
]

# Stack Exchange uses semicolons for AND-semantics in the tagged= param.
# To get OR-semantics, we must make one API call per tag and merge.
_TAG_SEPARATOR = ";"

# Maximum characters of question body kept before appending answer text.
_QUESTION_BODY_LIMIT = 2_000
# Maximum characters of answer body appended.
_ANSWER_BODY_LIMIT = 1_500
# Hard cap passed to truncate_at_sentence for the final combined content.
_CONTENT_SENTENCE_LIMIT = 3_400

# When quota drops below this threshold we emit a warning (but do not abort).
_QUOTA_WARN_THRESHOLD = 10

# httpx timeout in seconds for all Stack Exchange calls.
_HTTP_TIMEOUT = 20.0

# User-Agent forwarded to SE API (they encourage descriptive UAs).
_USER_AGENT = "ai-daily-digest/1.0 (MCP fetch endpoint; contact: digest-bot)"

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/fetch", tags=["sources"])

# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class StackOverflowFetchRequest(BaseModel):
    """Parameters controlling the Stack Overflow fetch operation.

    Attributes:
        tags: One or more Stack Overflow tags.  The API applies OR-semantics
            when multiple tags are provided (``tagged`` param with ``;``).
        max_results: Maximum number of questions to return (1–50).
        days_back: Only include questions newer than ``days_back`` days ago.
        min_score: Minimum question score (``min`` param in the SE API).
        sort: SE sort order for questions (``votes``, ``activity``, or
            ``creation``).
    """

    tags: List[str] = Field(
        default=_DEFAULT_TAGS,
        min_length=1,
        description=(
            "Stack Overflow tags to search. Multiple tags use OR-semantics."
        ),
    )
    max_results: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum number of questions to return.",
    )
    days_back: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Return questions published within this many days.",
    )
    min_score: int = Field(
        default=5,
        description="Minimum question score threshold (upvotes − downvotes).",
    )
    sort: str = Field(
        default="votes",
        pattern="^(votes|activity|creation)$",
        description="Stack Exchange sort order: votes, activity, or creation.",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_http_client() -> httpx.Client:
    """Return a configured synchronous httpx client for Stack Exchange calls."""
    return httpx.Client(
        timeout=_HTTP_TIMEOUT,
        headers={
            "User-Agent": _USER_AGENT,
            # httpx sends Accept-Encoding: gzip, br by default; SE always gzips.
            "Accept": "application/json",
        },
        follow_redirects=True,
    )


def _check_quota(data: Dict[str, Any], errors: List[str]) -> None:
    """Emit a warning if the SE quota is close to exhaustion."""
    remaining: Optional[int] = data.get("quota_remaining")
    if remaining is not None and remaining < _QUOTA_WARN_THRESHOLD:
        msg = (
            f"Stack Exchange API quota critically low: {remaining} requests remaining."
        )
        logger.warning(msg)
        errors.append(msg)


def _fetch_questions(
    client: httpx.Client,
    req: StackOverflowFetchRequest,
    fromdate: int,
    errors: List[str],
) -> List[Dict[str, Any]]:
    """Fetch questions from SE API using per-tag calls to achieve OR-semantics.

    The SE API's ``tagged`` parameter with semicolons uses AND-semantics
    (questions must have ALL specified tags). To get OR-semantics, we make
    one API call per tag and deduplicate by ``question_id`` in Python.

    Returns the merged, deduplicated list of question dicts.
    """
    all_questions: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for tag in req.tags:
        tag = tag.strip()
        if not tag:
            continue

        params: Dict[str, Any] = {
            "site": "stackoverflow",
            "tagged": tag,
            "order": "desc",
            "sort": req.sort,
            "pagesize": min(req.max_results, 10),  # small per-tag to stay within quota
            "filter": "withbody",
            "fromdate": fromdate,
        }
        # Only add min score if > 0 (score 0 means "no filter")
        if req.min_score > 0:
            params["min"] = req.min_score

        try:
            response = client.get(_QUESTIONS_URL, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            errors.append(
                f"stackoverflow: tag '{tag}' HTTP {exc.response.status_code}: "
                f"{exc.response.text[:200]}"
            )
            continue
        except httpx.HTTPError as exc:
            errors.append(f"stackoverflow: tag '{tag}' network error: {exc}")
            continue

        try:
            data: Dict[str, Any] = response.json()
        except Exception as exc:
            errors.append(f"stackoverflow: tag '{tag}' JSON parse error: {exc}")
            continue

        _check_quota(data, errors)

        questions = data.get("items", [])
        for q in questions:
            qid = q.get("question_id")
            if qid and qid not in seen_ids:
                seen_ids.add(qid)
                all_questions.append(q)

        logger.debug(
            "stackoverflow: tag '%s' returned %d questions (%d new, quota=%s)",
            tag, len(questions), len([q for q in questions if q.get('question_id') in seen_ids]),
            data.get("quota_remaining", "?"),
        )

    logger.info(
        "stackoverflow: %d unique questions from %d tags",
        len(all_questions), len(req.tags),
    )
    return all_questions


def _fetch_top_answer_body(
    client: httpx.Client,
    question_id: int,
    errors: List[str],
) -> str:
    """Return the cleaned body of the top-voted answer, or '' on any failure."""
    url = _ANSWERS_URL_TEMPLATE.format(question_id=question_id)
    params: Dict[str, Any] = {
        "site": "stackoverflow",
        "filter": "withbody",
        "sort": "votes",
        "order": "desc",
        "pagesize": 1,
    }

    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        data: Dict[str, Any] = response.json()
    except httpx.HTTPStatusError as exc:
        errors.append(
            f"stackoverflow: answers API HTTP {exc.response.status_code} "
            f"for question {question_id}"
        )
        return ""
    except httpx.HTTPError as exc:
        errors.append(
            f"stackoverflow: answers API network error for question {question_id}: {exc}"
        )
        return ""
    except Exception as exc:
        errors.append(
            f"stackoverflow: answers JSON parse error for question {question_id}: {exc}"
        )
        return ""

    _check_quota(data, errors)

    answers: List[Dict[str, Any]] = data.get("items", [])
    if not answers:
        return ""

    top_answer = answers[0]
    raw_body: str = top_answer.get("body", "") or ""
    cleaned = clean_html(raw_body)
    return truncate_at_sentence(cleaned, limit=_ANSWER_BODY_LIMIT)


def _build_content(
    client: httpx.Client,
    question: Dict[str, Any],
    errors: List[str],
) -> Tuple[str, bool]:
    """Assemble the full content string for a question.

    Returns ``(content, ok)`` where *ok* is False if content is still < 10
    characters after all fallback attempts.
    """
    question_id: int = question["question_id"]

    # --- Question body (HTML → plain text) ---------------------------------
    raw_body: str = question.get("body", "") or ""
    question_text = clean_html(raw_body)[:_QUESTION_BODY_LIMIT]

    # --- Top answer enrichment ---------------------------------------------
    answer_text = _fetch_top_answer_body(client, question_id, errors)

    # --- Combine -----------------------------------------------------------
    if answer_text:
        combined = question_text + "\n\n[Top Answer]\n" + answer_text
    else:
        combined = question_text

    content = truncate_at_sentence(combined, limit=_CONTENT_SENTENCE_LIMIT)

    # --- Fallback: use title if body is empty/too short --------------------
    if len(content) < 10:
        title_fallback = clean_html(question.get("title", "") + ". " + question.get("link", ""))
        content = truncate_at_sentence(title_fallback, limit=500)

    if len(content) < 10:
        return "", False

    return content, True


def _question_to_digest_item(
    client: httpx.Client,
    question: Dict[str, Any],
    errors: List[str],
) -> Optional[DigestItem]:
    """Convert a raw SE question dict to a :class:`DigestItem`.

    Returns *None* and appends to *errors* if the question cannot be normalised.
    """
    question_id: int = question.get("question_id", 0)
    title: str = (question.get("title", "") or "").strip()
    link: str = (question.get("link", "") or "").strip()
    creation_epoch: int = question.get("creation_date", 0) or 0

    # --- Basic field validation --------------------------------------------
    if not question_id or not link:
        errors.append(
            f"stackoverflow: question missing id or link; skipping "
            f"(title={title[:60]!r})"
        )
        return None

    if len(title) < 3:
        title = (title + "…") if title else "Untitled question"
        if len(title) < 3:
            title = "Untitled question"

    # --- Timestamp ---------------------------------------------------------
    published_at = datetime.fromtimestamp(creation_epoch, tz=timezone.utc)

    # --- Content -----------------------------------------------------------
    content, ok = _build_content(client, question, errors)
    if not ok:
        errors.append(
            f"stackoverflow: content too short after cleaning; skipping "
            f"question_id={question_id} ({link[:80]})"
        )
        return None

    # --- Metadata ----------------------------------------------------------
    metadata: Dict[str, Any] = {
        "score": question.get("score", 0),
        "answer_count": question.get("answer_count", 0),
        "view_count": question.get("view_count", 0),
        "tags": question.get("tags", []),
        "is_answered": question.get("is_answered", False),
    }

    # --- Build DigestItem --------------------------------------------------
    try:
        return DigestItem(
            id=f"so:{question_id}",
            source="stackoverflow",
            title=title[:512],
            url=link,
            content=content[:12_000],
            published_at=published_at,
            category="question",
            metadata=metadata,
        )
    except Exception as exc:
        errors.append(
            f"stackoverflow: DigestItem validation failed for question_id="
            f"{question_id}: {exc}"
        )
        return None


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------


@router.post("/stackoverflow", response_model=SourceResponse)
def fetch_stackoverflow(req: StackOverflowFetchRequest) -> SourceResponse:
    """Fetch recent Stack Overflow questions via the Stack Exchange REST API.

    For each question that passes the score/date filters:

    1. The HTML question body is cleaned and truncated.
    2. The top-voted answer body is fetched, cleaned, and appended (when
       available) to maximise context for LLM downstream processing.
    3. The combined text is normalised into a :class:`~schemas.common.DigestItem`.

    The endpoint uses **no authentication** (Stack Exchange unauthenticated tier:
    ~300 requests/day per IP).  Gzip decompression is handled transparently by
    httpx.

    Args:
        req: Validated :class:`StackOverflowFetchRequest` from the request body.

    Returns:
        :class:`~schemas.common.SourceResponse` with ``source="stackoverflow"``.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=req.days_back)
    fromdate = int(cutoff.timestamp())

    items: List[DigestItem] = []
    errors: List[str] = []

    with _build_http_client() as client:
        # ------------------------------------------------------------------ #
        # 1. Fetch questions list                                              #
        # ------------------------------------------------------------------ #
        questions = _fetch_questions(client, req, fromdate, errors)

        if not questions:
            logger.info(
                "stackoverflow: no questions returned for tags=%s days_back=%d min_score=%d",
                req.tags,
                req.days_back,
                req.min_score,
            )
            return SourceResponse(
                source="stackoverflow",
                items=[],
                total_fetched=0,
                fetch_timestamp=now,
                errors=errors,
            )

        # ------------------------------------------------------------------ #
        # 2. Normalise each question → DigestItem                             #
        # ------------------------------------------------------------------ #
        for question in questions:
            # Guard: re-check creation_date client-side (API fromdate is
            # inclusive but can occasionally return borderline items).
            creation_epoch: int = question.get("creation_date", 0) or 0
            created_at = datetime.fromtimestamp(creation_epoch, tz=timezone.utc)
            if created_at < cutoff:
                continue

            item = _question_to_digest_item(client, question, errors)
            if item is not None:
                items.append(item)

    # ---------------------------------------------------------------------- #
    # 3. Sort newest-first and return                                          #
    # ---------------------------------------------------------------------- #
    items.sort(key=lambda i: i.published_at, reverse=True)

    logger.info(
        "stackoverflow: returning %d items (%d errors)",
        len(items),
        len(errors),
    )

    return SourceResponse(
        source="stackoverflow",
        items=items,
        total_fetched=len(items),
        fetch_timestamp=now,
        errors=errors,
    )
