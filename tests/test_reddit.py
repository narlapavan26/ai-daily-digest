"""
Test Reddit JSON API
No authentication required — uses public .json endpoints
"""

from __future__ import annotations

import sys

# Windows / CI: avoid UnicodeEncodeError on print(json.dumps(..., ensure_ascii=False))
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        # pyrefly: ignore [missing-attribute]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Reddit asks for a descriptive UA; bare "python-httpx" style strings are often throttled.
REDDIT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
    "AIDigestCollector/1.0 (+https://github.com/ai-daily-digest)"
)

REDDIT_BASES = (
    "https://www.reddit.com",
    "https://old.reddit.com",
)


def test_reddit():
    """Test Reddit API for AI/ML subreddits"""

    try:
        import httpx
    except ImportError:
        print("[ERROR] httpx not installed")
        print("Install with: pip install httpx")
        return

    import asyncio

    async def fetch_subreddit(subreddit: str):
        """Fetch posts from a subreddit (try multiple Reddit hosts)."""
        headers = {"User-Agent": REDDIT_UA, "Accept": "application/json"}

        last_err: str | None = None
        for base in REDDIT_BASES:
            url = f"{base}/r/{subreddit}/hot.json"
            try:
                async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                    response = await client.get(url, params={"limit": 10, "raw_json": 1})
                if response.status_code != 200:
                    last_err = f"{base} status {response.status_code}"
                    continue
                data = response.json()
                posts = data.get("data", {}).get("children", [])
                return subreddit, posts, None
            except Exception as e:
                last_err = f"{type(e).__name__}: {e!r}"
                continue
        return subreddit, None, last_err or "all_reddit_hosts_failed"

    async def test_all_subreddits():
        subreddits = [
            "MachineLearning",
            "LocalLLaMA",
            "ArtificialIntelligence",
            "deeplearning",
            "datascience",
        ]

        print("=" * 60)
        print("Testing: Reddit API")
        print("=" * 60)
        print(f"Subreddits to test: {len(subreddits)}\n")

        tasks = [fetch_subreddit(sub) for sub in subreddits]
        results = await asyncio.gather(*tasks)

        working = 0
        failed = 0
        total_posts = 0

        for subreddit, posts, error in results:
            print(f"\n{'='*60}")
            print(f"r/{subreddit}")
            print(f"{'='*60}")

            if error:
                print(f"[ERROR] Error: {error}")
                failed += 1
            elif posts is None:
                print("[ERROR] No response data")
                failed += 1
            elif len(posts) == 0:
                print("[WARN] Empty listing (0 posts) — may be rate-limited or blocked")
                failed += 1
            else:
                print(f"[OK] Found {len(posts)} hot posts")
                working += 1
                total_posts += len(posts)

                print("\nTop Posts:")
                for i, post_data in enumerate(posts[:3], 1):
                    post = post_data.get("data", {})
                    print(f"\n{i}. {post.get('title', 'N/A')[:80]}")
                    print(f"   Score: {post.get('score', 0)} | Comments: {post.get('num_comments', 0)}")
                    print(f"   URL: {post.get('url', 'N/A')[:60]}")

        print("\n" + "=" * 60)
        print("SUMMARY: REDDIT API TEST")
        print("=" * 60)
        print(f"[OK] Working subreddits: {working}/{len(subreddits)}")
        print(f"[ERROR] Failed subreddits: {failed}/{len(subreddits)}")
        print(f"Total posts collected: {total_posts}")
        print(f"[~] Average per subreddit: {total_posts/len(subreddits):.1f}")

        if working == len(subreddits):
            print("\n[OK] All subreddits accessible!")
            print(f"TIP: Estimated daily collection: ~{total_posts * 2} items")

        return working, failed

    return asyncio.run(test_all_subreddits())


def _flatten_posts(children: list) -> list[dict]:
    out: list[dict] = []
    for post_data in children:
        post = post_data.get("data", {})
        if not post:
            continue
        sub = post.get("subreddit", "") or ""
        out.append(
            {
                "subreddit": sub,
                "title": post.get("title", ""),
                "author": post.get("author", ""),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "upvote_ratio": post.get("upvote_ratio", 0),
                "link_flair_text": post.get("link_flair_text", ""),
                "url": post.get("url", ""),
                "permalink": f"https://www.reddit.com{post.get('permalink', '')}",
                "created_utc": post.get("created_utc", 0),
                "selftext": (post.get("selftext") or "")[:3000],
                "is_self": post.get("is_self", False),
                "post_id": post.get("id", ""),
            }
        )
    return out


async def _fetch_listing(client, url: str, params: dict) -> list:
    try:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("data", {}).get("children", []) or []
    except Exception:
        return []


