"""
POST /fetch/reddit — Reddit API with optional OAuth 2.0 authentication.

Fetches posts from one or more subreddits, optionally enriching selfless posts
with top-comment bodies when ``selftext`` is absent. Returns a ``SourceResponse``
with normalized ``DigestItem`` objects ready for LLM consumption.

Design notes
------------
* Supports OAuth 2.0 'password' grant flow using REDDIT_CLIENT_ID,
  REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD env vars.
* OAuth is required since Reddit blocked unauthenticated JSON access in 2023.
  Without credentials, the endpoint returns empty results with a clear error.
* A custom ``User-Agent`` header is **required** by Reddit's API ToS.
* Rate limiting: 0.5 s sleep between every HTTP request to avoid HTTP 429.
* Comment enrichment: first 3 comments with ``body`` length > 20 chars are
  concatenated and used as fallback content for link posts.
* All text is HTML-stripped and sentence-truncated before storage.
* Validation errors per-post are captured in ``errors`` rather than raising.
"""

from __future__ import annotations

import logging
import os
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

router = APIRouter(prefix="/fetch", tags=["sources"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REDDIT_BASE = "https://www.reddit.com"
_REDDIT_OAUTH_BASE = "https://oauth.reddit.com"   # used when authenticated
_REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_USER_AGENT = "AIDigestBot/1.0 (ai-daily-digest; contact: bot@example.com)"
_REQUEST_TIMEOUT = 15.0          # seconds per individual HTTP call
_RATE_LIMIT_SLEEP = 0.5          # seconds between consecutive requests
_MAX_REDIRECTS = 5
_COMMENT_MIN_BODY = 20           # minimum characters for a comment to be used
_TOP_COMMENTS = 3                # number of top comments to concatenate
_CONTENT_TRUNCATE_LIMIT = 2_400  # characters passed to truncate_at_sentence
_CONTENT_MAX = 12_000            # hard ceiling for DigestItem.content


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class RedditFetchRequest(BaseModel):
    """Parameters for POST /fetch/reddit."""

    subreddits: List[str] = Field(
        default=["MachineLearning", "LocalLLaMA", "artificial", "mlops"],
        min_length=1,
        description="List of subreddit names (without r/ prefix) to fetch from.",
        examples=[["MachineLearning", "LocalLLaMA"]],
    )
    max_posts_per_sub: int = Field(
        default=5,
        ge=0,
        le=25,
        description="Maximum number of posts to retrieve per subreddit. Set to 0 to disable.",
    )
    days_back: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Reject posts older than this many days.",
    )
    min_score: int = Field(
        default=10,
        ge=0,
        description="Minimum Reddit score (upvotes − downvotes) for a post to be included.",
    )
    sort: str = Field(
        default="top",
        pattern=r"^(hot|top|new|rising)$",
        description="Listing sort order: hot, top, new, or rising.",
    )


# ---------------------------------------------------------------------------
# OAuth helper
# ---------------------------------------------------------------------------

def _get_oauth_token(errors: List[str]) -> Optional[str]:
    """
    Obtain an OAuth 2.0 Bearer token via Reddit's 'password' grant flow.

    Reads credentials from environment variables:
      REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD

    Returns the access token string on success, None if credentials are missing
    or if the token request fails.
    """
    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    username = os.environ.get("REDDIT_USERNAME", "").strip()
    password = os.environ.get("REDDIT_PASSWORD", "").strip()

    if not all([client_id, client_secret, username, password]):
        return None  # no credentials configured — caller handles gracefully

    try:
        resp = httpx.post(
            _REDDIT_TOKEN_URL,
            auth=(client_id, client_secret),
            data={
                "grant_type": "password",
                "username": username,
                "password": password,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=15.0,
        )
        resp.raise_for_status()
        token_data = resp.json()
        access_token = token_data.get("access_token", "")
        if not access_token:
            errors.append(f"Reddit OAuth: token response missing access_token: {token_data}")
            return None
        logger.info("Reddit OAuth: obtained access token successfully")
        return access_token
    except httpx.HTTPStatusError as exc:
        errors.append(
            f"Reddit OAuth: token request failed HTTP {exc.response.status_code}: "
            f"{exc.response.text[:200]}"
        )
        return None
    except Exception as exc:
        errors.append(f"Reddit OAuth: token request error: {exc}")
        return None


# ---------------------------------------------------------------------------
# HTTP client factory
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_client(oauth_token: Optional[str] = None) -> httpx.Client:
    """Create a shared synchronous httpx client with Reddit-appropriate headers.

    If ``oauth_token`` is provided, adds an Authorization header and sets
    the base URL to ``oauth.reddit.com`` for authenticated API access.
    """
    headers: Dict[str, str] = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }
    if oauth_token:
        headers["Authorization"] = f"Bearer {oauth_token}"
    return httpx.Client(
        headers=headers,
        timeout=_REQUEST_TIMEOUT,
        follow_redirects=True,
        max_redirects=_MAX_REDIRECTS,
    )


def _get_json(
    client: httpx.Client,
    url: str,
    errors: List[str],
    *,
    context: str = "",
) -> Optional[Any]:
    """
    GET *url* and return parsed JSON, or ``None`` on any failure.

    Appends a human-readable message to *errors* on failure.
    Sleeps ``_RATE_LIMIT_SLEEP`` seconds **after** every request (success or
    failure) to respect Reddit's rate-limit guidance.
    """
    try:
        resp = client.get(url)
        time.sleep(_RATE_LIMIT_SLEEP)  # always throttle regardless of outcome

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 10))
            logger.warning("Reddit 429 for %s — sleeping %ds", url, retry_after)
            time.sleep(retry_after)
            errors.append(f"{context}: rate-limited (429); skipped.")
            return None

        if resp.status_code != 200:
            errors.append(f"{context}: HTTP {resp.status_code} for {url}")
            return None

        return resp.json()

    except httpx.TimeoutException:
        time.sleep(_RATE_LIMIT_SLEEP)
        errors.append(f"{context}: request timed out for {url}")
        return None
    except httpx.HTTPError as exc:
        time.sleep(_RATE_LIMIT_SLEEP)
        errors.append(f"{context}: HTTP error — {exc}")
        return None
    except Exception as exc:
        time.sleep(_RATE_LIMIT_SLEEP)
        errors.append(f"{context}: unexpected error fetching {url} — {exc}")
        return None


