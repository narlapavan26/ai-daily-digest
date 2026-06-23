"""
tests/unit/conftest.py (also used by tests/integration/)
==========================================================
Shared pytest fixtures for the digest_runner test suite.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import pytest

from digest_runner.schemas.digest_schemas import (
    DeduplicationResult,
    DigestMetadata,
    DigestSectionName,
    EnrichedItem,
    FastFailBatch,
    FastFailResult,
    FastFailVerdict,
    FinalDigestItem,
    FinalDigestSchema,
    ImpactedAudience,
    LLMProvider,
    NormalizedItem,
    NoveltyType,
    SourceName,
    SubgraphOutput,
    TimeSensitivity,
)


@pytest.fixture
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def make_normalized_item(utc_now):
    """Factory fixture: create a NormalizedItem with sensible defaults."""
    def _make(
        item_id: str = "arxiv:2401.00001",
        source: SourceName = SourceName.ARXIV,
        title: str = "LLM Agents with Tool Use",
        url: str = "https://arxiv.org/abs/2401.00001",
        content: str = "This paper proposes a novel approach to LLM agent tool use that improves accuracy by 15%.",
        days_old: float = 1.0,
    ) -> NormalizedItem:
        return NormalizedItem(
            id=item_id,
            source=source,
            title=title,
            url=url,
            published_at=utc_now,
            content_for_llm=content,
            quality_signals={"stars": 500} if source == SourceName.ARXIV else {},
            days_old=days_old,
        )
    return _make


@pytest.fixture
def sample_normalized_item(make_normalized_item) -> NormalizedItem:
    return make_normalized_item()


@pytest.fixture
def make_enriched_item(utc_now):
    """Factory fixture: create an EnrichedItem with sensible defaults."""
    def _make(
        item_id: str = "arxiv:2401.00001",
        source: SourceName = SourceName.ARXIV,
        title: str = "LLM Agents with Tool Use",
        url: str = "https://arxiv.org/abs/2401.00001",
        relevance_score: float = 0.85,
        time_sensitivity: TimeSensitivity = TimeSensitivity.HIGH,
        novelty_type: NoveltyType = NoveltyType.BREAKTHROUGH,
        section: DigestSectionName = DigestSectionName.RESEARCH,
    ) -> EnrichedItem:
        return EnrichedItem(
            id=item_id,
            source=source,
            title=title,
            url=url,
            published_at=utc_now,
            days_old=1.0,
            quality_signals={},
            is_relevant=True,
            relevance_score=relevance_score,
            change_summary="Added a novel multi-step tool selection mechanism.",
            significance="Developers using agentic frameworks will benefit from 15% better accuracy.",
            novelty_type=novelty_type,
            impacted_audience=[ImpactedAudience.AGENT_BUILDERS],
            time_sensitivity=time_sensitivity,
            actionable_insight="Integrate this paper's approach into your LangGraph agent.",
            confidence=0.85,
            digest_section=section,
            enriched_by=LLMProvider.GROQ,
            selection_rank=1,
        )
    return _make


@pytest.fixture
def sample_enriched_item(make_enriched_item) -> EnrichedItem:
    return make_enriched_item()


@pytest.fixture
def make_subgraph_output(make_enriched_item, utc_now):
    """Factory fixture: create a SubgraphOutput with one enriched item."""
    def _make(
        source: SourceName = SourceName.ARXIV,
        items: Optional[List[EnrichedItem]] = None,
        total_reviewed: int = 10,
    ) -> SubgraphOutput:
        enriched = items if items is not None else [make_enriched_item(
            item_id=f"{source.value}:test001",
            source=source,
        )]
        return SubgraphOutput(
            source=source,
            enriched_items=enriched,
            total_reviewed=total_reviewed,
            total_selected=len(enriched),
            fast_fail_dropped=2,
            llm_dropped=max(0, total_reviewed - 2 - len(enriched)),
            model_used=LLMProvider.GROQ,
            processing_ms=1200.0,
        )
    return _make


@pytest.fixture
def sample_subgraph_output(make_subgraph_output) -> SubgraphOutput:
    return make_subgraph_output()


@pytest.fixture
def two_subgraph_outputs(make_subgraph_output, make_enriched_item) -> List[SubgraphOutput]:
    """Two SubgraphOutputs from different sources — for merger tests."""
    arxiv_item = make_enriched_item(
        item_id="arxiv:paper1",
        source=SourceName.ARXIV,
        title="Efficient Attention Mechanisms for Long Contexts",
        url="https://arxiv.org/abs/2401.00001",
        relevance_score=0.90,
        time_sensitivity=TimeSensitivity.LOW,
        novelty_type=NoveltyType.BREAKTHROUGH,
        section=DigestSectionName.RESEARCH,
    )
    hn_item = make_enriched_item(
        item_id="hackernews:story123",
        source=SourceName.HACKERNEWS,
        title="LangGraph 0.3.0 Released with Native Streaming Support",
        url="https://news.ycombinator.com/item?id=story123",
        relevance_score=0.95,
        time_sensitivity=TimeSensitivity.HIGH,
        novelty_type=NoveltyType.NEW_RELEASE,
        section=DigestSectionName.FRAMEWORK_RELEASES,
    )
    return [
        make_subgraph_output(source=SourceName.ARXIV, items=[arxiv_item]),
        make_subgraph_output(source=SourceName.HACKERNEWS, items=[hn_item]),
    ]


@pytest.fixture
def mock_digest_run_state(two_subgraph_outputs) -> dict:
    """A minimal DigestRunState dict suitable for testing merger_node."""
    return {
        "run_date": "2026-06-10",
        "run_id": "test-run-uuid-1234",
        "active_sources": ["arxiv", "hackernews"],
        "subgraph_outputs": two_subgraph_outputs,
        "errors": [],
    }


@pytest.fixture
def mock_final_digest_schema(make_enriched_item, utc_now) -> FinalDigestSchema:
    """Minimal FinalDigestSchema for render_node tests."""
    from digest_runner.schemas.digest_schemas import DigestSection

    top_item = FinalDigestItem(
        id="hackernews:story123",
        source=SourceName.HACKERNEWS,
        novelty_type=NoveltyType.NEW_RELEASE,
        section=DigestSectionName.FRAMEWORK_RELEASES,
        url="https://news.ycombinator.com/item?id=story123",
        published_at=utc_now,
        tags=["langgraph", "release", "streaming"],
        headline="LangGraph 0.3.0 ships native streaming support",
        what_happened="LangGraph 0.3.0 was released with built-in streaming for all node types.",
        why_it_matters="This means developers can now stream partial results without custom middleware.",
        key_takeaway="Upgrade to LangGraph 0.3.0 to get streaming for free.",
        action_hint="pip install langgraph==0.3.0",
        time_sensitivity=TimeSensitivity.HIGH,
        confidence_score=0.95,
    )
    section_item = FinalDigestItem(
        id="arxiv:paper1",
        source=SourceName.ARXIV,
        novelty_type=NoveltyType.BREAKTHROUGH,
        section=DigestSectionName.RESEARCH,
        url="https://arxiv.org/abs/2401.99999",
        published_at=utc_now,
        tags=["attention", "long-context", "research"],
        headline="Sparse attention cuts long-context memory by 60%",
        what_happened="Researchers published a sparse attention variant that reduces memory by 60% on 128K contexts.",
        why_it_matters="This fixes the memory wall problem when running large-context models in production.",
        key_takeaway="This sparse attention method is production-ready and can be integrated into existing frameworks.",
        time_sensitivity=TimeSensitivity.LOW,
        confidence_score=0.88,
    )

    metadata = DigestMetadata(
        digest_date="2026-06-10",
        total_raw_items=20,
        total_selected=2,
        sources_reviewed=[SourceName.ARXIV, SourceName.HACKERNEWS],
        providers_used=[LLMProvider.GROQ],
        source_counts={
            "arxiv":      {"raw": 10, "selected": 1, "dropped": 9},
            "hackernews": {"raw": 10, "selected": 1, "dropped": 9},
        },
    )

    research_section = DigestSection(
        section=DigestSectionName.RESEARCH,
        title="📄 Research Worth Noting",
        emoji="📄",
        items=[section_item],
        item_count=1,
    )

    return FinalDigestSchema(
        metadata=metadata,
        top_story=top_item,
        sections=[research_section],
        quick_links=[section_item],
    )
