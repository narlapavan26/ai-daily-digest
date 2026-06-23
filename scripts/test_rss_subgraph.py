"""
scripts/test_rss_subgraph.py
=============================
End-to-end smoke test for the RSS subgraph pipeline.

Runs the full pipeline:
  MCP /fetch/rss  →  normalize  →  fast-fail  →  LLM enrich  →  SubgraphOutput

Usage (from repo root):
    # Full catalog run (all ~110 feeds, real LLM):
    python scripts/test_rss_subgraph.py

    # Quick test with just 2 feeds (faster, still real LLM):
    python scripts/test_rss_subgraph.py --quick

    # Skip LLM (only test MCP + normalize + fast-fail):
    python scripts/test_rss_subgraph.py --no-llm

    # Custom feeds:
    python scripts/test_rss_subgraph.py --feeds https://huggingface.co/blog/feed.xml

Prerequisites:
    1. MCP server running locally:  cd mcp && uvicorn main:app --reload
    2. .env has GROQ_API_KEY set
    3. pip install instructor openai pydantic pydantic-settings httpx feedparser
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# ── Setup sys.path so we can import from repo root ─────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ── Load .env before any imports that need keys ────────────────────────────────
env_file = REPO_ROOT / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                val = val.strip().strip('"').strip("'")
                if key.strip() and val:
                    os.environ.setdefault(key.strip(), val)
    print(f"[ENV] Loaded from {env_file}")
else:
    print("[ENV] No .env file found — using system environment")

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("test_rss_subgraph")


def print_separator(char="=", width=70):
    print(char * width)


def print_section(title: str):
    print_separator()
    print(f"  {title}")
    print_separator()


def run_test(
    feed_urls: list[str] | None = None,
    use_verified_catalog: bool = True,
    skip_llm: bool = False,
) -> None:
    """Run the RSS subgraph and pretty-print results."""

    print_section("RSS SUBGRAPH — END-TO-END TEST")
    print(f"  Time:    {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  MCP URL: {os.environ.get('MCP_BASE_URL', 'http://127.0.0.1:8000')} (from settings)")
    print(f"  Catalog: {use_verified_catalog}")
    print(f"  Feeds:   {feed_urls or 'catalog'}")
    print(f"  LLM:     {'SKIPPED' if skip_llm else 'Groq (Gemini fallback)'}")
    print_separator()

    # ── Step 1: Import subgraph ────────────────────────────────────────────────
    try:
        from digest_runner.subgraphs.rss_subgraph import RssSubgraph
        print("[OK] Imported RssSubgraph")
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        print("       Run from repo root: python scripts/test_rss_subgraph.py")
        sys.exit(1)

    # ── Step 2: Verify keys ────────────────────────────────────────────────────
    groq_key = os.environ.get("GROQ_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    print(f"[ENV] GROQ_API_KEY:   {'OK SET' if groq_key else 'NO MISSING'} ({groq_key[:12]}... if set)")
    print(f"[ENV] GEMINI_API_KEY: {'OK SET' if gemini_key else 'NO MISSING'}")

    if not groq_key and not skip_llm:
        print("\n[WARNING] GROQ_API_KEY not set — LLM enrichment will fail.")
        print("          Set it in .env or use --no-llm to skip LLM step.")

    # ── Step 3: Build subgraph ─────────────────────────────────────────────────
    subgraph = RssSubgraph(
        feed_urls=feed_urls,
        use_verified_catalog=use_verified_catalog,
    )

    # ── Step 4: Run ────────────────────────────────────────────────────────────
    if skip_llm:
        # Only run fetch + normalize + fast-fail (no LLM)
        print("\n[STEP 1/3] Fetching from MCP...")
        t0 = time.perf_counter()
        try:
            raw = subgraph.fetch_from_mcp()
            elapsed = (time.perf_counter() - t0) * 1000
            print(f"[OK] MCP fetch: {raw.get('total_fetched', 0)} items in {elapsed:.0f}ms")
            if raw.get("errors"):
                print(f"[WARN] MCP errors ({len(raw['errors'])}):")
                for e in raw["errors"][:5]:
                    print(f"       - {e[:100]}")
        except Exception as exc:
            print(f"[FAIL] MCP fetch failed: {exc}")
            print("       Is the MCP server running? cd mcp && uvicorn main:app --reload")
            sys.exit(1)

        print("\n[STEP 2/3] Normalizing items...")
        from digest_runner.subgraphs.rss_subgraph import _digest_item_to_normalized
        rows = list(raw.get("items") or [])
        normalized = []
        errors = []
        for row in rows:
            try:
                normalized.append(_digest_item_to_normalized(row))
            except Exception as e:
                errors.append(str(e))
        print(f"[OK] Normalized: {len(normalized)} items ({len(errors)} errors)")

        print("\n[STEP 3/3] Fast-fail filter...")
        # pyrefly: ignore [missing-module-attribute]
        from digest_runner.subgraphs.rss_subgraph import _fast_fail_batch
        ff = _fast_fail_batch(normalized)
        print(f"[OK] Fast-fail: {len(ff.passed)} passed, {len(ff.dropped)} dropped ({ff.pass_rate*100:.0f}% pass rate)")

        # Show fast-fail breakdown
        from collections import Counter
        verdicts = Counter(r.verdict for r in ff.dropped)
        for verdict, count in verdicts.items():
            print(f"     - {verdict}: {count}")

        # Preview items that passed
        print(f"\n[PREVIEW] First 5 items that passed fast-fail:")
        for i, item in enumerate(ff.passed[:5], 1):
            qs = item.quality_signals
            print(f"  {i}. [{qs.get('section','?')}] {item.title[:70]}")
            print(f"     Feed: {qs.get('feed','?')} | {item.days_old:.1f}d old | {len(item.content_for_llm)} chars")

        print_separator()
        print(f"[DONE] No-LLM test complete. {len(ff.passed)} items ready for enrichment.")
        return

    # Full run including LLM
    print("\n[RUNNING] Full RSS subgraph pipeline (this will take 30-120 seconds)...")
    t0 = time.perf_counter()
    try:
        output = subgraph.run()
    except Exception as exc:
        print(f"\n[FAIL] Subgraph crashed: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    elapsed = (time.perf_counter() - t0)

    # ── Step 5: Print results ──────────────────────────────────────────────────
    print_separator()
    print("  RESULTS")
    print_separator()
    print(f"  Source:          {output.source}")
    print(f"  Total reviewed:  {output.total_reviewed}")
    print(f"  Fast-fail drop:  {output.fast_fail_dropped}")
    print(f"  LLM drop:        {output.llm_dropped}")
    print(f"  Selected:        {output.total_selected}")
    print(f"  Model used:      {output.model_used}")
    print(f"  Fallback used:   {output.used_fallback}")
    print(f"  Processing time: {elapsed:.1f}s ({output.processing_ms:.0f}ms)")
    print_separator()

    if not output.enriched_items:
        print("\n[WARN] No enriched items produced.")
        print("       Possible causes:")
        print("       1. MCP server not running → cd mcp && uvicorn main:app --reload")
        print("       2. All feeds returned stale/empty content")
        print("       3. LLM scored everything as irrelevant")
        print("       4. Groq rate limit hit")
        return

    print(f"\n  ENRICHED ITEMS ({len(output.enriched_items)}):")
    print_separator("-")

    from collections import Counter
    section_counts = Counter()
    for i, item in enumerate(output.enriched_items, 1):
        section_counts[item.digest_section] += 1
        print(f"\n  [{i}] {item.title[:75]}")
        print(f"       Section:    {item.digest_section} | Novelty: {item.novelty_type}")
        print(f"       Relevance:  {item.relevance_score:.2f} | Confidence: {item.confidence:.2f}")
        print(f"       Sensitivity:{item.time_sensitivity} | Audience: {[a.value for a in item.impacted_audience]}")
        print(f"       Summary:    {item.change_summary[:120]}")
        print(f"       Insight:    {item.actionable_insight[:100]}")
        print(f"       URL:        {item.url}")

    print_separator()
    print("\n  SECTION DISTRIBUTION:")
    for section, count in section_counts.most_common():
        print(f"    {section}: {count}")

    # ── Step 6: Save output to file ────────────────────────────────────────────
    output_dir = REPO_ROOT / "tests" / "outputs"
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"rss_subgraph_test_{ts}.json"

    try:
        data = {
            "run_timestamp": ts,
            "total_reviewed": output.total_reviewed,
            "total_selected": output.total_selected,
            "fast_fail_dropped": output.fast_fail_dropped,
            "llm_dropped": output.llm_dropped,
            "model_used": str(output.model_used),
            "used_fallback": output.used_fallback,
            "processing_ms": output.processing_ms,
            "enriched_items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "url": str(item.url),
                    "source": str(item.source),
                    "published_at": item.published_at.isoformat(),
                    "days_old": item.days_old,
                    "digest_section": str(item.digest_section),
                    "novelty_type": str(item.novelty_type),
                    "relevance_score": item.relevance_score,
                    "confidence": item.confidence,
                    "time_sensitivity": str(item.time_sensitivity),
                    "change_summary": item.change_summary,
                    "significance": item.significance,
                    "actionable_insight": item.actionable_insight,
                    "impacted_audience": [str(a) for a in item.impacted_audience],
                }
                for item in output.enriched_items
            ],
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVED] Output written to: {output_file}")
    except Exception as exc:
        print(f"[WARN] Could not save output: {exc}")

    print_separator()
    print(f"[DONE] RSS subgraph test complete!")
    print(f"       {output.total_selected} enriched items from {output.total_reviewed} reviewed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test the RSS subgraph end-to-end")
    parser.add_argument(
        "--quick", action="store_true",
        help="Use only 3 feeds (fast test, skips catalog)",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Only test MCP fetch + normalize + fast-fail (skip LLM enrichment)",
    )
    parser.add_argument(
        "--feeds", nargs="+", default=None,
        help="Specific feed URLs to test",
    )
    args = parser.parse_args()

    if args.feeds:
        run_test(feed_urls=args.feeds, use_verified_catalog=False, skip_llm=args.no_llm)
    elif args.quick:
        quick_feeds = [
            "https://huggingface.co/blog/feed.xml",
            "https://blog.langchain.com/rss",
            "https://github.com/langchain-ai/langgraph/releases.atom",
        ]
        run_test(feed_urls=quick_feeds, use_verified_catalog=False, skip_llm=args.no_llm)
    else:
        run_test(feed_urls=None, use_verified_catalog=True, skip_llm=args.no_llm)


if __name__ == "__main__":
    main()
