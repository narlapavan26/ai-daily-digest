"""
digest_runner/nodes/render_node.py
====================================
Contains `render_digest` — a LangGraph node that renders a FinalDigestSchema
to Markdown and saves it to disk.

Template follows the exact structure defined in MarkdownDigest schema docstring:
  - Header with date + stats
  - Top story (if present)
  - Sections in deterministic order
  - Quick links table
  - Per-source stats table
  - Footer with generation time + providers
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from digest_runner.graph.state import DigestRunState
from digest_runner.schemas.digest_schemas import (
    DigestSection,
    DigestSectionName,
    FinalDigestItem,
    FinalDigestSchema,
    TimeSensitivity,
)

logger = logging.getLogger(__name__)

# ── Section heading map (same order as final_llm_node) ────────────────────────
_SECTION_HEADINGS = {
    DigestSectionName.FRAMEWORK_RELEASES: "🚀 Framework Releases",
    DigestSectionName.MODEL_RELEASES:     "🧠 Model Releases",
    DigestSectionName.NEW_TOOLS:          "🔧 New Tools",
    DigestSectionName.RESEARCH:           "📄 Research Worth Noting",
    DigestSectionName.INFRASTRUCTURE:     "⚙️ Infrastructure",
    DigestSectionName.COMMUNITY_BUZZ:     "💬 Community Buzz",
    DigestSectionName.QUICK_LINKS:        "🔗 Quick Links",
}

_SENSITIVITY_EMOJI = {
    TimeSensitivity.HIGH:   "🔴",
    TimeSensitivity.MEDIUM: "🟡",
    TimeSensitivity.LOW:    "🟢",
}

# Maximum items shown in full detail per section.
# Overflow is moved to Quick Links compact table.
_MAX_ITEMS_PER_SECTION = 7
_USELESS_ACTIONS = {
    "read the full article at the source url",
    "read the full article",
    "visit the source url",
    "try out the new release",
    "try out the new version",
}


# ── Render helpers ─────────────────────────────────────────────────────────────

def _render_item(item: FinalDigestItem, *, heading_level: int = 3) -> str:
    """Render one FinalDigestItem to Markdown."""
    hashes = "#" * heading_level
    lines = [
        f"{hashes} {item.headline}",
        "",
        f"**What happened:** {item.what_happened}",
        "",
        f"**Why it matters:** {item.why_it_matters}",
        "",
        f"**Key takeaway:** _{item.key_takeaway}_",
    ]

    if item.action_hint:
        # Skip generic/useless action hints that add no value
        hint_lower = item.action_hint.lower().strip().rstrip(".")
        if hint_lower not in _USELESS_ACTIONS and len(item.action_hint) > 20:
            lines += ["", f"> 💡 **Action:** {item.action_hint}"]

    tags_str = ", ".join(f"`{t}`" for t in (item.tags or []))
    date_str = item.published_at.strftime("%Y-%m-%d")
    sensitivity = _SENSITIVITY_EMOJI.get(item.time_sensitivity, "")
    lines += [
        "",
        f"🔗 [{item.headline}]({item.url}) · `{item.source.value if hasattr(item.source, 'value') else item.source}` · {date_str}"
        + (f" · {tags_str}" if tags_str else "")
        + (f" · {sensitivity}" if sensitivity else ""),
        "",
    ]
    return "\n".join(lines)


def _render_section(section: DigestSection) -> str:
    """Render one DigestSection to Markdown."""
    heading = _SECTION_HEADINGS.get(section.section, section.title)
    lines = [f"## {heading}", ""]

    if section.section_summary:
        lines += [f"_{section.section_summary}_", ""]

    # Hard cap: show at most _MAX_ITEMS_PER_SECTION items in full detail
    featured = section.items[:_MAX_ITEMS_PER_SECTION]
    overflow  = section.items[_MAX_ITEMS_PER_SECTION:]

    for item in featured:
        lines.append(_render_item(item, heading_level=3))
        lines.append("---")
        lines.append("")

    if overflow:
        lines.append(f"_+ {len(overflow)} more minor updates:_ ")
        overflow_links = ", ".join(
            f"[{item.headline[:60]}]({item.url})" for item in overflow
        )
        lines.append(overflow_links)
        lines.append("")

    return "\n".join(lines)


def _render_quick_links_table(items: List[FinalDigestItem]) -> str:
    """Render quick-links as a Markdown table."""
    lines = [
        "## 🔗 Quick Links",
        "",
        "| # | Title | Source | Tags | Sensitivity |",
        "|---|-------|--------|------|-------------|",
    ]
    for i, item in enumerate(items, 1):
        tags_str = ", ".join(item.tags or [])
        sens = _SENSITIVITY_EMOJI.get(item.time_sensitivity, str(item.time_sensitivity))
        title_link = f"[{item.headline}]({item.url})"
        src_label = item.source.value if hasattr(item.source, 'value') else str(item.source)
        lines.append(
            f"| {i} | {title_link} | `{src_label}` | {tags_str} | {sens} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_stats_table(digest: FinalDigestSchema) -> str:
    """Render per-source stats table."""
    lines = [
        "## 📊 Today's Stats",
        "",
        "| Source | Selected | Reviewed | Drop Rate |",
        "|--------|----------|----------|-----------|",
    ]
    total_selected = 0
    total_reviewed = 0
    for src, counts in sorted(digest.metadata.source_counts.items()):
        sel = counts.get("selected", 0)
        rev = counts.get("raw", 0)
        drop = int((1 - sel / rev) * 100) if rev else 0
        src_label = src.value if hasattr(src, 'value') else str(src)
        lines.append(f"| {src_label} | {sel} | {rev} | {drop}% |")
        total_selected += sel
        total_reviewed += rev
    total_drop = int((1 - total_selected / total_reviewed) * 100) if total_reviewed else 0
    lines += [
        f"| **TOTAL** | **{total_selected}** | **{total_reviewed}** | **{total_drop}%** |",
        "",
    ]
    return "\n".join(lines)


def render_markdown(digest: FinalDigestSchema) -> str:
    """Render the complete FinalDigestSchema to a Markdown string."""
    md = digest.metadata
    sources_str = ", ".join(sorted(s.value if hasattr(s, 'value') else str(s) for s in md.sources_reviewed))

    sections_md: List[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    sections_md.append(f"# 🤖 AI/ML Daily Digest — {md.digest_date}")
    sections_md.append("")
    sections_md.append(
        f"> {md.total_selected} items curated from {md.total_raw_items} reviewed"
    )
    sections_md.append(f"> Sources: {sources_str}")
    sections_md.append("")
    sections_md.append("---")
    sections_md.append("")

    # ── Top Story ─────────────────────────────────────────────────────────────
    if digest.top_story:
        ts = digest.top_story
        sections_md.append("## 🔥 Today's Top Story")
        sections_md.append("")
        sections_md.append(f"### {ts.headline}")
        sections_md.append("")
        sections_md.append(f"**What happened:** {ts.what_happened}")
        sections_md.append("")
        sections_md.append(f"**Why it matters:** {ts.why_it_matters}")
        sections_md.append("")
        sections_md.append(f"**Key takeaway:** _{ts.key_takeaway}_")
        sections_md.append("")
        if ts.action_hint:
            sections_md.append(f"> 💡 **Action:** {ts.action_hint}")
            sections_md.append("")
        date_str = ts.published_at.strftime("%Y-%m-%d")
        sections_md.append(f"🔗 [{ts.headline}]({ts.url}) · `{ts.source.value if hasattr(ts.source, 'value') else ts.source}` · {date_str}")
        sections_md.append("")
        sections_md.append("---")
        sections_md.append("")

    # ── Content Sections ─────────────────────────────────────────────────────
    for section in digest.sections:
        if not section.items:
            continue
        sections_md.append(_render_section(section))

    # ── Quick Links ───────────────────────────────────────────────────────────
    if digest.quick_links:
        sections_md.append(_render_quick_links_table(digest.quick_links))
        sections_md.append("---")
        sections_md.append("")

    # ── Stats ─────────────────────────────────────────────────────────────────
    sections_md.append(_render_stats_table(digest))

    # ── Footer ────────────────────────────────────────────────────────────────
    providers_str = ", ".join(p.value if hasattr(p, 'value') else str(p) for p in md.providers_used)
    gen_time = md.generated_at.strftime("%Y-%m-%d %H:%M")
    sections_md.append(
        f"_Generated {gen_time} UTC · Providers: {providers_str} · Schema v{md.schema_version}_"
    )
    sections_md.append("")

    return "\n".join(sections_md)


def render_digest(state: DigestRunState) -> dict:
    """
    LangGraph node: render the FinalDigestSchema to Markdown and save to disk.

    Reads:
      state["final_digest"] — FinalDigestSchema from final_llm_node
      state["run_date"]     — "YYYY-MM-DD" for the filename

    Returns:
      { "output_path": str }   — absolute path to the saved .md file
    """
    final_digest: Optional[FinalDigestSchema] = state.get("final_digest")
    run_date: str = state.get("run_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if final_digest is None:
        logger.error("render_digest: no final_digest in state — cannot render")
        return {"output_path": "", "errors": ["render_digest: final_digest is None"]}

    # Render to Markdown
    markdown_content = render_markdown(final_digest)

    # Determine output directory — supports DIGEST_OUTPUT_DIR env override
    output_dir = os.environ.get("DIGEST_OUTPUT_DIR", "outputs")
    output_path = Path(output_dir) / f"digest_{run_date}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(markdown_content, encoding="utf-8")

    logger.info(
        "render_digest: saved %d chars to %s",
        len(markdown_content), output_path.resolve(),
    )

    return {"output_path": str(output_path.resolve())}
