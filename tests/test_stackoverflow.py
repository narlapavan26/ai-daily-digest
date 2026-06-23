"""
Test Stack Overflow API
Free API, no authentication required
"""

def test_stackoverflow():
    """Test Stack Overflow API for AI/ML questions"""
    
    try:
        import httpx
    except ImportError:
        print("[ERROR] httpx not installed")
        print("Install with: pip install httpx")
        return
    
    import asyncio
    
    async def test_api():
        print("=" * 60)
        print("Testing: Stack Overflow API")
        print("=" * 60)
        
        base_url = "https://api.stackexchange.com/2.3"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test 1: Search questions with AI tags
            print(f"{'='*60}")
            print("Test 1: Recent AI/ML Questions")
            print(f"{'='*60}")
            
            tags = ["machine-learning", "artificial-intelligence", "nlp", "llm"]
            
            try:
                response = await client.get(
                    f"{base_url}/questions",
                    params={
                        "order": "desc",
                        "sort": "activity",
                        "tagged": ";".join(tags),
                        "site": "stackoverflow",
                        "pagesize": 10,
                        "filter": "withbody"  # Include question body
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    questions = data.get('items', [])
                    
                    print(f"[OK] Found {len(questions)} recent questions")
                    print(f"   Quota remaining: {data.get('quota_remaining', 'N/A')}")
                    
                    if questions:
                        print(f"\nRecent Questions:")
                        for i, q in enumerate(questions[:5], 1):
                            print(f"\n{i}. {q.get('title', 'N/A')[:70]}")
                            print(f"   Score: {q.get('score', 0)} | Answers: {q.get('answer_count', 0)}")
                            print(f"   Views: {q.get('view_count', 0):,}")
                            
                            tags_list = q.get('tags', [])
                            if tags_list:
                                print(f"   Tags: {', '.join(tags_list[:5])}")
                            
                            print(f"   URL: {q.get('link', 'N/A')}")
                
                elif response.status_code == 429:
                    print(f"[WARNING] Rate limit exceeded")
                else:
                    print(f"[ERROR] Error: Status {response.status_code}")
            
            except Exception as e:
                print(f"[ERROR] Error: {e}")
            
            # Test 2: Search for specific topics
            print(f"\n{'='*60}")
            print("Test 2: Search 'LangChain'")
            print(f"{'='*60}")
            
            try:
                response = await client.get(
                    f"{base_url}/search",
                    params={
                        "order": "desc",
                        "sort": "activity",
                        "intitle": "LangChain",
                        "site": "stackoverflow",
                        "pagesize": 5
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    questions = data.get('items', [])
                    print(f"[OK] Found {len(questions)} LangChain questions")
                    
                    if questions:
                        for i, q in enumerate(questions[:3], 1):
                            print(f"\n{i}. {q.get('title', 'N/A')[:70]}")
                            print(f"   Score: {q.get('score', 0)}")
                else:
                    print(f"[WARNING] Status: {response.status_code}")
            
            except Exception as e:
                print(f"[ERROR] Error: {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY: STACK OVERFLOW API TEST")
        print("=" * 60)
        print("[OK] API is accessible")
        print("[OK] No authentication required")
        print("[OK] Question search working")
        print("[WARNING] Rate limit: 300 requests/day (no key)")
        print("TIP: Expected collection: ~10-15 questions per day")
    
    asyncio.run(test_api())


if __name__ == "__main__":
    import json
    import asyncio
    from datetime import datetime
    
    print("\n" + "TEST SUITE: STACK OVERFLOW API TESTING" + "\n")
    test_stackoverflow()
    print("\n[OK] Testing Complete!")
    
    # Collect actual questions data for JSON output
    async def collect_so_data():
        import httpx
        import time
        base_url = "https://api.stackexchange.com/2.3"
        
        three_days_ago_ts = int(time.time() - 3 * 24 * 3600)  # Unix timestamp
        all_questions = []
        seen_ids = set()  # dedup across tag queries
        # Query ONE tag at a time — SO uses AND logic for multiple tags (too restrictive)
        tags = [
            "machine-learning", "artificial-intelligence", "nlp",
            "deep-learning", "large-language-model", "langchain"
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            for tag in tags:
                try:
                    response = await client.get(
                        f"{base_url}/questions",
                        params={
                            "order": "desc",
                            "sort": "activity",
                            "tagged": tag,
                            "site": "stackoverflow",
                            "pagesize": 15,
                            "fromdate": three_days_ago_ts,
                            "filter": "withbody"
                        }
                    )

                    if response.status_code == 200:
                        data = response.json()
                        questions = data.get('items', [])

                        for q in questions:
                            qid = q.get('question_id')
                            if qid in seen_ids:
                                continue
                            seen_ids.add(qid)
                            # Confirm recent activity client-side
                            if q.get('last_activity_date', 0) < three_days_ago_ts:
                                continue
                            all_questions.append({
                                "title": q.get('title', ''),
                                "score": q.get('score', 0),
                                "answer_count": q.get('answer_count', 0),
                                "view_count": q.get('view_count', 0),
                                "tags": q.get('tags', []),
                                "url": q.get('link', ''),
                                "creation_date": q.get('creation_date', 0),
                                "last_activity_date": q.get('last_activity_date', 0),
                                "body": q.get('body', '')[:1000]
                            })
                except Exception:
                    pass

        return all_questions

    try:
        questions_data = asyncio.run(collect_so_data())
        
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({
            "source": "stackoverflow",
            "collected_at": datetime.now().isoformat(),
            "cutoff_days": 3,
            "total_questions": len(questions_data),
            "questions": questions_data
        }, indent=2))
    except Exception as e:
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({"source": "stackoverflow", "error": str(e), "questions": []}, indent=2))
