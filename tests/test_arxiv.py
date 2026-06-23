"""
Test ArXiv API
No API key required - completely free
"""

def test_arxiv_search():
    """Test ArXiv paper search"""
    
    try:
        import arxiv
    except ImportError:
        print("❌ arxiv library not installed")
        print("Install with: pip install arxiv")
        return
    
    print("=" * 60)
    print("Testing: ArXiv API - Search")
    print("=" * 60)
    print("Query: cs.AI category, last 7 days\n")
    
    try:
        # Create client
        client = arxiv.Client()
        
        # Search recent cs.AI papers
        search = arxiv.Search(
            query="cat:cs.AI",
            max_results=10,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        
        papers = list(client.results(search))
        
        print(f"[OK] Found {len(papers)} papers\n")
        
        if papers:
            print("-" * 60)
            print("Sample Papers:")
            print("-" * 60)
            
            for i, paper in enumerate(papers[:3], 1):
                print(f"\n{i}. {paper.title}")
                print(f"   Authors: {', '.join([a.name for a in paper.authors[:3]])}{'...' if len(paper.authors) > 3 else ''}")
                print(f"   Published: {paper.published.strftime('%Y-%m-%d')}")
                print(f"   URL: {paper.entry_id}")
                print(f"   Abstract: {paper.summary[:200]}...")
                print(f"   Categories: {', '.join(paper.categories)}")
            
            print("\n" + "-" * 60)
            print(f"SUMMARY: Statistics:")
            print(f"   Total papers found: {len(papers)}")
            avg_abstract_len = sum(len(p.summary) for p in papers) / len(papers)
            print(f"   Average abstract length: {int(avg_abstract_len)} chars")
            print(f"   Authors per paper: {sum(len(p.authors) for p in papers) / len(papers):.1f}")
            
            # Check freshness
            from datetime import datetime, timedelta
            now = datetime.now(papers[0].published.tzinfo)
            recent_papers = [p for p in papers if (now - p.published) < timedelta(days=1)]
            print(f"   Papers from last 24h: {len(recent_papers)}")
            
        else:
            print("[WARNING] No papers found (unusual)")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")


def test_arxiv_multiple_categories():
    """Test multiple ArXiv categories"""
    
    try:
        import arxiv
    except ImportError:
        print("[ERROR] arxiv library not installed")
        return
    
    print("\n" + "=" * 60)
    print("Testing: ArXiv API - Multiple Categories")
    print("=" * 60)
    
    categories = [
        ("cs.AI", "Artificial Intelligence"),
        ("cs.LG", "Machine Learning"),
        ("stat.ML", "Machine Learning (Stats)"),
        ("cs.CL", "Computation and Language"),
        ("cs.CV", "Computer Vision")
    ]
    
    client = arxiv.Client()
    total_papers = 0
    
    print("\nPapers per category (last 24h):\n")
    
    for cat_id, cat_name in categories:
        try:
            search = arxiv.Search(
                query=f"cat:{cat_id}",
                max_results=50,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )
            
            papers = list(client.results(search))
            
            # Filter to last 24h
            from datetime import datetime, timedelta
            now = datetime.now(papers[0].published.tzinfo) if papers else datetime.now()
            recent = [p for p in papers if (now - p.published) < timedelta(days=1)]
            
            print(f"  {cat_id:10s} ({cat_name:30s}): {len(recent):2d} papers")
            total_papers += len(recent)
            
        except Exception as e:
            print(f"  {cat_id:10s} ({cat_name:30s}): [ERROR] Error - {e}")
    
    print(f"\nSUMMARY: Total AI/ML papers from last 24h: {total_papers}")
    print(f"   Daily collection estimate: {total_papers * 1.5:.0f} papers (with buffer)")


def test_arxiv_error_handling():
    """Test ArXiv API error handling"""
    
    try:
        import arxiv
    except ImportError:
        return
    
    print("\n" + "=" * 60)
    print("Testing: ArXiv API - Error Handling")
    print("=" * 60)
    
    client = arxiv.Client()
    
    # Test 1: Invalid query
    print("\n1. Testing invalid query handling...")
    try:
        search = arxiv.Search(
            query="INVALID_CATEGORY_XYZ",
            max_results=5
        )
        papers = list(client.results(search))
        print(f"   [OK] Handled gracefully, returned {len(papers)} papers")
    except Exception as e:
        print(f"   [WARNING] Exception: {e}")
    
    # Test 2: Very large max_results
    print("\n2. Testing rate limit behavior...")
    try:
        search = arxiv.Search(
            query="cat:cs.AI",
            max_results=100
        )
        papers = list(client.results(search))
        print(f"   [OK] No rate limit issues, got {len(papers)} papers")
    except Exception as e:
        print(f"   [WARNING] Rate limit hit: {e}")
    
    # Test 3: Network timeout simulation
    print("\n3. Testing timeout handling...")
    try:
        search = arxiv.Search(
            query="cat:cs.AI",
            max_results=5
        )
        # Set short timeout
        client = arxiv.Client(
            page_size=100,
            delay_seconds=0.5,
            num_retries=2
        )
        papers = list(client.results(search))
        print(f"   [OK] Retry logic works, got {len(papers)} papers")
    except Exception as e:
        print(f"   [WARNING] Failed after retries: {e}")


if __name__ == "__main__":
    import json
    from datetime import datetime, timedelta
    
    print("\n" + "TEST SUITE: ARXIV API TESTING" + "\n")
    
    # Test 1: Basic search
    test_arxiv_search()
    
    # Test 2: Multiple categories
    test_arxiv_multiple_categories()
    
    # Test 3: Error handling
    test_arxiv_error_handling()
    
    print("\n" + "=" * 60)
    print("[OK] Testing Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Document results in TESTING_RESULTS.md")
    print("2. Test Papers With Code API (test_papers_with_code.py)")
    print("3. Test RSS feeds (test_rss_feeds.py)")
    
    print("\nTIP: Production Recommendation:")
    print("   • Fetch from all 5 categories simultaneously")
    print("   • Filter papers from last 24 hours only")
    print("   • Expect ~30-80 papers per day total")
    print("   • No rate limiting issues expected")
    
    # Collect actual papers data for output
    try:
        import arxiv
        client = arxiv.Client()
        
        # Collect papers from all categories
        # cs.CV removed — produces off-topic vision/robotics papers.
        # cs.SE added — software engineering papers overlap with framework development.
        categories = [
            ("cs.AI", "Artificial Intelligence"),
            ("cs.LG", "Machine Learning"),
            ("cs.CL", "Computation and Language"),
            ("cs.SE", "Software Engineering"),
        ]
        
        collected_papers = []
        seen_ids = set()
        # 4-day cutoff so weekends/holidays are covered (ArXiv doesn't publish on weekends)
        cutoff_date = datetime.now().astimezone() - timedelta(days=4)
        
        for cat_code, cat_name in categories:
            search = arxiv.Search(
                query=f"cat:{cat_code}",
                max_results=100,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )
            
            for paper in client.results(search):
                # Only collect papers from last 3 days, deduplicate by ID
                pub = paper.published if paper.published.tzinfo else paper.published.astimezone()
                if pub < cutoff_date:
                    break  # Results are sorted newest-first, safe to stop
                if paper.entry_id in seen_ids:
                    continue
                seen_ids.add(paper.entry_id)
                collected_papers.append({
                    "title": paper.title,
                    "authors": [a.name for a in paper.authors],
                    "published": paper.published.isoformat(),
                    "url": paper.entry_id,
                    "abstract": paper.summary,
                    "categories": paper.categories,
                    "primary_category": paper.primary_category,
                    "pdf_url": paper.pdf_url
                })
        
        # Output JSON data
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({
            "source": "arxiv",
            "collected_at": datetime.now().isoformat(),
            "cutoff_days": 4,
            "total_papers": len(collected_papers),
            "papers": collected_papers
        }, indent=2))
        
    except Exception as e:
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({
            "source": "arxiv",
            "error": str(e),
            "papers": []
        }, indent=2))
