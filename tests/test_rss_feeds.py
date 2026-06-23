"""
VERIFIED RSS FEEDS FOR AI/ML DAILY DIGEST
Last verified: February 2026
All feeds tested and validated
"""

def test_rss_feeds():
    """Test parsing multiple RSS/Atom feeds"""
    
    try:
        import feedparser
    except ImportError:
        print("[ERROR] feedparser not installed")
        print("Install with: pip install feedparser")
        return
    
    print("=" * 80)
    print("COMPREHENSIVE RSS FEED TESTING - AI/ML DAILY DIGEST")
    print("=" * 80)
    
    feeds_to_test = [
        # ═══════════════════════════════════════════════════════════════
        # SECTION A — COMPANY & LAB BLOGS
        # ═══════════════════════════════════════════════════════════════
        ("HuggingFace Blog", "https://huggingface.co/blog/feed.xml"),
        ("Anthropic News", "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml"),
        ("Google Research Blog", "https://research.google/blog/rss"),
        ("DeepMind Blog", "https://www.deepmind.com/blog/rss.xml"),
        ("AWS ML Blog", "https://aws.amazon.com/blogs/machine-learning/feed/"),
        ("NVIDIA Developer", "https://developer.nvidia.com/blog/feed/"),
        ("Weights & Biases", "https://wandb.ai/fully-connected/rss.xml"),
        ("OpenAI News", "https://openai.com/news/rss.xml"),
        ("Meta AI FAIR", "https://research.facebook.com/feed/"),
        ("Microsoft Research", "https://www.microsoft.com/en-us/research/blog/feed/"),
        ("Azure AI Blog", "https://azure.microsoft.com/en-us/blog/tag/ai/feed/"),
        ("Google Cloud AI Blog", "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/"),
        ("Apple ML Research", "https://machinelearning.apple.com/rss.xml"),
        
        # ═══════════════════════════════════════════════════════════════
        # SECTION B — NEWSLETTERS & INDEPENDENT BLOGS
        # ═══════════════════════════════════════════════════════════════
        ("Import AI", "https://importai.substack.com/feed"),
        ("BAIR Blog", "https://bair.berkeley.edu/blog/feed.xml"),
        ("KDnuggets", "https://www.kdnuggets.com/feed"),
        ("Towards Data Science", "https://medium.com/feed/towards-data-science"),
        ("Analytics Vidhya", "https://www.analyticsvidhya.com/feed/"),
        ("MarkTechPost", "https://www.marktechpost.com/feed/"),
        ("The Gradient", "https://thegradient.pub/rss/"),
        ("The Algorithmic Bridge", "https://thealgorithmicbridge.substack.com/feed"),
        ("The Decoder", "https://the-decoder.com/feed/"),
        ("Sebastian Raschka", "https://magazine.sebastianraschka.com/feed"),
        ("Chip Huyen Blog", "https://huyenchip.com/feed.xml"),
        
        # ═══════════════════════════════════════════════════════════════
        # SECTION C — AGENTIC FRAMEWORK BLOGS
        # ═══════════════════════════════════════════════════════════════
        ("LangChain Blog", "https://blog.langchain.com/rss"),
        ("LlamaIndex Blog", "https://medium.com/feed/llamaindex-blog"),
        
        # ═══════════════════════════════════════════════════════════════
        # SECTION D — AGENTIC FRAMEWORK GITHUB RELEASES
        # ═══════════════════════════════════════════════════════════════
        ("LangChain Releases", "https://github.com/langchain-ai/langchain/releases.atom"),
        ("LangGraph Releases", "https://github.com/langchain-ai/langgraph/releases.atom"),
        ("LlamaIndex Releases", "https://github.com/run-llama/llama_index/releases.atom"),
        ("CrewAI Releases", "https://github.com/crewAIInc/crewAI/releases.atom"),
        ("AutoGen Releases", "https://github.com/microsoft/autogen/releases.atom"),
        ("Haystack Releases", "https://github.com/deepset-ai/haystack/releases.atom"),
        ("Flowise Releases", "https://github.com/FlowiseAI/Flowise/releases.atom"),
        ("AutoGPT Releases", "https://github.com/Significant-Gravitas/AutoGPT/releases.atom"),
        ("DSPy Releases", "https://github.com/stanfordnlp/dspy/releases.atom"),
        ("Pydantic AI Releases", "https://github.com/pydantic/pydantic-ai/releases.atom"),
        ("Semantic Kernel Releases", "https://github.com/microsoft/semantic-kernel/releases.atom"),
        ("phidata Releases", "https://github.com/phidatahq/phidata/releases.atom"),
        ("smolagents Releases", "https://github.com/huggingface/smolagents/releases.atom"),
        ("OpenHands Releases", "https://github.com/All-Hands-AI/OpenHands/releases.atom"),
        ("MetaGPT Releases", "https://github.com/geekan/MetaGPT/releases.atom"),
        ("GPT Engineer Releases", "https://github.com/gpt-engineer-org/gpt-engineer/releases.atom"),
        ("Composio Releases", "https://github.com/ComposioHQ/composio/releases.atom"),
        ("BrowserUse Releases", "https://github.com/browser-use/browser-use/releases.atom"),
        
        # ═══════════════════════════════════════════════════════════════
        # SECTION E — BACKEND & INFRA FRAMEWORK RELEASES
        # ═══════════════════════════════════════════════════════════════
        ("FastAPI Releases", "https://github.com/fastapi/fastapi/releases.atom"),
        ("Flask Releases", "https://github.com/pallets/flask/releases.atom"),
        ("Django Releases", "https://github.com/django/django/releases.atom"),
        ("Streamlit Releases", "https://github.com/streamlit/streamlit/releases.atom"),
        ("Gradio Releases", "https://github.com/gradio-app/gradio/releases.atom"),
        ("Ray Releases", "https://github.com/ray-project/ray/releases.atom"),
        ("MLflow Releases", "https://github.com/mlflow/mlflow/releases.atom"),
        ("BentoML Releases", "https://github.com/bentoml/BentoML/releases.atom"),
        ("Lightning Releases", "https://github.com/Lightning-AI/pytorch-lightning/releases.atom"),
        ("LangServe Releases", "https://github.com/langchain-ai/langserve/releases.atom"),
        ("Chainlit Releases", "https://github.com/Chainlit/chainlit/releases.atom"),
        ("Litestar Releases", "https://github.com/litestar-org/litestar/releases.atom"),
        ("Starlette Releases", "https://github.com/encode/starlette/releases.atom"),
        ("Uvicorn Releases", "https://github.com/encode/uvicorn/releases.atom"),
        ("Celery Releases", "https://github.com/celery/celery/releases.atom"),
        ("Airflow Releases", "https://github.com/apache/airflow/releases.atom"),
        ("Prefect Releases", "https://github.com/PrefectHQ/prefect/releases.atom"),
        ("Temporal Releases", "https://github.com/temporalio/temporal/releases.atom"),
        
        # ═══════════════════════════════════════════════════════════════
        # SECTION F — ML/AI CORE FRAMEWORK RELEASES
        # ═══════════════════════════════════════════════════════════════
        ("PyTorch Releases", "https://github.com/pytorch/pytorch/releases.atom"),
        ("Transformers Releases", "https://github.com/huggingface/transformers/releases.atom"),
        ("Diffusers Releases", "https://github.com/huggingface/diffusers/releases.atom"),
        ("vLLM Releases", "https://github.com/vllm-project/vllm/releases.atom"),
        ("Ollama Releases", "https://github.com/ollama/ollama/releases.atom"),
        ("Unsloth Releases", "https://github.com/unslothai/unsloth/releases.atom"),
        ("Instructor Releases", "https://github.com/instructor-ai/instructor/releases.atom"),
        ("Qdrant Releases", "https://github.com/qdrant/qdrant/releases.atom"),
        ("Chroma Releases", "https://github.com/chroma-core/chroma/releases.atom"),
        ("Weaviate Releases", "https://github.com/weaviate/weaviate/releases.atom"),
        ("TensorFlow Releases", "https://github.com/tensorflow/tensorflow/releases.atom"),
        ("JAX Releases", "https://github.com/jax-ml/jax/releases.atom"),
        ("ONNX Runtime Releases", "https://github.com/microsoft/onnxruntime/releases.atom"),
        ("llama.cpp Releases", "https://github.com/ggerganov/llama.cpp/releases.atom"),
        ("LocalAI Releases", "https://github.com/mudler/LocalAI/releases.atom"),
        ("LiteLLM Releases", "https://github.com/BerriAI/litellm/releases.atom"),
        ("Milvus Releases", "https://github.com/milvus-io/milvus/releases.atom"),
        ("FAISS Releases", "https://github.com/facebookresearch/faiss/releases.atom"),
        
        # ═══════════════════════════════════════════════════════════════
        # SECTION G — GITHUB DISCUSSIONS (Top frameworks only)
        # ═══════════════════════════════════════════════════════════════
        ("LangChain Discussions", "https://github.com/langchain-ai/langchain/discussions.atom"),
        ("LlamaIndex Discussions", "https://github.com/run-llama/llama_index/discussions.atom"),
        ("AutoGen Discussions", "https://github.com/microsoft/autogen/discussions.atom"),
        ("FastAPI Discussions", "https://github.com/fastapi/fastapi/discussions.atom"),
        
        # ═══════════════════════════════════════════════════════════════
        # SECTION H — INFRA & MLOPS COMPANY BLOGS
        # ═══════════════════════════════════════════════════════════════
        ("Streamlit Blog", "https://blog.streamlit.io/feed/"),
        ("Replicate Blog", "https://replicate.com/blog/rss"),
        
        # ═══════════════════════════════════════════════════════════════
        # SECTION L — PODCASTS (Essential only)
        # ═══════════════════════════════════════════════════════════════
        ("Lex Fridman", "https://lexfridman.com/feed/podcast/"),
        ("Practical AI", "https://changelog.com/practicalai/feed"),
        ("TWIML AI", "https://twimlai.com/feed/"),
    ]
    
    working_feeds = []
    failed_feeds = []
    section_results = {}
    current_section = "Unknown"

    # Pre-fetch all feeds concurrently so sequential printing doesn't wait on HTTP
    from concurrent.futures import ThreadPoolExecutor

    def _fetch(item):
        n, u = item
        try:
            return n, feedparser.parse(u), None
        except Exception as ex:
            return n, None, str(ex)

    print(f"Fetching {len(feeds_to_test)} feeds concurrently...")
    with ThreadPoolExecutor(max_workers=20) as pool:
        prefetched = {n: (f, e) for n, f, e in pool.map(_fetch, feeds_to_test)}

    for name, url in feeds_to_test:
        # Detect section changes
        if "Company" in name or name == "HuggingFace Blog":
            current_section = "A - Company Blogs"
        elif name == "Import AI":
            current_section = "B - Newsletters"
        elif name == "LangChain Blog":
            current_section = "C - Framework Blogs"
        elif "Releases" in name and "LangChain" in name:
            current_section = "D - Agentic Releases"
        elif "Releases" in name and "FastAPI" in name:
            current_section = "E - Backend Releases"
        elif "Releases" in name and "PyTorch" in name:
            current_section = "F - ML Core Releases"
        elif "Discussions" in name:
            current_section = "G - Discussions"
        elif name == "Streamlit Blog":
            current_section = "H - MLOps Blogs"
        elif name == "Lex Fridman":
            current_section = "L - Podcasts"
        
        if current_section not in section_results:
            section_results[current_section] = {"working": 0, "failed": 0}
        
        print(f"\n{'-'*80}")
        print(f"Testing: {name}")
        print(f"URL: {url}")
        print(f"{'-'*80}")
        
        try:
            feed, fetch_err = prefetched.get(name, (None, "not fetched"))
            if fetch_err:
                raise Exception(fetch_err)
            if not feed:
                raise Exception("No feed data returned")

            if feed.bozo and feed.bozo_exception:
                print(f"[WARNING] Parse warning: {feed.bozo_exception}")
            
            if not feed.entries:
                print(f"[ERROR] No entries found")
                failed_feeds.append((name, "No entries", current_section))
                section_results[current_section]["failed"] += 1
                continue
            
            print(f"[OK] Found {len(feed.entries)} entries")
            working_feeds.append((name, len(feed.entries), current_section))
            section_results[current_section]["working"] += 1
            
            # Show latest entry
            if len(feed.entries) > 0:
                entry = feed.entries[0]
                print(f"\nLatest Entry:")
                # pyrefly: ignore [unsupported-operation]
                print(f"   Title: {entry.get('title', 'N/A')[:80]}")
                print(f"   Published: {entry.get('published', 'N/A')}")
                # pyrefly: ignore [unsupported-operation]
                print(f"   Link: {entry.get('link', 'N/A')[:80]}")
                
        except Exception as e:
            print(f"[ERROR] Error: {e}")
            failed_feeds.append((name, str(e), current_section))
            section_results[current_section]["failed"] += 1
    
    # Enhanced Summary
    print("\n" + "=" * 80)
    print("RSS FEED TEST SUMMARY")
    print("=" * 80)
    print(f"[OK] Working feeds: {len(working_feeds)}/{len(feeds_to_test)}")
    print(f"[ERROR] Failed feeds: {len(failed_feeds)}/{len(feeds_to_test)}")
    print(f"Success rate: {len(working_feeds)/len(feeds_to_test)*100:.1f}%")
    
    # Section-by-section breakdown
    print("\n" + "=" * 80)
    print("SECTION-BY-SECTION BREAKDOWN")
    print("=" * 80)
    for section in sorted(section_results.keys()):
        working = section_results[section]["working"]
        failed = section_results[section]["failed"]
        total = working + failed
        print(f"\n{section}:")
        print(f"   [OK] Working: {working}/{total}")
        if failed > 0:
            print(f"   [ERROR] Failed: {failed}/{total}")
    
    if working_feeds:
        print(f"\n" + "=" * 80)
        print(f"WORKING FEEDS ({len(working_feeds)}):")
        print("=" * 80)
        for name, count, section in working_feeds:
            print(f"   [OK] {name:<35} ({count} entries) [{section}]")
    
    if failed_feeds:
        print(f"\n" + "=" * 80)
        print(f"FAILED FEEDS ({len(failed_feeds)}):")
        print("=" * 80)
        for name, reason, section in failed_feeds:
            print(f"   [ERROR] {name:<35} | {reason[:40]} | [{section}]")
    
    return len(working_feeds), len(failed_feeds)


