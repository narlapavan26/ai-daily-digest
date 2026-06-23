"""
scripts/test_other_subgraphs.py
===============================
Smoke tests for all non-RSS subgraphs.
Focuses on ensuring the 'content_for_llm' field is rich enough for the LLM.

Usage:
  python scripts/test_other_subgraphs.py --arxiv
  python scripts/test_other_subgraphs.py --github
  python scripts/test_other_subgraphs.py --hackernews
  python scripts/test_other_subgraphs.py --huggingface
  python scripts/test_other_subgraphs.py --reddit
  python scripts/test_other_subgraphs.py --stackoverflow
  python scripts/test_other_subgraphs.py --all
"""

import argparse
import sys
import os
import time
from pathlib import Path

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Load .env
env_file = REPO_ROOT / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Import ALL subgraphs
from digest_runner.subgraphs import (
    ArxivSubgraph,
    GithubSubgraph,
    HackerNewsSubgraph,
    HuggingFaceSubgraph,
    RedditSubgraph,
    StackOverflowSubgraph,
)

def print_separator(char="=", width=80):
    print(char * width)

def test_subgraph(name: str, subgraph_instance):
    print_separator()
    print(f" TESTING SUBGRAPH: {name.upper()}")
    print_separator()
    
    # 1. Fetch raw items
    print(f"\n[1] Fetching raw items from MCP...")
    try:
        raw_data = subgraph_instance.fetch_from_mcp()
    except Exception as e:
        print(f"[FAIL] MCP Fetch failed: {e}")
        return
        
    raw_items = raw_data.get("items", [])
    errors = raw_data.get("errors", [])
    print(f"    - Fetched {len(raw_items)} items.")
    if errors:
        print(f"    - Errors: {errors}")
        
    if not raw_items:
        print("[WARN] No items fetched. Skipping normalization.")
        return

    # 2. Normalize items
    print(f"\n[2] Normalizing items...")
    normalized = subgraph_instance.normalize(raw_items)
    print(f"    - Normalized {len(normalized)} items.")

    # 3. Fast Fail
    print(f"\n[3] Running Fast-Fail Filter...")
    ff_batch = subgraph_instance.fast_fail(normalized)
    print(f"    - Passed: {len(ff_batch.passed)}")
    print(f"    - Dropped: {len(ff_batch.dropped)}")
    
    # 4. Content Inspection
    print(f"\n[4] Inspecting content quality for LLM (Top 3 items)...")
    if not ff_batch.passed:
        print("    [WARN] No items passed fast-fail!")
    
    for i, item in enumerate(ff_batch.passed[:3], 1):
        content_len = len(item.content_for_llm)
        print_separator("-")
        print(f"  Item {i}: {item.title}")
        print(f"  URL: {item.url}")
        print(f"  Quality Signals: {item.quality_signals}")
        print(f"  Content Length: {content_len} characters")
        print("  Content Snippet:")
        # Show first 300 and last 100 characters to verify richness
        if content_len > 400:
            snippet = item.content_for_llm[:300] + "\n\n[...TRUNCATED...]\n\n" + item.content_for_llm[-100:]
        else:
            snippet = item.content_for_llm
            
        # Indent snippet for readability
        for line in snippet.splitlines():
            safe_line = line.encode('ascii', 'replace').decode('ascii')
            print(f"    | {safe_line}")
            
        if content_len < 100:
            print("    [WARNING] Content is extremely short! LLM may struggle.")
        elif content_len > 3000:
            print("    [WARNING] Content is very long, might consume many tokens.")
        else:
            print("    [OK] Content length is healthy.")
            
    print("\nDone testing", name)


def main():
    parser = argparse.ArgumentParser(description="Test non-RSS subgraphs (no LLM)")
    parser.add_argument("--arxiv",         action="store_true", help="Test ArXiv subgraph")
    parser.add_argument("--github",        action="store_true", help="Test GitHub subgraph")
    parser.add_argument("--hackernews",    action="store_true", help="Test HackerNews subgraph")
    parser.add_argument("--huggingface",   action="store_true", help="Test HuggingFace subgraph")
    parser.add_argument("--reddit",        action="store_true", help="Test Reddit subgraph")
    parser.add_argument("--stackoverflow", action="store_true", help="Test StackOverflow subgraph")
    parser.add_argument("--all",           action="store_true", help="Test ALL 6 subgraphs")
    args = parser.parse_args()

    if not any(vars(args).values()):
        print("Please specify a subgraph to test.")
        print("Options: --arxiv, --github, --hackernews, --huggingface, --reddit, --stackoverflow, --all")
        sys.exit(1)

    if args.arxiv or args.all:
        # pyrefly: ignore [unexpected-keyword]
        test_subgraph("ArXiv", ArxivSubgraph(query="large language models", max_results=5, days_back=7))

    if args.github or args.all:
        test_subgraph("GitHub", GithubSubgraph(topics=["llm", "agent"], max_results=5, days_back=7))

    if args.hackernews or args.all:
        test_subgraph("HackerNews", HackerNewsSubgraph(category="AI OR LLM", max_results=5, min_score=30, days_back=3))

    if args.huggingface or args.all:
        test_subgraph("HuggingFace", HuggingFaceSubgraph(max_models=5, max_blogs=3, days_back=7))

    if args.reddit or args.all:
        test_subgraph("Reddit", RedditSubgraph(
            subreddits=["MachineLearning", "LocalLLaMA"],
            max_posts_per_sub=3, days_back=3, min_score=10,
        ))

    if args.stackoverflow or args.all:
        test_subgraph("StackOverflow", StackOverflowSubgraph(
            tags=["llm", "langchain", "openai-api"],
            max_results=5, days_back=7, min_score=3,
        ))


if __name__ == "__main__":
    main()
