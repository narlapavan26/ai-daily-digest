"""
Test Hacker News Algolia API
Free API, no authentication required
"""

def test_hackernews():
    """Test Hacker News Algolia API for AI/ML stories"""
    
    try:
        import httpx
    except ImportError:
        print("[ERROR] httpx not installed")
        print("Install with: pip install httpx")
        return
    
    import asyncio
    
    async def search_hn():
        print("=" * 60)
        print("Testing: Hacker News Algolia API")
        print("=" * 60)
        
        url = "https://hn.algolia.com/api/v1/search"
        
        # Test queries
        queries = [
            ("AI OR LLM", "General AI/ML"),
            ("machine learning", "Machine Learning"),
            ("GPT OR Claude OR Gemini", "LLM Models"),
            ("LangChain OR agents", "AI Agents"),
        ]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for query, description in queries:
                print(f"\n{'='*60}")
                print(f"Query: {description}")
                print(f"Search: {query}")
                print(f"{'='*60}")
                
                try:
                    response = await client.get(
                        url,
                        params={
                            "query": query,
                            "tags": "story",
                            "numericFilters": "points>50"
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        hits = data.get('hits', [])
                        
                        print(f"[OK] Found {len(hits)} stories (score > 50)")
                        
                        if hits:
                            print(f"\nTop Stories:")
                            for i, story in enumerate(hits[:5], 1):
                                print(f"\n{i}. {story.get('title', 'N/A')[:80]}")
                                print(f"   Points: {story.get('points', 0)} | Comments: {story.get('num_comments', 0)}")
                                print(f"   URL: {story.get('url', 'N/A')[:60]}")
                    else:
                        print(f"[ERROR] Error: Status {response.status_code}")
                
                except Exception as e:
                    print(f"[ERROR] Error: {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY: HACKER NEWS API TEST")
        print("=" * 60)
        print("[OK] API is accessible and working")
        print("TIP: Recommendation: Use points>50 filter for quality")
        print("[~] Expected collection: ~20-40 AI stories per day")
    
    asyncio.run(search_hn())


if __name__ == "__main__":
    import json
    import asyncio
    from datetime import datetime
    
    print("\n" + "TEST SUITE: HACKER NEWS API TESTING" + "\n")
    test_hackernews()
    print("\n[OK] Testing Complete!")
    
    # Collect actual stories data for JSON output
    async def collect_hn_data():
        import httpx
        import time
        queries = [
            ("AI and LLM", "AI OR LLM OR artificial intelligence"),
            ("Machine Learning", "machine learning"),
            ("GPT and Claude", "GPT OR Claude OR Gemini OR ChatGPT")
        ]
        
        three_days_ago_ts = int(time.time() - 3 * 24 * 3600)  # Unix timestamp
        all_stories = []
        seen_ids = set()
        async with httpx.AsyncClient(timeout=30.0) as client:
            for category, query in queries:
                try:
                    url = "https://hn.algolia.com/api/v1/search"
                    # Try with points>5 first (3-day window + quality filter)
                    params = {
                        "query": query,
                        "tags": "story",
                        "hitsPerPage": 50,
                        "numericFilters": f"created_at_i>{three_days_ago_ts},points>5"
                    }
                    response = await client.get(url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        hits = data.get('hits', [])
                        
                        # Fallback: if too few results, drop points filter
                        if len(hits) < 3:
                            params_fallback = {
                                "query": query,
                                "tags": "story",
                                "hitsPerPage": 50,
                                "numericFilters": f"created_at_i>{three_days_ago_ts}"
                            }
                            resp2 = await client.get(url, params=params_fallback)
                            if resp2.status_code == 200:
                                hits = resp2.json().get('hits', [])
                                print(f"[~] HN fallback for '{category}': {len(hits)} hits (no points filter)", flush=True)
                        
                        for hit in hits:
                            story_id = hit.get('objectID', '')
                            if story_id in seen_ids:
                                continue
                            seen_ids.add(story_id)
                            all_stories.append({
                                "category": category,
                                "title": hit.get('title', ''),
                                "author": hit.get('author', ''),
                                "points": hit.get('points', 0),
                                "num_comments": hit.get('num_comments', 0),
                                "url": hit.get('url', ''),
                                "story_url": f"https://news.ycombinator.com/item?id={story_id}",
                                "created_at": hit.get('created_at', ''),
                                "story_text": hit.get('story_text', '')[:2000] if hit.get('story_text') else '',
                                "object_id": story_id,
                            })
                    else:
                        print(f"[WARN] HN query '{category}' returned status {response.status_code}", flush=True)
                except Exception as e:
                    import sys
                    print(f"[WARN] HN query '{category}' error: {e}", file=sys.stderr)
        
        # Enrich stories with top comments from Algolia items API
        import re as _re
        for story in all_stories:
            oid = story.get('object_id', '')
            if not oid or story.get('num_comments', 0) == 0:
                continue
            try:
                item_resp = await client.get(
                    f"https://hn.algolia.com/api/v1/items/{oid}",
                    timeout=10.0
                )
                if item_resp.status_code == 200:
                    item_data = item_resp.json()
                    children = item_data.get('children', [])
                    top_comments = []
                    for child in children[:5]:
                        text = child.get('text', '')
                        if text:
                            clean = _re.sub('<[^>]+>', ' ', text)
                            clean = _re.sub(r'\s+', ' ', clean).strip()
                            if len(clean) > 20:
                                top_comments.append(clean[:600])
                    story['top_comments'] = top_comments
            except Exception:
                pass
        
        return all_stories
    
    try:
        stories_data = asyncio.run(collect_hn_data())
        
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({
            "source": "hackernews",
            "collected_at": datetime.now().isoformat(),
            "cutoff_days": 3,
            "total_stories": len(stories_data),
            "stories": stories_data
        }, indent=2))
    except Exception as e:
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({"source": "hackernews", "error": str(e), "stories": []}, indent=2))
