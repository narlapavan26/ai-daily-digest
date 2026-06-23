"""
Verified RSS/Atom sources for the AI/ML digest.

Must stay in sync with ``tests/test_rss_feeds.py`` → ``feeds_to_collect`` (the list used
for === DATA OUTPUT === / ``collected_api_data.json``), so MCP and test harness use the same URLs
and section labels.

NOISE REDUCTION (2025-06-21):
Removed feeds that generate excessive junk:
  - PyTorch Releases: produces CI commit hash tags (trunk/, viable/strict/) as "releases"
  - Gradio Releases: monorepo sub-packages (@gradio/video, @gradio/timer, etc.)
  - Composio Releases: monorepo sub-packages (@composio/core, @composio/langchain, etc.)
  - Streamlit Releases: daily dev builds (1.58.1.dev20260619, etc.)
  - GitHub Discussions: typically GitHub issues/support, not news
These 5 feed types were responsible for ~55 of 87 FastFail drops (63%).
"""

from __future__ import annotations

# (feed_display_name, feed_url, section) — same order and strings as test_rss_feeds.py
RSS_VERIFIED_FEEDS: list[tuple[str, str, str]] = [
    # SECTION A — Company & Lab Blogs
    ("HuggingFace Blog", "https://huggingface.co/blog/feed.xml", "Company Blogs"),
    ("Anthropic News", "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml", "Company Blogs"),
    ("Google Research", "https://research.google/blog/rss", "Company Blogs"),
    ("DeepMind Blog", "https://www.deepmind.com/blog/rss.xml", "Company Blogs"),
    ("AWS ML Blog", "https://aws.amazon.com/blogs/machine-learning/feed/", "Company Blogs"),
    ("NVIDIA Developer", "https://developer.nvidia.com/blog/feed/", "Company Blogs"),
    ("Weights & Biases", "https://wandb.ai/fully-connected/rss.xml", "Company Blogs"),
    ("OpenAI News", "https://openai.com/news/rss.xml", "Company Blogs"),
    ("Meta AI FAIR", "https://research.facebook.com/feed/", "Company Blogs"),
    ("Microsoft Research", "https://www.microsoft.com/en-us/research/blog/feed/", "Company Blogs"),
    ("Azure AI Blog", "https://azure.microsoft.com/en-us/blog/tag/ai/feed/", "Company Blogs"),
    ("Google Cloud AI Blog", "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/", "Company Blogs"),
    ("Apple ML Research", "https://machinelearning.apple.com/rss.xml", "Company Blogs"),
    # SECTION B — Newsletters & Blogs
    ("Import AI", "https://importai.substack.com/feed", "Newsletters"),
    ("BAIR Blog", "https://bair.berkeley.edu/blog/feed.xml", "Newsletters"),
    ("KDnuggets", "https://www.kdnuggets.com/feed", "Newsletters"),
    ("Towards Data Science", "https://medium.com/feed/towards-data-science", "Newsletters"),
    ("Analytics Vidhya", "https://www.analyticsvidhya.com/feed/", "Newsletters"),
    ("MarkTechPost", "https://www.marktechpost.com/feed/", "Newsletters"),
    ("The Gradient", "https://thegradient.pub/rss/", "Newsletters"),
    ("The Algorithmic Bridge", "https://thealgorithmicbridge.substack.com/feed", "Newsletters"),
    ("The Decoder", "https://the-decoder.com/feed/", "Newsletters"),
    ("Sebastian Raschka", "https://magazine.sebastianraschka.com/feed", "Newsletters"),
    ("Chip Huyen Blog", "https://huyenchip.com/feed.xml", "Newsletters"),
    # SECTION C — Agentic Framework Blogs
    ("LangChain Blog", "https://blog.langchain.com/rss", "Framework Blogs"),
    ("LlamaIndex Blog", "https://medium.com/feed/llamaindex-blog", "Framework Blogs"),
    # SECTION D — Agentic Framework Releases
    ("LangChain Releases", "https://github.com/langchain-ai/langchain/releases.atom", "Agentic Releases"),
    ("LangGraph Releases", "https://github.com/langchain-ai/langgraph/releases.atom", "Agentic Releases"),
    ("LlamaIndex Releases", "https://github.com/run-llama/llama_index/releases.atom", "Agentic Releases"),
    ("CrewAI Releases", "https://github.com/crewAIInc/crewAI/releases.atom", "Agentic Releases"),
    ("AutoGen Releases", "https://github.com/microsoft/autogen/releases.atom", "Agentic Releases"),
    ("Haystack Releases", "https://github.com/deepset-ai/haystack/releases.atom", "Agentic Releases"),
    ("Flowise Releases", "https://github.com/FlowiseAI/Flowise/releases.atom", "Agentic Releases"),
    ("AutoGPT Releases", "https://github.com/Significant-Gravitas/AutoGPT/releases.atom", "Agentic Releases"),
    ("DSPy Releases", "https://github.com/stanfordnlp/dspy/releases.atom", "Agentic Releases"),
    ("Pydantic AI Releases", "https://github.com/pydantic/pydantic-ai/releases.atom", "Agentic Releases"),
    ("Semantic Kernel Releases", "https://github.com/microsoft/semantic-kernel/releases.atom", "Agentic Releases"),
    ("phidata Releases", "https://github.com/phidatahq/phidata/releases.atom", "Agentic Releases"),
    ("smolagents Releases", "https://github.com/huggingface/smolagents/releases.atom", "Agentic Releases"),
    ("OpenHands Releases", "https://github.com/All-Hands-AI/OpenHands/releases.atom", "Agentic Releases"),
    ("MetaGPT Releases", "https://github.com/geekan/MetaGPT/releases.atom", "Agentic Releases"),
    ("GPT Engineer Releases", "https://github.com/gpt-engineer-org/gpt-engineer/releases.atom", "Agentic Releases"),
    ("BrowserUse Releases", "https://github.com/browser-use/browser-use/releases.atom", "Agentic Releases"),
    # NOTE: Composio Releases removed — monorepo generates @composio/* subpackage spam
    # SECTION E — Backend & Infra Framework Releases
    ("FastAPI Releases", "https://github.com/fastapi/fastapi/releases.atom", "Backend Releases"),
    ("Flask Releases", "https://github.com/pallets/flask/releases.atom", "Backend Releases"),
    ("Django Releases", "https://github.com/django/django/releases.atom", "Backend Releases"),
    # NOTE: Streamlit Releases removed — generates daily dev builds (1.x.dev20260619)
    # NOTE: Gradio Releases removed — generates @gradio/* monorepo subpackage releases
    ("Ray Releases", "https://github.com/ray-project/ray/releases.atom", "Backend Releases"),
    ("MLflow Releases", "https://github.com/mlflow/mlflow/releases.atom", "Backend Releases"),
    ("BentoML Releases", "https://github.com/bentoml/BentoML/releases.atom", "Backend Releases"),
    ("Lightning Releases", "https://github.com/Lightning-AI/pytorch-lightning/releases.atom", "Backend Releases"),
    ("LangServe Releases", "https://github.com/langchain-ai/langserve/releases.atom", "Backend Releases"),
    ("Chainlit Releases", "https://github.com/Chainlit/chainlit/releases.atom", "Backend Releases"),
    ("Litestar Releases", "https://github.com/litestar-org/litestar/releases.atom", "Backend Releases"),
    ("Starlette Releases", "https://github.com/encode/starlette/releases.atom", "Backend Releases"),
    ("Uvicorn Releases", "https://github.com/encode/uvicorn/releases.atom", "Backend Releases"),
    ("Celery Releases", "https://github.com/celery/celery/releases.atom", "Backend Releases"),
    ("Airflow Releases", "https://github.com/apache/airflow/releases.atom", "Backend Releases"),
    ("Prefect Releases", "https://github.com/PrefectHQ/prefect/releases.atom", "Backend Releases"),
    ("Temporal Releases", "https://github.com/temporalio/temporal/releases.atom", "Backend Releases"),
    # SECTION F — ML/AI Core Framework Releases
    # NOTE: PyTorch Releases removed — generates CI commit hash tags (trunk/, viable/strict/)
    ("Transformers Releases", "https://github.com/huggingface/transformers/releases.atom", "ML Core Releases"),
    ("Diffusers Releases", "https://github.com/huggingface/diffusers/releases.atom", "ML Core Releases"),
    ("vLLM Releases", "https://github.com/vllm-project/vllm/releases.atom", "ML Core Releases"),
    ("Ollama Releases", "https://github.com/ollama/ollama/releases.atom", "ML Core Releases"),
    ("Unsloth Releases", "https://github.com/unslothai/unsloth/releases.atom", "ML Core Releases"),
    ("Instructor Releases", "https://github.com/instructor-ai/instructor/releases.atom", "ML Core Releases"),
    ("Qdrant Releases", "https://github.com/qdrant/qdrant/releases.atom", "ML Core Releases"),
    ("Chroma Releases", "https://github.com/chroma-core/chroma/releases.atom", "ML Core Releases"),
    ("Weaviate Releases", "https://github.com/weaviate/weaviate/releases.atom", "ML Core Releases"),
    ("TensorFlow Releases", "https://github.com/tensorflow/tensorflow/releases.atom", "ML Core Releases"),
    ("JAX Releases", "https://github.com/jax-ml/jax/releases.atom", "ML Core Releases"),
    ("ONNX Runtime Releases", "https://github.com/microsoft/onnxruntime/releases.atom", "ML Core Releases"),
    ("llama.cpp Releases", "https://github.com/ggerganov/llama.cpp/releases.atom", "ML Core Releases"),
    ("LocalAI Releases", "https://github.com/mudler/LocalAI/releases.atom", "ML Core Releases"),
    ("LiteLLM Releases", "https://github.com/BerriAI/litellm/releases.atom", "ML Core Releases"),
    ("Milvus Releases", "https://github.com/milvus-io/milvus/releases.atom", "ML Core Releases"),
    ("FAISS Releases", "https://github.com/facebookresearch/faiss/releases.atom", "ML Core Releases"),
    # NOTE: GitHub Discussions feeds removed — these are support tickets / Q&A, not news
    # SECTION H — MLOps Blogs
    ("Streamlit Blog", "https://blog.streamlit.io/feed/", "MLOps Blogs"),
    ("Replicate Blog", "https://replicate.com/blog/rss", "MLOps Blogs"),
    # SECTION L — Podcasts
    ("Lex Fridman", "https://lexfridman.com/feed/podcast/", "Podcasts"),
    ("Practical AI", "https://changelog.com/practicalai/feed", "Podcasts"),
    ("TWIML AI", "https://twimlai.com/feed/", "Podcasts"),
]

VERIFIED_CATALOG_FEED_COUNT: int = len(RSS_VERIFIED_FEEDS)


def catalog_urls() -> list[str]:
    return [row[1] for row in RSS_VERIFIED_FEEDS]


def catalog_lookup_by_url() -> dict[str, tuple[str, str]]:
    """Normalize URL key → (display_name, section)."""
    out: dict[str, tuple[str, str]] = {}
    for name, url, section in RSS_VERIFIED_FEEDS:
        key = url.strip().rstrip("/").lower()
        out[key] = (name, section)
    return out
