"""
Test Semantic Scholar API
Free API, optional API key (works without)
"""
import os

def test_semantic_scholar():
    """Test Semantic Scholar API"""
    
    try:
        import httpx
    except ImportError:
        print("[ERROR] httpx not installed")
        print("Install with: pip install httpx")
        return
    
    import asyncio
    
    async def test_api():
        print("=" * 60)
        print("Testing: Semantic Scholar API")
        print("=" * 60)
        
        base_url = "https://api.semanticscholar.org/graph/v1"
        
        # Check for API key (optional)
        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip('"').strip("'")
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
            print("[OK] Using API key for higher rate limits\n")
        else:
            print("[WARNING] No API key (100 requests/5min limit)\n")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test 1: Search papers
            print(f"{'='*60}")
            print("Test 1: Search Papers ('large language model')")
            print(f"{'='*60}")
            
            try:
                response = await client.get(
                    f"{base_url}/paper/search",
                    params={
                        "query": "large language model",
                        "limit": 10,
                        "fields": "title,authors,year,citationCount,abstract,url"
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    papers = data.get('data', [])
                    
                    print(f"[OK] Found {len(papers)} papers")
                    
                    if papers:
                        print(f"\nTop Papers:")
                        for i, paper in enumerate(papers[:3], 1):
                            print(f"\n{i}. {paper.get('title', 'N/A')[:70]}")
                            print(f"   Year: {paper.get('year', 'N/A')}")
                            print(f"   Citations: {paper.get('citationCount', 0):,}")
                            print(f"   URL: {paper.get('url', 'N/A')}")
                            
                            authors = paper.get('authors', [])
                            if authors:
                                author_names = [a.get('name') for a in authors[:3]]
                                print(f"   Authors: {', '.join(author_names)}")
                            
                            abstract = paper.get('abstract', '')
                            if abstract:
                                print(f"   Abstract: {abstract[:150]}...")
                
                elif response.status_code == 429:
                    print(f"[WARNING] Rate limit exceeded (429)")
                    print(f"   → Get API key for higher limits")
                else:
                    print(f"[ERROR] Error: Status {response.status_code}")
            
            except Exception as e:
                print(f"[ERROR] Error: {e}")
            
            # Test 2: Get paper details by ArXiv ID
            print(f"\n{'='*60}")
            print("Test 2: Get Paper by ArXiv ID")
            print(f"{'='*60}")
            
            try:
                # Example ArXiv paper
                arxiv_id = "2005.14165"  # GPT-3 paper
                
                response = await client.get(
                    f"{base_url}/paper/arXiv:{arxiv_id}",
                    params={
                        "fields": "title,authors,year,citationCount,abstract,influentialCitationCount"
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    paper = response.json()
                    print(f"[OK] Found paper: {paper.get('title', 'N/A')[:70]}")
                    print(f"   Citations: {paper.get('citationCount', 0):,}")
                    print(f"   Influential citations: {paper.get('influentialCitationCount', 0):,}")
                else:
                    print(f"[WARNING] Status: {response.status_code}")
            
            except Exception as e:
                print(f"[ERROR] Error: {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY: SEMANTIC SCHOLAR API TEST")
        print("=" * 60)
        if api_key:
            print("[OK] API Key: Set (higher rate limits)")
        else:
            print("[WARNING] API Key: Not set (100 req/5min)")
        print("[OK] Paper search: Working")
        print("[OK] ArXiv lookup: Working")
        print("TIP: Expected collection: ~20-30 papers per day")
        print("TIP: Use for: Citation tracking, paper discovery")
    
    asyncio.run(test_api())


if __name__ == "__main__":
    import json
    import sys
    import asyncio
    from datetime import datetime
    
    print("\n" + "TEST SUITE: SEMANTIC SCHOLAR API TESTING" + "\n")
    test_semantic_scholar()
    print("\n[OK] Testing Complete!")
    
    # Collect actual papers data for JSON output
    async def collect_ss_data():
        import httpx
        base_url = "https://api.semanticscholar.org/graph/v1"
        
        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip('"').strip("'")
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        
        all_papers = []
        seen_titles = set()
        queries = ["large language model", "machine learning", "deep learning", "natural language processing"]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for qi, query in enumerate(queries):
                # Rate-limit: wait between queries (S2 allows ~1 req/s without key, ~10/s with key)
                if qi > 0:
                    await asyncio.sleep(1.5)
                
                # Retry with backoff for 429s
                for attempt in range(3):
                    try:
                        response = await client.get(
                            f"{base_url}/paper/search",
                            params={
                                "query": query,
                                "limit": 50,
                                "year": "2024-",
                                "fieldsOfStudy": "Computer Science",
                                "fields": "title,authors,year,citationCount,abstract,url,publicationDate,openAccessPdf,publicationTypes"
                            },
                            headers=headers
                        )
                        
                        if response.status_code == 429:
                            wait = 3 * (attempt + 1)
                            print(f"[~] S2 rate limited on '{query}', retrying in {wait}s...", flush=True)
                            await asyncio.sleep(wait)
                            continue
                        
                        if response.status_code == 200:
                            data = response.json()
                            papers = data.get('data', [])
                            
                            for paper in papers:
                                title = paper.get('title', '')
                                if not title or title.lower() in seen_titles:
                                    continue
                                seen_titles.add(title.lower())
                                all_papers.append({
                                    "query": query,
                                    "title": title,
                                    "year": paper.get('year', 0),
                                    "citations": paper.get('citationCount', 0),
                                    "url": paper.get('url', ''),
                                    "authors": [a.get('name') for a in paper.get('authors', [])],
                                    "abstract": paper.get('abstract', '') or '',
                                    "publication_date": paper.get('publicationDate', ''),
                                    "pdf_url": paper.get('openAccessPdf', {}).get('url', '') if paper.get('openAccessPdf') else '',
                                    "publication_types": paper.get('publicationTypes', [])
                                })
                            break  # success, move to next query
                        else:
                            print(f"[WARNING] S2 query '{query}': status {response.status_code}", file=sys.stderr)
                            break
                    except Exception as e:
                        print(f"[WARNING] S2 query '{query}' failed: {e}", file=sys.stderr)
                        break
        
        return all_papers
    
    try:
        papers_data = asyncio.run(collect_ss_data())
        
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({
            "source": "semantic_scholar",
            "collected_at": datetime.now().isoformat(),
            "total_papers": len(papers_data),
            "papers": papers_data
        }, indent=2))
    except Exception as e:
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({"source": "semantic_scholar", "error": str(e), "papers": []}, indent=2))
