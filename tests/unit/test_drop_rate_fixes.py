"""
tests/unit/test_drop_rate_fixes.py
====================================
Smoke + unit tests validating the 6 drop-rate reduction fixes from the
drop_rate_analysis.md artifact.

Priority order matches the artifact:
  P2: Budget caps raised (RSS 12->40, ArXiv 5->12, HN 5->10, Reddit 3->8)
  P3: Staleness window aligned (RSS stale 5->7.0 = rss_days_back=7)
  P5: LLM system prompt softened (thorough not ruthless)
  P6: reject_reason requirement strengthened

Does NOT require MCP server or LLM API keys.
"""
from __future__ import annotations

import pytest

from digest_runner.config.settings import settings
from digest_runner.schemas.digest_schemas import (
    EnrichedItem,
    FastFailVerdict,
    ImpactedAudience,
    InsightExtraction,
    LLMProvider,
    NoveltyType,
    RelevanceAssessment,
    SourceName,
    TimeSensitivity,
    DigestSectionName,
)
from digest_runner.subgraphs.base import (
    _SYSTEM_PROMPT,
    is_junk_release,
    NOVELTY_TO_SECTION,
)
from digest_runner.subgraphs.rss_subgraph import RssSubgraph
from digest_runner.subgraphs.arxiv_subgraph import ArxivSubgraph
from digest_runner.nodes.fast_fail_node import apply_fast_fail


class TestBudgetCaps:
    def test_rss_budget_raised_to_40(self):
        assert settings.rss_subgraph_budget >= 40

    def test_arxiv_budget_raised_to_12(self):
        assert settings.arxiv_budget >= 12

    def test_hackernews_budget_raised_to_10(self):
        assert settings.hackernews_budget >= 10

    def test_reddit_budget_raised_to_8(self):
        assert settings.reddit_budget >= 8

    def test_rss_subgraph_budget_property_matches_settings(self):
        assert RssSubgraph().budget >= 40

    def test_arxiv_subgraph_budget_property_matches_settings(self):
        assert ArxivSubgraph().budget >= 12


class TestStalenessAlignment:
    def test_rss_stale_days_lte_days_back(self):
        assert settings.rss_fast_fail_stale_days <= settings.rss_days_back

    def test_rss_stale_days_is_7(self):
        assert settings.rss_fast_fail_stale_days == 7.0

    def test_rss_item_at_6_days_passes_fast_fail(self, make_normalized_item):
        subgraph = RssSubgraph()
        item = make_normalized_item(item_id="rss:fresh-6d", source=SourceName.RSS_FEEDS, days_old=6.0)
        batch = apply_fast_fail([item], subgraph)
        assert len(batch.passed) == 1, f"6d item should pass (stale=7), dropped: {[d.reason for d in batch.dropped]}"

    def test_rss_item_at_7_point_1_days_dropped(self, make_normalized_item):
        subgraph = RssSubgraph()
        item = make_normalized_item(item_id="rss:stale-7.1d", source=SourceName.RSS_FEEDS, days_old=7.1)
        batch = apply_fast_fail([item], subgraph)
        assert len(batch.dropped) == 1
        assert batch.dropped[0].verdict == FastFailVerdict.DROP_STALE


class TestSystemPromptTone:
    def test_prompt_not_ruthless(self):
        assert "ruthless" not in _SYSTEM_PROMPT.lower()

    def test_prompt_says_thorough(self):
        assert "thorough" in _SYSTEM_PROMPT.lower()

    def test_prompt_errs_on_inclusion(self):
        assert "inclusion" in _SYSTEM_PROMPT.lower() or "keep it" in _SYSTEM_PROMPT.lower()

    def test_prompt_not_drop_default(self):
        assert "err on the side of dropping" not in _SYSTEM_PROMPT.lower()


class TestRejectReasonEnforcement:
    def test_missing_reject_reason_auto_filled(self):
        assessment = RelevanceAssessment(item_id="rss:001", is_relevant=False, relevance_score=0.1)
        assert assessment.reject_reason is not None and len(assessment.reject_reason) > 0

    def test_relevance_score_clamped_above_1(self):
        assessment = RelevanceAssessment(item_id="rss:002", is_relevant=True, relevance_score=1.5)
        assert assessment.relevance_score <= 1.0

    def test_relevance_score_clamped_below_0(self):
        assessment = RelevanceAssessment(item_id="rss:003", is_relevant=False, relevance_score=-0.5)
        assert assessment.relevance_score >= 0.0

    def test_id_field_aliased_to_item_id(self):
        assessment = RelevanceAssessment(**{"id": "rss:004", "is_relevant": True, "relevance_score": 0.7})
        assert assessment.item_id == "rss:004"