if __name__ == "__main__":
    import json
    from datetime import datetime
    
    print("\nRSS FEED TESTING SUITE - COMPREHENSIVE\n")
    test_rss_feeds()
    print("\n[OK] Testing Complete!")
    
    # Collect actual feed entries for JSON output
    def collect_rss_data():
        import feedparser
        import re
        import time
        import calendar
        import httpx
        # pyrefly: ignore [missing-import]
        from trafilatura import extract as traf_extract
        
        three_days_ago = time.time() - 3 * 24 * 3600  # Unix timestamp
        MIN_WORDS_FOR_FULLTEXT = 80  # If RSS content < this, fetch full article
        MAX_CONTENT_CHARS = 5000    # Max content length per entry
        FETCH_TIMEOUT = 12          # seconds per URL for full-text fetch
        UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"
        
        # Full comprehensive feed list matching test function
        feeds_to_collect = [
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
            ("Composio Releases", "https://github.com/ComposioHQ/composio/releases.atom", "Agentic Releases"),
            ("BrowserUse Releases", "https://github.com/browser-use/browser-use/releases.atom", "Agentic Releases"),
            
            # SECTION E — Backend & Infra Framework Releases
            ("FastAPI Releases", "https://github.com/fastapi/fastapi/releases.atom", "Backend Releases"),
            ("Flask Releases", "https://github.com/pallets/flask/releases.atom", "Backend Releases"),
            ("Django Releases", "https://github.com/django/django/releases.atom", "Backend Releases"),
            ("Streamlit Releases", "https://github.com/streamlit/streamlit/releases.atom", "Backend Releases"),
            ("Gradio Releases", "https://github.com/gradio-app/gradio/releases.atom", "Backend Releases"),
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
            ("PyTorch Releases", "https://github.com/pytorch/pytorch/releases.atom", "ML Core Releases"),
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
            
            # SECTION G — GitHub Discussions
            ("LangChain Discussions", "https://github.com/langchain-ai/langchain/discussions.atom", "Discussions"),
            ("LlamaIndex Discussions", "https://github.com/run-llama/llama_index/discussions.atom", "Discussions"),
            ("AutoGen Discussions", "https://github.com/microsoft/autogen/discussions.atom", "Discussions"),
            ("FastAPI Discussions", "https://github.com/fastapi/fastapi/discussions.atom", "Discussions"),
            
            # SECTION H — MLOps Blogs
            ("Streamlit Blog", "https://blog.streamlit.io/feed/", "MLOps Blogs"),
            ("Replicate Blog", "https://replicate.com/blog/rss", "MLOps Blogs"),
            
            # SECTION L — Podcasts
            ("Lex Fridman", "https://lexfridman.com/feed/podcast/", "Podcasts"),
            ("Practical AI", "https://changelog.com/practicalai/feed", "Podcasts"),
            ("TWIML AI", "https://twimlai.com/feed/", "Podcasts"),
        ]
        
        all_entries = []
        fulltext_hits = 0
        fulltext_misses = 0

        def _fetch_fulltext(url: str) -> str:
            """Fetch full article text from URL using trafilatura + httpx."""
            if not url or "github.com" in url:
                return ""  # Skip GitHub release pages (already have content)
            try:
                r = httpx.get(url, follow_redirects=True, timeout=FETCH_TIMEOUT,
                              headers={"User-Agent": UA})
                if r.status_code == 200 and len(r.text) > 500:
                    text = traf_extract(r.text, favor_recall=True,
                                        include_comments=False, include_tables=False)
                    return text or ""
            except Exception:
                pass
            return ""

        # Fetch all feeds concurrently
        from concurrent.futures import ThreadPoolExecutor

        def _fetch_one(item):
            n, u, s = item
            try:
                return n, s, feedparser.parse(u)
            except Exception:
                return n, s, None

        with ThreadPoolExecutor(max_workers=20) as pool:
            feed_map = {n: (s, f) for n, s, f in pool.map(_fetch_one, feeds_to_collect)}

        for name, url, section in feeds_to_collect:
            try:
                sec, feed = feed_map.get(name, (section, None))
                if not feed:
                    continue

                if feed.entries:
                    count = 0
                    for entry in feed.entries[:15]:  # Check up to 15, collect max 5
                        # Date filter using published_parsed (struct_time)
                        pub_parsed = entry.get('published_parsed') or entry.get('updated_parsed')
                        if pub_parsed:
                            # pyrefly: ignore [bad-argument-type]
                            entry_epoch = calendar.timegm(pub_parsed)
                            if entry_epoch < three_days_ago:
                                continue  # Skip old entries
                        
                        # Try full content first (content:encoded), fall back to summary
                        raw_content = ''
                        if hasattr(entry, 'content') and entry.get('content'):
                            for c_item in entry.content:
                                val = c_item.get('value', '')
                                if val and len(val) > len(raw_content):
                                    raw_content = val
                        if not raw_content:
                            raw_content = entry.get('summary', entry.get('description', ''))
                        if raw_content:
                            # pyrefly: ignore [no-matching-overload]
                            clean_content = re.sub('<[^<]+?>', '', raw_content)
                            clean_content = re.sub(r'\s+', ' ', clean_content).strip()
                        else:
                            clean_content = ''
                        
                        # If RSS content is too short, fetch full article via trafilatura
                        word_count = len(clean_content.split())
                        entry_link = entry.get('link', '')
                        if word_count < MIN_WORDS_FOR_FULLTEXT and entry_link:
                            # pyrefly: ignore [bad-argument-type]
                            fulltext = _fetch_fulltext(entry_link)
                            if fulltext and len(fulltext.split()) > word_count:
                                clean_content = fulltext
                                fulltext_hits += 1
                            else:
                                fulltext_misses += 1
                        
                        clean_summary = clean_content[:MAX_CONTENT_CHARS]
                        
                        all_entries.append({
                            "feed": name,
                            "section": sec,
                            "title": entry.get('title', ''),
                            "link": entry.get('link', ''),
                            "published": entry.get('published', entry.get('updated', '')),
                            "summary": clean_summary
                        })
                        
                        count += 1
                        if count >= 8:  # Max 8 entries per feed
                            break
            except Exception:
                pass
        
        print(f"\n[Content Enhancement] Full-text fetched: {fulltext_hits} | Skipped/failed: {fulltext_misses}")
        return all_entries
    
    try:
        entries_data = collect_rss_data()
        
        # Create output data structure
        output_data = {
            "source": "rss_feeds",
            "collected_at": datetime.now().isoformat(),
            "cutoff_days": 3,
            "total_entries": len(entries_data),
            "total_feeds": len(set([e["feed"] for e in entries_data])) if entries_data else 0,
            "entries": entries_data
        }
        
        # Output for aggregation by run_all_tests.py
        print("\n=== DATA OUTPUT ===")
        print(json.dumps(output_data, indent=2))
    except Exception as e:
        print("\n=== DATA OUTPUT ===")
        print(json.dumps({"source": "rss_feeds", "error": str(e), "entries": []}, indent=2))