def _fetch_top_comments(
    client: httpx.Client,
    subreddit: str,
    post_id: str,
    errors: List[str],
) -> str:
    """
    Fetch the comment listing for a post and return the concatenated bodies of
    the first ``_TOP_COMMENTS`` comments that have ``body`` length > ``_COMMENT_MIN_BODY``.

    Returns an empty string if comments cannot be retrieved.
    """
    url = f"{_REDDIT_BASE}/r/{subreddit}/comments/{post_id}.json?limit=25&sort=top"
    data = _get_json(client, url, errors, context=f"r/{subreddit}/{post_id} comments")
    if not data or not isinstance(data, list) or len(data) < 2:
        return ""

    comment_listing = data[1]
    if not isinstance(comment_listing, dict):
        return ""

    children = (
        comment_listing.get("data", {}).get("children", []) or []
    )

    bodies: List[str] = []
    for child in children:
        if len(bodies) >= _TOP_COMMENTS:
            break
        if not isinstance(child, dict):
            continue
        kind = child.get("kind", "")
        if kind != "t1":  # only real comments, not "more" stubs
            continue
        body = (child.get("data", {}) or {}).get("body", "") or ""
        body = clean_html(body.strip())
        if len(body) > _COMMENT_MIN_BODY:
            bodies.append(body)

    return " ".join(bodies)