class TestPydanticSchemaRobustness:
    def test_insight_unknown_novelty_type_mapped_to_update(self):
        ins = InsightExtraction(
            item_id="t:001", change_summary="Some interesting change happened here that matters.",
            significance="This matters because practitioners will notice it daily.",
            novelty_type="unknown_fancy_type", impacted_audience=["ml_engineers"],
            time_sensitivity="medium", actionable_insight="Check the project page.",
        )
        assert ins.novelty_type in {e.value for e in NoveltyType}

    def test_insight_uppercase_novelty_type_normalized(self):
        ins = InsightExtraction(
            item_id="t:002", change_summary="Framework version 2.0 was released with breaking changes.",
            significance="Developers must upgrade their code to use the new API structure.",
            novelty_type="NEW_RELEASE", impacted_audience=["ml_engineers"],
            time_sensitivity="high", actionable_insight="pip install framework==2.0",
        )
        assert ins.novelty_type == "new_release"

    def test_insight_invalid_time_sensitivity_defaults_to_medium(self):
        ins = InsightExtraction(
            item_id="t:003", change_summary="Some important change was made to the framework today.",
            significance="Practitioners should be aware of this development this week.",
            novelty_type="update", impacted_audience=["ml_engineers"],
            time_sensitivity="URGENT", actionable_insight="Review the changelog.",
        )
        assert ins.time_sensitivity == "medium"

    def test_insight_invalid_audience_filtered_to_default(self):
        ins = InsightExtraction(
            item_id="t:004", change_summary="A significant improvement was released for the framework.",
            significance="This helps ML engineers deploy faster in production.",
            novelty_type="new_release", impacted_audience=["robot_builders", "space_engineers"],
            time_sensitivity="medium", actionable_insight="Upgrade to get the improvements.",
        )
        assert ins.impacted_audience == ["ml_engineers"]

    def test_insight_overlong_change_summary_truncated(self):
        ins = InsightExtraction(
            item_id="t:005", change_summary="A" * 600,
            significance="This is significant for practitioners building LLM systems.",
            novelty_type="update", impacted_audience=["ml_engineers"],
            time_sensitivity="medium", actionable_insight="Review the full changelog now.",
        )
        assert len(ins.change_summary) <= 500

    def test_novelty_to_section_mapping_complete(self):
        for novelty in NoveltyType:
            assert novelty in NOVELTY_TO_SECTION, f"NoveltyType.{novelty.name} missing from NOVELTY_TO_SECTION"


class TestJunkFilter:
    def _make_item(self, title, url="https://example.com/releases/tag/v1.0"):
        from datetime import datetime, timezone
        from digest_runner.schemas.digest_schemas import NormalizedItem
        return NormalizedItem(
            id="test:junk", source=SourceName.RSS_FEEDS, title=title,
            url=url, published_at=datetime.now(timezone.utc),
            content_for_llm="Some content that is definitely long enough to pass the length check.",
            days_old=1.0,
        )

    def test_pytorch_trunk_tag_is_junk(self):
        is_junk, _ = is_junk_release(self._make_item("trunk/041915122a828a989e495a9a07f7fb9e2dfe4d72"))
        assert is_junk

    def test_llamacpp_build_tag_is_junk(self):
        is_junk, _ = is_junk_release(self._make_item("b9741 Released"))
        assert is_junk

    def test_scoped_npm_package_is_junk(self):
        is_junk, _ = is_junk_release(self._make_item("@gradio/video@0.21.0"))
        assert is_junk

    def test_dev_build_is_junk(self):
        is_junk, _ = is_junk_release(self._make_item("Streamlit 1.58.1.dev20260619"))
        assert is_junk

    def test_rc_build_is_junk(self):
        is_junk, _ = is_junk_release(self._make_item("Ollama v0.30.10-rc1"))
        assert is_junk

    def test_real_release_not_junk(self):
        is_junk, reason = is_junk_release(self._make_item("LangGraph 0.4.0 Released with Native Streaming Support"))
        assert not is_junk, f"Real release should NOT be junk, got: {reason}"

    def test_huggingface_blog_not_junk(self):
        is_junk, reason = is_junk_release(self._make_item("NVIDIA Blackwell Tops MLPerf Training 6.0 Benchmarks"))
        assert not is_junk, f"HuggingFace blog should NOT be junk, got: {reason}"
