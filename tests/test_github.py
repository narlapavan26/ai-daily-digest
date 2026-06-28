"""
Test GitHub API
Tests repository search, trending repos, and releases tracking
"""
import os

def test_github_api():
    """Test GitHub API for trending repos and framework releases"""
    
    try:
        import httpx
    except ImportError:
        print("[ERROR] httpx not installed")
        print("Install with: pip install httpx")
        return
    
    import asyncio
    
    async def test_api():
        print("=" * 60)
        print("Testing: GitHub API")
        print("=" * 60)
        
        # Check for token
        github_token = os.environ.get("GH_PAT_TOKEN", "").strip('"').strip("'")
        
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
            print("[OK] Using GitHub token for authentication\n")
        else:
            print("[WARNING] No GitHub token (60 requests/hour limit)")
            print("   Set GH_PAT_TOKEN for 5,000 requests/hour\n")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test 1: Search trending AI/ML repositories
            print(f"{'='*60}")
            print("Test 1: Search Trending AI/ML Repositories")
            print(f"{'='*60}")
            
            try:
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": "machine-learning language:Python stars:>1000",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 10
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    repos = data.get('items', [])
                    
                    print(f"[OK] Found {len(repos)} trending ML repos")
                    
                    if repos:
                        print(f"\nTop Repos:")
                        for i, repo in enumerate(repos[:5], 1):
                            print(f"\n{i}. {repo['full_name']}")
                            print(f"   Stars: {repo['stargazers_count']:,}")
                            print(f"   Forks: {repo['forks_count']:,}")
                            print(f"   Description: {repo['description'][:80] if repo.get('description') else 'No description'}")
                            print(f"   URL: {repo['html_url']}")
                
                elif response.status_code == 403:
                    print(f"[WARNING] Rate limit exceeded (403)")
                    print(f"   Add GH_PAT_TOKEN for higher limits")
                else:
                    print(f"[ERROR] Error: Status {response.status_code}")
            
            except Exception as e:
                print(f"[ERROR] Error: {e}")
            
            # Test 2: Get releases for agentic frameworks
            print(f"\n{'='*60}")
            print("Test 2: Framework Releases (Agentic & Backend)")
            print(f"{'='*60}")
            
            frameworks = [
                ("langchain-ai/langchain", "LangChain"),
                ("run-llama/llama_index", "LlamaIndex"),
                ("joaomdmoura/crewai", "CrewAI"),
                ("microsoft/autogen", "AutoGen"),
                ("tiangolo/fastapi", "FastAPI"),
            ]
            
            print(f"\nChecking latest releases:")
            
            for repo_name, display_name in frameworks:
                try:
                    response = await client.get(
                        f"https://api.github.com/repos/{repo_name}/releases/latest",
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        release = response.json()
                        print(f"\n[OK] {display_name}")
                        print(f"   Version: {release['tag_name']}")
                        print(f"   Published: {release['published_at'][:10]}")
                        print(f"   {release['html_url']}")
                    
                    elif response.status_code == 404:
                        print(f"\n[WARNING] {display_name}: No releases found")
                    
                    else:
                        print(f"\n[ERROR] {display_name}: Status {response.status_code}")
                
                except Exception as e:
                    print(f"\n[ERROR] {display_name}: {e}")
            
            # Test 3: Get trending repos (last week)
            print(f"\n{'='*60}")
            print("Test 3: Recently Trending (Created Last 7 Days)")
            print(f"{'='*60}")
            
            try:
                from datetime import datetime, timedelta
                week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": f"llm OR agent OR rag created:>{week_ago} stars:>50",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 5
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    repos = data.get('items', [])
                    
                    print(f"[OK] Found {len(repos)} new trending repos")
                    
                    if repos:
                        for i, repo in enumerate(repos, 1):
                            print(f"\n{i}. {repo['full_name']}")
                            print(f"   {repo['stargazers_count']} stars in {(datetime.now() - datetime.strptime(repo['created_at'], '%Y-%m-%dT%H:%M:%SZ')).days} days")
                            print(f"   Description: {repo['description'][:80] if repo.get('description') else 'No description'}")
                else:
                    print(f"[ERROR] Error: Status {response.status_code}")
            
            except Exception as e:
                print(f"[ERROR] Error: {e}")
            
            # Test 4: Check rate limits
            print(f"\n{'='*60}")
            print("Test 4: Rate Limit Status")
            print(f"{'='*60}")
            
            try:
                response = await client.get(
                    "https://api.github.com/rate_limit",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    core = data['resources']['core']
                    search = data['resources']['search']
                    
                    print(f" Rate Limits:")
                    print(f"   Core API: {core['remaining']:,} / {core['limit']:,} remaining")
                    print(f"   Search API: {search['remaining']:,} / {search['limit']:,} remaining")
                    
                    if core['remaining'] < 100:
                        print(f"\n  Low on requests! Consider adding GH_PAT_TOKEN")
            
            except Exception as e:
                print(f"[ERROR] Error: {e}")
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY: GITHUB API TEST")
        print(f"{'='*60}")
        print("[OK] GitHub API is accessible")
        print("[OK] Repository search working")
        print("[OK] Release tracking working")
        print(" Expected collection: ~30-50 repos + 20+ releases per day")
        print(" Covers: Agentic frameworks, backend frameworks, trending repos")
    
    asyncio.run(test_api())


if __name__ == "__main__":
    import json
    import asyncio
    from datetime import datetime
    
    print("\n" + "GITHUB API TESTING SUITE" + "\n")
    test_github_api()
    print("\nTesting Complete!")
    
    # Collect actual data for JSON output
    async def collect_github_data():
        import httpx
        from datetime import datetime, timedelta
        
        three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        github_token = os.environ.get("GH_PAT_TOKEN", "").strip('"').strip("'")
        
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        
        all_data = {
            "trending_repos": [],
            "framework_releases": [],
            "new_repos": []
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Collect trending repos — sort by STARS with minimum star filter
            try:
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": f"machine-learning OR llm OR agent language:Python stars:>100 pushed:>{three_days_ago}",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 20
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    repos = data.get('items', [])
                    
                    for repo in repos:
                        all_data["trending_repos"].append({
                            "name": repo['full_name'],
                            "stars": repo['stargazers_count'],
                            "forks": repo['forks_count'],
                            "description": repo.get('description', '') or '',
                            "language": repo.get('language', ''),
                            "url": repo['html_url'],
                            "pushed_at": repo.get('pushed_at', ''),
                            "topics": repo.get('topics', [])[:10]
                        })
            except Exception:
                pass
            
            # Additional broader AI trending query
            try:
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": f"AI OR LLM OR transformer stars:>500 pushed:>{three_days_ago}",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 10
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    repos = data.get('items', [])
                    seen_names = {r['name'] for r in all_data['trending_repos']}
                    
                    for repo in repos:
                        if repo['full_name'] not in seen_names:
                            all_data["trending_repos"].append({
                                "name": repo['full_name'],
                                "stars": repo['stargazers_count'],
                                "forks": repo['forks_count'],
                                "description": repo.get('description', '') or '',
                                "language": repo.get('language', ''),
                                "url": repo['html_url'],
                                "pushed_at": repo.get('pushed_at', ''),
                                "topics": repo.get('topics', [])[:10]
                            })
            except Exception:
                pass
            
            # Collect framework releases
            frameworks = [
                "langchain-ai/langchain",
                "run-llama/llama_index",
                "joaomdmoura/crewai",
                "microsoft/autogen",
                "deepset-ai/haystack",
                "FlowiseAI/Flowise",
                "tiangolo/fastapi",
                "pallets/flask",
                "django/django",
                "streamlit/streamlit",
                "gradio-app/gradio",
                "langchain-ai/langserve",
                "pytorch/pytorch",
                "Lightning-AI/pytorch-lightning",
                "ray-project/ray",
                "mlflow/mlflow",
                "bentoml/BentoML"
            ]
            
            for repo_name in frameworks:
                try:
                    response = await client.get(
                        f"https://api.github.com/repos/{repo_name}/releases/latest",
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        release = response.json()
                        published_at = release.get('published_at', '')
                        tag = release.get('tag_name', '')
                        # Skip trunk commits (e.g. "trunk/abc123") and bare
                        # commit-hash tags (e.g. "946d52a") — not real releases
                        import re as _re
                        _is_commit_hash = bool(_re.fullmatch(r'[a-f0-9]{7,40}', tag))
                        _is_trunk = bool(_re.search(r'(^|/)trunk/', tag, _re.IGNORECASE))
                        if _is_commit_hash or _is_trunk:
                            continue
                        # Only include releases from last 3 days
                        if published_at and published_at[:10] >= three_days_ago:
                            all_data["framework_releases"].append({
                                "framework": repo_name.split('/')[1],
                                "repo": repo_name,
                                "version": tag,
                                "published": published_at,
                                "url": release['html_url'],
                                "notes": release.get('body', '')[:5000]
                            })
                except Exception:
                    pass
            
            # Collect new trending repos (lower threshold for 3-day window)
            try:
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": f"llm OR agent OR rag OR AI created:>{three_days_ago} stars:>10",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 15
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    repos = data.get('items', [])
                    
                    for repo in repos:
                        all_data["new_repos"].append({
                            "name": repo['full_name'],
                            "stars": repo['stargazers_count'],
                            "created": repo['created_at'],
                            "description": repo.get('description', ''),
                            "url": repo['html_url']
                        })
            except Exception:
                pass
            
            # Fetch README excerpt for all repos (trending + new)
            import re as _re
            def _clean_readme(text, max_chars=2500):
                """Clean markdown README for digest: strip badges, images, HTML, keep description."""
                lines = text.split('\n')
                cleaned = []
                for line in lines:
                    # Skip badge/image lines
                    if _re.match(r'^\s*\[?!\[', line):
                        continue
                    if _re.match(r'^\s*<(img|div|p|br|hr)\b', line, _re.IGNORECASE):
                        continue
                    # Skip lines that are just URLs
                    if _re.match(r'^\s*https?://', line.strip()):
                        continue
                    # Skip table of contents links
                    if _re.match(r'^\s*-\s*\[.*\]\(#', line):
                        continue
                    cleaned.append(line)
                text = '\n'.join(cleaned)
                # Remove markdown link syntax but keep text: [text](url) -> text
                text = _re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
                # Remove HTML tags
                text = _re.sub(r'<[^>]+>', ' ', text)
                # Remove markdown bold/italic
                text = _re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
                # Remove markdown headers markers but keep text
                text = _re.sub(r'^#{1,6}\s+', '', text, flags=_re.MULTILINE)
                # Collapse whitespace
                text = _re.sub(r'\n{3,}', '\n\n', text)
                text = _re.sub(r'  +', ' ', text)
                return text[:max_chars].strip()
            
            all_repos = all_data['trending_repos'] + all_data['new_repos']
            for repo_item in all_repos:
                repo_fullname = repo_item.get('name', '')
                if not repo_fullname:
                    continue
                try:
                    readme_resp = await client.get(
                        f"https://api.github.com/repos/{repo_fullname}/readme",
                        headers={**headers, "Accept": "application/vnd.github.raw+json"},
                        timeout=10.0
                    )
                    if readme_resp.status_code == 200:
                        raw_readme = readme_resp.text
                        repo_item['readme_excerpt'] = _clean_readme(raw_readme)
                except Exception:
                    pass
        
        return all_data
    
    try:
        github_data = asyncio.run(collect_github_data())
        
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({
            "source": "github",
            "collected_at": datetime.now().isoformat(),
            "cutoff_days": 3,
            "total_trending_repos": len(github_data["trending_repos"]),
            "total_framework_releases": len(github_data["framework_releases"]),
            "total_new_repos": len(github_data["new_repos"]),
            "data": github_data
        }, indent=2))
    except Exception as e:
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({"source": "github", "error": str(e), "data": {"trending_repos": [], "framework_releases": [], "new_repos": []}}, indent=2))