def _build_content(
    post_data: Dict[str, Any],
    client: httpx.Client,
    subreddit: str,
    post_id: str,
    errors: List[str],
) -> str:
    """
    Build the ``content`` field for a ``DigestItem``.

    Priority:
    1. ``selftext`` (self-post body), HTML-cleaned and sentence-truncated.
    2. Title + top-3 comment bodies (for link posts or empty selftext).
    3. Title alone as last resort.
    """
    selftext = (post_data.get("selftext") or "").strip()

    # Reddit uses "[removed]" / "[deleted]" as placeholder selftext
    if selftext and selftext not in ("[removed]", "[deleted]"):
        cleaned = clean_html(selftext)
        result = truncate_at_sentence(cleaned, limit=_CONTENT_TRUNCATE_LIMIT)
        if len(result) >= 10:
            return result[:_CONTENT_MAX]

    # Fallback: title + top comments
    title = (post_data.get("title") or "").strip()
    comments = _fetch_top_comments(client, subreddit, post_id, errors)

    parts = [p for p in [title, comments] if p]
    combined = " — ".join(parts)
    combined = truncate_at_sentence(combined, limit=_CONTENT_TRUNCATE_LIMIT)

    if len(combined) >= 10:
        return combined[:_CONTENT_MAX]

    # Last resort: title only (even if short)
    return (title or "No content available.")[:_CONTENT_MAX]


