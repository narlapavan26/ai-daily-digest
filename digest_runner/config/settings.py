"""
Runtime configuration for the digest runner.

All tunable values for every source subgraph are here so you can change
them via .env without touching source code. Loaded via pydantic-settings.

Usage:
    from digest_runner.config.settings import settings
    budget = settings.arxiv_budget
"""

from __future__ import annotations

import json
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, field_validator, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class DigestSettings(BaseSettings):
    """Loads from environment / .env — extra env keys are ignored."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        str_strip_whitespace=True,
        validate_default=True,
    )

    # ── LLM API Keys ─────────────────────────────────────────────────────────
    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq API key. Get at https://console.groq.com",
    )
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key. Get at https://aistudio.google.com",
    )
    cerebras_api_key: Optional[str] = Field(
        default=None,
        description="Cerebras API key. Get at https://cloud.cerebras.ai",
    )
    openrouter_api_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("OPENROUTER_API_KEY", "openrouter_api_key")
    )
    github_models_api_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("GITHUB_TOKEN", "GITHUB_MODELS_API_KEY")
    )
    ollama_api_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("OLLAMA_API_KEY", "ollama_api_key")
    )
    sambanova_api_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("SAMBANOVA_API_KEY", "sambanova_api_key")
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Base URL for local Ollama server.",
    )
    ollama_model: str = Field(
        default="llama3.2",
        description="Ollama model name to use (must be pulled locally).",
    )

    # ── MCP Server connection ────────────────────────────────────────────────
    # pyrefly: ignore [bad-assignment]
    mcp_base_url: AnyHttpUrl = Field(
        default="http://127.0.0.1:8000",
        description="Base URL of the MCP FastAPI server (no trailing slash).",
    )
    mcp_bearer_token: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=2048,
        description="Optional Authorization bearer for Horizon-hosted MCP.",
    )
    mcp_request_timeout_seconds: float = Field(
        default=120.0,
        ge=5.0,
        le=300.0,
        description="HTTP timeout for each MCP call.",
    )

    # ── LLM enrichment (shared across all subgraphs) ─────────────────────────
    llm_batch_size: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Items per LLM call in relevance/insight passes.",
    )
    llm_inter_batch_sleep_seconds: float = Field(
        default=2.0,
        ge=0.0,
        le=30.0,
        description="Sleep between LLM batches to respect free-tier rate limits.",
    )
    llm_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Instructor retry count on schema-validation failures.",
    )

    # ── RSS subgraph ─────────────────────────────────────────────────────────
    rss_max_items_per_feed: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Max items per feed when calling POST /fetch/rss.",
    )
    rss_max_total_items: int = Field(
        default=200,
        ge=10,
        le=1000,
        description="Hard cap on total RSS items returned across all feeds.",
    )
    rss_days_back: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days window for RSS MCP requests.",
    )
    rss_fast_fail_stale_days: float = Field(
        default=7.0,
        ge=0.5,
        le=30.0,
        description=(
            "Fast-fail staleness threshold for RSS items (days). "
            "Must be <= rss_days_back to avoid fetching content that is immediately dropped."
        ),
    )
    rss_min_content_length: int = Field(
        default=20,
        ge=5,
        le=200,
        description="Fast-fail: drop RSS items with fewer chars than this in content_for_llm.",
    )
    rss_subgraph_budget: int = Field(
        default=40,
        ge=1,
        le=100,
        description="Max enriched RSS items to keep per run.",
    )

    # ── ArXiv subgraph ───────────────────────────────────────────────────────
    arxiv_queries: List[str] = Field(
        default=[
            "large language models agents tools",
            "llm inference serving optimization quantization",
            "multimodal foundation models vision language",
            "retrieval augmented generation RAG vector search",
            "diffusion models image video generation",
            "reinforcement learning from human feedback RLHF alignment",
            "transformer architecture attention efficiency",
            "ai safety interpretability alignment",
        ],
        description="List of ArXiv search queries. Each runs separately; results are deduped.",
    )
    arxiv_max_results: int = Field(
        default=15,
        ge=1,
        le=100,
        description="Max papers to fetch per query from ArXiv.",
    )
    arxiv_days_back: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days window for ArXiv paper freshness.",
    )
    arxiv_stale_days: float = Field(
        default=7.0,
        ge=0.5,
        le=30.0,
        description="Fast-fail staleness threshold for ArXiv items (days).",
    )
    arxiv_budget: int = Field(
        default=12,
        ge=1,
        le=20,
        description="Max enriched ArXiv papers to keep per run.",
    )
    arxiv_min_abstract_length: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Fast-fail: drop papers with abstract shorter than this.",
    )

    # ── GitHub subgraph ──────────────────────────────────────────────────────
    github_topics: List[str] = Field(
        default=[
            "llm", "agent", "rag", "langchain", "langgraph", "llama",
            "openai", "diffusion", "vllm", "ollama", "huggingface",
            "embeddings", "vector-database", "ai-agent", "mcp",
            "crewai", "autogen", "dspy", "llamaindex", "haystack",
        ],
        description="GitHub topic keywords for repo search. All passed as OR query.",
    )
    github_max_results: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Max GitHub repos + releases to fetch per run.",
    )
    github_days_back: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days window for GitHub activity.",
    )
    github_stale_days: float = Field(
        default=3.0,
        ge=0.5,
        le=14.0,
        description="Fast-fail staleness threshold for GitHub repos (days). Releases are never dropped.",
    )
    github_budget: int = Field(
        default=15,
        ge=1,
        le=50,
        description="Max enriched GitHub items to keep per run.",
    )
    github_min_stars: int = Field(
        default=50,
        ge=0,
        le=10000,
        description="Minimum stars for a trending repo to pass fast-fail.",
    )
    github_min_content_length: int = Field(
        default=20,
        ge=5,
        le=200,
        description="Fast-fail: drop GitHub items with fewer chars than this.",
    )

    # ── HackerNews subgraph ──────────────────────────────────────────────────
    hackernews_max_results: int = Field(
        default=30,
        ge=1,
        le=50,
        description="Max HN stories to fetch per run.",
    )
    hackernews_min_score: int = Field(
        default=10,
        ge=0,
        le=1000,
        description="Minimum HN points to request from Algolia API. Lowered to 10 so slow news days still yield results; fast-fail enforces the real quality bar.",
    )
    hackernews_days_back: int = Field(
        default=3,
        ge=1,
        le=14,
        description="Days window for HN stories.",
    )
    hackernews_stale_days: float = Field(
        default=3.0,
        ge=0.5,
        le=14.0,
        description="Fast-fail staleness threshold for HN stories (days).",
    )
    hackernews_min_points_fast_fail: int = Field(
        default=10,
        ge=0,
        le=500,
        description="Local fast-fail: drop HN stories with points < this value.",
    )
    hackernews_min_community_signal: float = Field(
        default=0.0,
        ge=0.0,
        description="Fast-fail: drop HN items where points*log(1+comments) < this threshold.",
    )
    hackernews_budget: int = Field(
        default=10,
        ge=1,
        le=25,
        description="Max enriched HN stories to keep per run.",
    )

    # ── HuggingFace subgraph ─────────────────────────────────────────────────
    huggingface_max_models: int = Field(
        default=15,
        ge=1,
        le=30,
        description="Max trending HuggingFace Hub models to fetch.",
    )
    huggingface_max_blogs: int = Field(
        default=8,
        ge=0,
        le=20,
        description="Max HuggingFace blog posts to fetch.",
    )
    huggingface_days_back: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days window for HuggingFace models and blog posts.",
    )
    huggingface_stale_days: float = Field(
        default=7.0,
        ge=0.5,
        le=30.0,
        description="Fast-fail staleness threshold for HuggingFace items (days).",
    )
    huggingface_budget: int = Field(
        default=7,
        ge=1,
        le=20,
        description="Max enriched HuggingFace items to keep per run.",
    )
    huggingface_min_downloads: int = Field(
        default=100,
        ge=0,
        description="Fast-fail: drop HF models with fewer monthly downloads than this.",
    )

    # ── Reddit subgraph ──────────────────────────────────────────────────────
    reddit_subreddits: List[str] = Field(
        default=[
            "MachineLearning", "LocalLLaMA", "artificial", "mlops",
            "LanguageModelEvaluation", "ArtificialIntelligence",
            "learnmachinelearning", "deeplearning",
        ],
        description="Default subreddits to monitor.",
    )
    reddit_max_posts_per_sub: int = Field(
        default=5,
        ge=0,
        le=25,
        description="Max posts to fetch per subreddit. Set to 0 to disable Reddit fetching.",
    )
    reddit_days_back: int = Field(
        default=3,
        ge=1,
        le=14,
        description="Days window for Reddit posts.",
    )
    reddit_min_score: int = Field(
        default=10,
        ge=0,
        le=10000,
        description="Minimum Reddit post score (upvotes) for fetching and fast-fail.",
    )
    reddit_stale_days: float = Field(
        default=3.0,
        ge=0.5,
        le=14.0,
        description="Fast-fail staleness threshold for Reddit posts (days).",
    )
    reddit_min_comments: int = Field(
        default=0,
        ge=0,
        description="Fast-fail: drop Reddit posts with fewer comments than this.",
    )
    reddit_budget: int = Field(
        default=8,
        ge=1,
        le=25,
        description="Max enriched Reddit posts to keep per run.",
    )
    # Reddit OAuth credentials (required since Reddit blocked unauthenticated access in 2023)
    reddit_client_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("REDDIT_CLIENT_ID", "reddit_client_id"),
        description="Reddit OAuth app client ID. Create at https://www.reddit.com/prefs/apps",
    )
    reddit_client_secret: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("REDDIT_CLIENT_SECRET", "reddit_client_secret"),
        description="Reddit OAuth app client secret.",
    )
    reddit_username: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("REDDIT_USERNAME", "reddit_username"),
        description="Reddit account username for OAuth 'password' grant.",
    )
    reddit_password: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("REDDIT_PASSWORD", "reddit_password"),
        description="Reddit account password for OAuth 'password' grant.",
    )

    # ── StackOverflow subgraph ───────────────────────────────────────────────
    stackoverflow_tags: List[str] = Field(
        default=[
            "llm", "langchain", "openai-api", "huggingface", "pytorch",
            "transformers", "langchain-python", "vector-database",
            "rag", "llama-index", "semantic-search", "embeddings",
        ],
        description="Default StackOverflow tags to query.",
    )
    stackoverflow_max_results: int = Field(
        default=25,
        ge=1,
        le=50,
        description="Max StackOverflow questions to fetch.",
    )
    stackoverflow_days_back: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days window for StackOverflow questions.",
    )
    stackoverflow_min_score: int = Field(
        default=1,
        ge=0,
        le=1000,
        description="Minimum SO question score for fetching. Lowered to 1 so more results come through; fast-fail (min_score=3) is the real quality gate.",
    )
    stackoverflow_stale_days: float = Field(
        default=7.0,
        ge=0.5,
        le=30.0,
        description="Fast-fail staleness threshold for SO questions (days).",
    )
    stackoverflow_require_answer: bool = Field(
        default=False,
        description="Fast-fail: if True, drop questions with no accepted answer.",
    )
    stackoverflow_budget: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Max enriched SO questions to keep per run.",
    )

    @field_validator("mcp_bearer_token", mode="before")
    @classmethod
    def _empty_token_to_none(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    # ── Publishers ───────────────────────────────────────────────────────────
    discord_webhook_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("DISCORD_WEBHOOK_URL", "discord_webhook_url"),
        description="Discord Webhook URL to post the digest.",
    )
    telegram_bot_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "telegram_bot_token"),
        description="Telegram Bot API Token.",
    )
    telegram_chat_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_CHAT_ID", "telegram_chat_id"),
        description="Telegram Chat ID (or channel @name) to post to.",
    )
    smtp_server: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_SERVER", "smtp_server"),
        description="SMTP server address for email publishing.",
    )
    smtp_port: int = Field(
        default=587,
        validation_alias=AliasChoices("SMTP_PORT", "smtp_port"),
        description="SMTP server port.",
    )
    smtp_username: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_USERNAME", "smtp_username"),
        description="SMTP authentication username.",
    )
    smtp_password: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_PASSWORD", "smtp_password"),
        description="SMTP authentication password.",
    )
    email_to: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("EMAIL_TO", "email_to"),
        description="Comma-separated list of recipient email addresses.",
    )
    email_from: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("EMAIL_FROM", "email_from"),
        description="Sender email address.",
    )


# Singleton — import `settings` everywhere, never re-instantiate.
settings = DigestSettings()