async def collect_reddit_data(
    *,
    subreddits: list[str] | None = None,
    cutoff_days: int = 7,
    max_comment_enrich: int = 12,
) -> list[dict]:
    """Fetch posts from subreddits; optional top-comments enrichment (capped)."""
    import asyncio
    import re as _re

    import httpx

    if subreddits is None:
        subreddits = [
            "MachineLearning",
            "LocalLLaMA",
            "ArtificialIntelligence",
            "deeplearning",
            "datascience",
        ]

    headers = {"User-Agent": REDDIT_UA, "Accept": "application/json"}
    three_days_ago = __import__("time").time() - cutoff_days * 24 * 3600
    all_posts: list[dict] = []

    async with httpx.AsyncClient(
        timeout=35.0, headers=headers, follow_redirects=True
    ) as client:
        for subreddit in subreddits:
            subreddit_posts: list[dict] = []
            for base in REDDIT_BASES:
                if len(subreddit_posts) >= 8:
                    break
                for sort in ("hot", "new"):
                    url = f"{base}/r/{subreddit}/{sort}.json"
                    children = await _fetch_listing(
                        client, url, {"limit": 25, "raw_json": 1}
                    )
                    for post_data in children:
                        post = post_data.get("data", {})
                        created_utc = post.get("created_utc", 0) or 0
                        if created_utc < three_days_ago:
                            continue
                        subreddit_posts.append(
                            {
                                "subreddit": subreddit,
                                "title": post.get("title", ""),
                                "author": post.get("author", ""),
                                "score": post.get("score", 0),
                                "num_comments": post.get("num_comments", 0),
                                "upvote_ratio": post.get("upvote_ratio", 0),
                                "link_flair_text": post.get("link_flair_text", ""),
                                "url": post.get("url", ""),
                                "permalink": f"https://www.reddit.com{post.get('permalink', '')}",
                                "created_utc": created_utc,
                                "selftext": (post.get("selftext") or "")[:3000],
                                "is_self": post.get("is_self", False),
                                "post_id": post.get("id", ""),
                            }
                        )
                    if len(subreddit_posts) >= 8:
                        break

            # If date filter removed everything, take newest from /new (still bounded)
            if not subreddit_posts:
                for base in REDDIT_BASES:
                    url = f"{base}/r/{subreddit}/new.json"
                    children = await _fetch_listing(
                        client, url, {"limit": 15, "raw_json": 1}
                    )
                    subreddit_posts = _flatten_posts(children)[:12]
                    if subreddit_posts:
                        break

            all_posts.extend(subreddit_posts)

        # Enrich with top comments (sequential; capped to stay under CI timeouts)
        enriched = 0
        for post in all_posts:
            if enriched >= max_comment_enrich:
                break
            if post.get("selftext", "").strip() and post.get("is_self", False):
                continue
            if post.get("num_comments", 0) < 2:
                continue
            post_id = post.get("post_id", "")
            sub = post.get("subreddit", "")
            if not post_id or not sub:
                continue
            try:
                await asyncio.sleep(0.75)
                cmt_url = f"https://www.reddit.com/r/{sub}/comments/{post_id}.json"
                cmt_resp = await client.get(
                    cmt_url,
                    params={"limit": 8, "depth": 1, "sort": "top", "raw_json": 1},
                    timeout=20.0,
                )
                if cmt_resp.status_code == 200:
                    cmt_data = cmt_resp.json()
                    if isinstance(cmt_data, list) and len(cmt_data) > 1:
                        children = cmt_data[1].get("data", {}).get("children", [])
                        top_comments = []
                        for c in children[:5]:
                            body = c.get("data", {}).get("body", "")
                            if body and body not in ("[deleted]", "[removed]"):
                                clean = _re.sub(r"\s+", " ", body).strip()
                                if len(clean) > 20:
                                    top_comments.append(clean[:800])
                        if top_comments:
                            post["top_comments"] = top_comments
                            enriched += 1
            except Exception:
                pass

    return all_posts


if __name__ == "__main__":
    import json
    from datetime import datetime

    print("\nTEST SUITE: REDDIT API TESTING\n")

    try:
        test_reddit()
    except Exception as e:
        print(f"[WARN] Smoke test raised (continuing to data collection): {e}")

    print("\n[OK] Smoke test section done.\n")

    import asyncio

    try:
        posts_data = asyncio.run(
            collect_reddit_data(cutoff_days=7, max_comment_enrich=12)
        )
        payload = {
            "source": "reddit",
            "collected_at": datetime.now().isoformat(),
            "cutoff_days": 7,
            "total_posts": len(posts_data),
            "posts": posts_data,
        }
    except Exception as e:
        posts_data = []
        payload = {
            "source": "reddit",
            "collected_at": datetime.now().isoformat(),
            "cutoff_days": 7,
            "total_posts": 0,
            "posts": [],
            "error": f"{type(e).__name__}: {e!r}",
        }

    print("\n=== DATA OUTPUT ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    sys.exit(0)
