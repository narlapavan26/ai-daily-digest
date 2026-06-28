"""
digest_runner/main.py
======================
CLI entrypoint for the AI Daily Digest pipeline.

Usage:
    python -m digest_runner.main
    python -m digest_runner.main --sources arxiv hackernews
    python -m digest_runner.main --sources rss_feeds --output-dir /tmp/digests

Environment variables required:
    GROQ_API_KEY   — primary LLM provider
    GEMINI_API_KEY — fallback LLM provider (optional but recommended)
    MCP_BASE_URL   — MCP server URL (default: http://127.0.0.1:8000)
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def _load_env_into_os_environ() -> None:
    """
    Load .env file values directly into os.environ so that any code
    that calls os.environ.get('GROQ_API_KEY') etc. can find them.

    pydantic-settings populates the `settings` object but does NOT
    inject values into os.environ — this function bridges that gap.
    """
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:  # don't override existing env vars
                os.environ[key] = value
    except Exception as exc:
        import warnings
        warnings.warn(f"Failed to load .env file: {exc}", RuntimeWarning, stacklevel=2)


# Load .env into os.environ immediately on import so API keys are always available
_load_env_into_os_environ()

# Force UTF-8 output on Windows to avoid UnicodeEncodeError with emoji
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configure basic logging if not already configured
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stderr,
)

logger = logging.getLogger(__name__)


def run_digest(
    sources: Optional[List[str]] = None,
    output_dir: str = "outputs",
) -> dict:
    """
    Build and invoke the digest pipeline.

    Args:
        sources:    List of source names to process. Defaults to all 7 sources.
        output_dir: Directory where the Markdown file is saved.
                    Can also be set via DIGEST_OUTPUT_DIR env var.

    Returns:
        Final LangGraph state dict, including:
          - output_path:   Path to saved Markdown file
          - final_digest:  FinalDigestSchema
          - errors:        List of non-fatal error strings
    """
    from digest_runner.graph.digest_graph import build_graph, DEFAULT_SOURCES
    from digest_runner.utils.provider_pool import ProviderPool

    # Clear any stale cooldowns from previous runs
    ProviderPool.reset()

    if output_dir != "outputs":
        os.environ["DIGEST_OUTPUT_DIR"] = output_dir

    graph = build_graph()

    initial_state = {
        "run_date":        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "run_id":          str(uuid.uuid4()),
        "active_sources":  sources or DEFAULT_SOURCES,
        "subgraph_outputs": [],
        "errors":          [],
    }

    logger.info(
        "Starting digest run: run_id=%s sources=%s",
        initial_state["run_id"][:8],
        initial_state["active_sources"],
    )

    result = graph.invoke(initial_state)

    errors = result.get("errors") or []
    if errors:
        logger.warning("Digest completed with %d errors:\n  %s", len(errors), "\n  ".join(errors[:10]))

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="AI Daily Digest Runner — fetch, enrich, and render the daily AI/ML digest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m digest_runner.main
  python -m digest_runner.main --sources arxiv hackernews github
  python -m digest_runner.main --output-dir /tmp/digests
        """,
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        metavar="SOURCE",
        help="Space-separated list of sources to process. "
             "Valid: arxiv hackernews github huggingface reddit stackoverflow rss_feeds. "
             "Defaults to all 7.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory to write the Markdown digest file. Default: outputs/",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="If set, publish the digest to Discord, Telegram, and Email (requires env vars). Default: False",
    )

    args = parser.parse_args()

    try:
        result = run_digest(sources=args.sources, output_dir=args.output_dir)
        output_path = result.get("output_path") or "unknown"
        errors = result.get("errors") or []
        final_digest = result.get("final_digest")
        selected = getattr(getattr(final_digest, 'metadata', None), 'total_selected', 0) if final_digest else 0
        print(f"\n[OK] Digest saved to: {output_path}")
        print(f"     Items selected: {selected}")
        
        # ── Trigger Publishers (if requested) ───────────────────────────────
        if args.publish:
            from digest_runner.publishers.discord_publisher import publish_to_discord
            from digest_runner.publishers.telegram_publisher import publish_to_telegram
            from digest_runner.publishers.email_publisher import publish_to_email
            
            publishers = [
                ("Discord", publish_to_discord),
                ("Telegram", publish_to_telegram),
                ("Email", publish_to_email),
            ]
            for name, publisher in publishers:
                try:
                    publisher(output_path, selected)
                    logger.info("Published to %s", name)
                except Exception as pub_exc:
                    logger.error("%s publisher failed: %s", name, pub_exc)
        else:
            logger.info("Publishing skipped (run with --publish to enable).")
            print("[INFO] Publishing skipped (no --publish flag).")
        # ─────────────────────────────────────────────────────────────────────

        if errors:
            logger.warning("Digest completed with %d non-fatal errors (digest still saved).", len(errors))
            print(f"[WARN] {len(errors)} non-fatal errors occurred (check logs)")
        sys.exit(0)  # digest was saved — always success even with provider fallbacks

    except KeyboardInterrupt:
        print("\nAborted by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Fatal error in digest run: %s", exc)
        print(f"\n[FAIL] Fatal error: {exc}", file=sys.stderr)
        sys.exit(2)