def _process_subreddit(
    client: httpx.Client,
    subreddit: str,
    req: RedditFetchRequest,
    cutoff: datetime,
    now: datetime,
    oauth_token: Optional[str] = None,
) -> Tuple[List[DigestItem], List[str]]:
    """
    Fetch posts from one subreddit and return ``(items, errors)``.

    Applies score and date filters before building ``DigestItem`` objects.
    Comment enrichment is requested for every post that lacks selftext.
    Uses OAuth API base (oauth.reddit.com) when token is provided.
    """
    items: List[DigestItem] = []
    errors: List[str] = []
    context = f"r/{subreddit}"

    # Use OAuth API base when authenticated; public base otherwise
    base_url = _REDDIT_OAUTH_BASE if oauth_token else _REDDIT_BASE

    # Reddit's ?t= time filter only works with 'top'; use 'week' as safe default
    time_filter = "week" if req.sort == "top" else "all"
    url = (
        f"{base_url}/r/{subreddit}/{req.sort}.json"
        f"?limit={req.max_posts_per_sub}&t={time_filter}&raw_json=1"
    )

    data = _get_json(client, url, errors, context=context)
    if not data or not isinstance(data, dict):
        errors.append(f"{context}: unexpected listing response shape.")
        return items, errors

    children = (data.get("data") or {}).get("children") or []
    if not children:
        logger.info("%s: empty listing returned", context)
        return items, errors

    for child in children:
        if len(items) >= req.max_posts_per_sub:
            break

        if not isinstance(child, dict) or child.get("kind") != "t3":
            continue  # skip non-post kinds (e.g. stickied meta entries)

        post = child.get("data") or {}

        # ── Filters ────────────────────────────────────────────────────────
        score: int = post.get("score") or 0
        if score < req.min_score:
            continue

        created_utc: float = post.get("created_utc") or 0.0
        published_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)
        if published_at < cutoff:
            continue

        # ── Identity ───────────────────────────────────────────────────────
        post_id: str = post.get("id") or ""
        if not post_id:
            errors.append(f"{context}: post missing 'id'; skipped.")
            continue

        # ── URL ────────────────────────────────────────────────────────────
        # link posts have a meaningful 'url'; self-posts reference the permalink
        post_url: str = (post.get("url") or "").strip()
        permalink: str = post.get("permalink") or ""
        if not post_url or post_url.startswith("/r/"):
            post_url = f"{_REDDIT_BASE}{permalink}" if permalink else ""
        if not post_url:
            errors.append(f"{context}/{post_id}: no resolvable URL; skipped.")
            continue

        # ── Title ──────────────────────────────────────────────────────────
        title: str = clean_html((post.get("title") or "Untitled").strip())
        if len(title) < 3:
            title = "Untitled"

        # ── Content ────────────────────────────────────────────────────────
        content = _build_content(post, client, subreddit, post_id, errors)
        if len(content) < 10:
            errors.append(
                f"{context}/{post_id}: content too short after cleaning; skipped."
            )
            continue

        # ── Metadata ───────────────────────────────────────────────────────
        metadata: Dict[str, Any] = {
            "subreddit": post.get("subreddit") or subreddit,
            "score": score,
            "num_comments": post.get("num_comments") or 0,
            "author": post.get("author") or "[unknown]",
            "flair": post.get("link_flair_text") or "",
        }

        # ── Assemble DigestItem ────────────────────────────────────────────
        try:
            items.append(
                DigestItem(
                    id=f"reddit:{post_id}",
                    source="reddit",
                    title=title[:512],
                    url=post_url,
                    content=content,
                    published_at=published_at,
                    category="post",
                    metadata=metadata,
                )
            )
        except Exception as exc:
            errors.append(
                f"{context}/{post_id}: DigestItem validation failed — {exc}"
            )

    return items, errors


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/reddit", response_model=SourceResponse)
def fetch_reddit(req: RedditFetchRequest) -> SourceResponse:
    """
    Fetch AI/ML posts from one or more subreddits via Reddit's OAuth API.

    **OAuth credentials required.** Reddit blocked unauthenticated access in 2023.
    Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD
    in your .env file. Create an app at: https://www.reddit.com/prefs/apps

    Behaviour
    ---------
    * Obtains a short-lived OAuth Bearer token via 'password' grant before fetching.
    * Uses oauth.reddit.com (authenticated endpoint) for all listing requests.
    * Iterates over each requested subreddit sequentially to respect rate limits.
    * Posts are filtered by ``min_score`` and ``days_back`` before being included.
    * Link posts lacking ``selftext`` are enriched with the top-3 comment bodies.
    * A 0.5 s sleep is inserted after every HTTP request to respect rate limits.
    * Per-subreddit and per-post errors are captured in the ``errors`` list.
    * Returns empty results (not an error) when credentials are not configured.

    Returns
    -------
    ``SourceResponse`` with ``source="reddit"`` containing all successfully
    normalized ``DigestItem`` objects sorted newest-first.
    """
    now = _utc_now()
    cutoff = now - timedelta(days=req.days_back)

    all_items: List[DigestItem] = []
    all_errors: List[str] = []

    # ── Step 1: Obtain OAuth token ────────────────────────────────────────────
    oauth_token = _get_oauth_token(all_errors)
    if oauth_token is None:
        # Check if it's a config issue (no credentials) vs auth failure
        has_creds = all([os.environ.get(k, "").strip() for k in [
            "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
            "REDDIT_USERNAME", "REDDIT_PASSWORD",
        ]])
        if not has_creds:
            logger.warning(
                "Reddit: OAuth credentials not configured. Set REDDIT_CLIENT_ID, "
                "REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD in .env. "
                "See: https://www.reddit.com/prefs/apps"
            )
            # Return empty results gracefully (not an error - just unconfigured)
            return SourceResponse(
                source="reddit", items=[], total_fetched=0,
                fetch_timestamp=now,
                errors=["Reddit OAuth not configured - set credentials in .env to enable"],
            )
        # Auth failed despite having credentials - return with error
        return SourceResponse(
            source="reddit", items=[], total_fetched=0,
            fetch_timestamp=now,
            errors=all_errors or ["Reddit OAuth authentication failed"],
        )

    # ── Step 2: Deduplicate subreddit names ───────────────────────────────────
    seen_subs: set[str] = set()
    unique_subs = [
        s.strip()
        for s in req.subreddits
        if s.strip() and not (s.strip().lower() in seen_subs or seen_subs.add(s.strip().lower()))  # type: ignore[func-returns-value]
    ]

    # ── Step 3: Fetch from each subreddit ─────────────────────────────────────
    with _make_client(oauth_token=oauth_token) as client:
        for subreddit in unique_subs:
            if not subreddit:
                continue
            try:
                sub_items, sub_errors = _process_subreddit(
                    client, subreddit, req, cutoff, now, oauth_token=oauth_token
                )
                all_items.extend(sub_items)
                all_errors.extend(sub_errors)
                logger.info(
                    "r/%s: %d items fetched, %d errors",
                    subreddit,
                    len(sub_items),
                    len(sub_errors),
                )
            except Exception as exc:
                msg = f"r/{subreddit}: unhandled error — {exc}"
                logger.exception(msg)
                all_errors.append(msg)

    # Sort newest-first for deterministic LangGraph pipeline ordering
    all_items.sort(key=lambda i: i.published_at, reverse=True)

    return SourceResponse(
        source="reddit",
        items=all_items,
        total_fetched=len(all_items),
        fetch_timestamp=now,
        errors=all_errors,
    )
