<div align="center">

# ⚡ AI Daily Digest

**An autonomous AI/ML news pipeline that fetches, filters, enriches, and delivers a curated daily brief — straight to Discord, Telegram, and Email.**

[![CI](https://github.com/narlapavan26/ai-daily-digest/actions/workflows/ci.yml/badge.svg)](https://github.com/narlapavan26/ai-daily-digest/actions/workflows/ci.yml)
[![Daily Digest](https://github.com/narlapavan26/ai-daily-digest/actions/workflows/daily-digest.yml/badge.svg)](https://github.com/narlapavan26/ai-daily-digest/actions/workflows/daily-digest.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![LangGraph](https://img.shields.io/badge/built_with-LangGraph-6f42c1)](https://github.com/langchain-ai/langgraph)

</div>

---

## 🤔 What Is This?

The AI landscape is moving at breakneck speed. Day to day, AI news is emerging in vast, overwhelming numbers across scattered various platforms. Picking out the highest-signal updates before they become yesterday's news is incredibly hard and time-consuming. 

**AI Daily Digest** is your autonomous research assistant. It aggressively sweeps the internet for new AI developments, ruthlessly throws away the noise (like minor patch releases or clickbait), and leverages a rotating swarm of LLMs to analyze, score, and extract deep engineering insights from what remains. 

The result? A highly curated, zero-fluff intelligence briefing delivered directly to you—giving you a competitive edge by surfacing only what a senior ML engineer or researcher actually needs to know today.

### 🌟 What it produces

The pipeline outputs a beautifully formatted, structured Markdown newsletter designed for rapid consumption. It includes:

- 🏆 **The Top Story** — The absolute highest-impact development of the day, summarized with its "why it matters" and an actionable takeaway.
- ⚙️ **Framework & Infrastructure Updates** — Critical updates for the tools you use in production (vLLM, LangGraph, vector databases, inference engines).
- 🧠 **Model Drops** — The latest weights, architectures, and multimodal foundation models you need to test.
- 🔬 **Research Worth Noting** — Cutting-edge papers filtered for real-world engineering value and actual benchmarks, not just theory.
- 🛠️ **New Developer Tools** — SDKs, libraries, and utilities that speed up your AI workflow.
- 🌐 **Community Buzz** — The most vibrant discussions and trending repositories bubbling up from HackerNews and GitHub.
- ⚡ **Quick Links & Stats** — A rapid-fire table of honorable mentions and a transparent breakdown of the day's fetch vs. drop rates.

---

## 🏗️ Architecture

```
python -m digest_runner.main
         │
         ├─ _load_env_into_os_environ()        reads .env → os.environ
         ├─ ProviderPool.reset()               clears 429 cooldowns
         └─ build_graph().invoke(initial_state)
                    │
              ┌─────▼─────┐
              │ init_node  │  sets run_date, run_id
              └─────┬─────┘
                    │ route_to_sources() fan-out via Send()
         ┌──────────┼──────────┬──────────┬──────────┬──────────┐
         ▼          ▼          ▼          ▼          ▼          ▼
      arxiv    hackernews   github   huggingface stackoverflow rss_feeds
         │          │          │          │          │          │
         └──────────┴──────────┴──── all parallel ──┴──────────┘
                              │
                    Each branch runs BaseSubgraph.run():
                      1. fetch_from_mcp()    → MCP server on Prefect Horizon
                      2. normalize()         → source-specific field mapping
                      3. is_junk_release()   → cheap regex drop
                      4. fast_fail()         → staleness / length drop
                      5. enrich_normalized_items():
                           a. run_relevance_batch()  → LLM relevance scoring
                           b. run_insight_batch()    → LLM insight extraction
                              (via ProviderPool: OLLAMA→GITHUB→GROQ→GEMINI→
                               CEREBRAS→OPENROUTER→SAMBANOVA)
                              │
                    SubgraphOutput appended to state["subgraph_outputs"]
                    via operator.add reducer (thread-safe parallel writes)
                              │
                    ┌─────────▼─────────┐
                    │  merger_node       │  3-pass dedup (ID → URL → fuzzy title)
                    └─────────┬─────────┘
                              │ merged_items: List[EnrichedItem]
                    ┌─────────▼─────────┐
                    │  final_llm_node    │  top story pick + narrative LLM writing
                    └─────────┬─────────┘
                              │ final_digest: FinalDigestSchema
                    ┌─────────▼─────────┐
                    │  render_node       │  → outputs/digest_YYYY-MM-DD.md
                    └─────────┬─────────┘
                              │ output_path
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          Discord          Telegram         Email
       (webhook +         (sendDocument    (SMTP +
        .md attach)        Bot API)         HTML)
```

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/narlapavan26/ai-daily-digest.git
cd ai-daily-digest
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r digest_runner/requirements.txt
```

### 4. Copy and fill in the environment file

```bash
cp .env.example .env
# Edit .env with your API keys (see table below)
```

### 5. Start the MCP data server (local mode)

```bash
cd mcp
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 6. Run the digest pipeline

```bash
# From project root (separate terminal)
python -m digest_runner.main

# Run specific sources only
python -m digest_runner.main --sources arxiv hackernews github

# Save output to custom directory
python -m digest_runner.main --output-dir /tmp/digests
```

---

## 🔑 Environment Variables

Copy `.env.example` to `.env` and fill in the values you want to use. Every key is optional — the system degrades gracefully when keys are absent.

### AI Provider Keys (LLM enrichment)

| Variable | Provider | Model Used | Free Tier |
|----------|----------|------------|-----------|
| `GROQ_API_KEY` | [Groq](https://console.groq.com) | `llama-3.3-70b-versatile` | 30 RPM |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com) | `gemini-2.5-flash-lite` | 15 RPM |
| `CEREBRAS_API_KEY` | [Cerebras](https://cloud.cerebras.ai) | `gpt-oss-120b` | 30 RPM |
| `OPENROUTER_API_KEY` | [OpenRouter](https://openrouter.ai) | `nvidia/nemotron-3-super-120b` | 20 RPM |
| `SAMBANOVA_API_KEY` | [SambaNova](https://cloud.sambanova.ai) | `Meta-Llama-3.3-70B-Instruct` | 15 RPM |
| `OLLAMA_API_KEY` | [Ollama](https://ollama.com) | `gemma4:31b` | 20 RPM |
| `GH_MODELS_API_KEY` | [GitHub Models](https://github.com/marketplace/models) | `gpt-4o-mini` | 15 RPM |

> **Note:** In GitHub Actions secrets, use `GH_MODELS_API_KEY` (not `GITHUB_MODELS_API_KEY`) — GitHub forbids secrets starting with `GITHUB_`.

### MCP Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_BASE_URL` | `http://127.0.0.1:8000` | URL of the MCP data server |
| `MCP_BEARER_TOKEN` | — | Auth token for Prefect Horizon deployment |
| `MCP_REQUEST_TIMEOUT_SECONDS` | `60` | HTTP timeout for MCP calls |

### Publishing Channels

| Variable | Description |
|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Full Discord webhook URL |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your chat/channel ID |
| `SMTP_SERVER` | SMTP host (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (e.g. `587`) |
| `SMTP_USERNAME` | SMTP login email |
| `SMTP_PASSWORD` | SMTP password or app password |
| `EMAIL_FROM` | Sender address |
| `EMAIL_TO` | Comma-separated recipient addresses |

### Data Sources (Optional)

| Variable | Used for |
|----------|----------|
| `GH_PAT_TOKEN` | GitHub API token (raises rate limit from 60 → 5000 req/hr) |
| `REDDIT_CLIENT_ID` | Reddit API OAuth client ID |
| `REDDIT_CLIENT_SECRET` | Reddit API OAuth secret |
| `SUPABASE_URL` | Supabase project URL (for future persistence layer) |
| `SUPABASE_KEY` | Supabase anon/service key |

---

## 🔄 CI/CD Workflows

The project has 4 GitHub Actions workflows:

### 1. `ci.yml` — Continuous Integration

**Triggers:** Every push to every branch.

```
Jobs:
  lint         → ruff check digest_runner/ mcp/ tests/
  unit-tests   → pytest tests/unit/ (matrix: 6 test files in parallel)
  integration  → needs: unit-tests → pytest tests/integration/
  schema-check → needs: lint → python -c "from digest_runner.schemas import *"
```

This runs on every push. If it fails, the branch cannot be merged to `main`.

### 2. `branch-test.yml` — Branch Pipeline Test

**Triggers:** Push to `feature/**` or `test/**` branches.

```
Jobs:
  run-tests    → pytest tests/unit/ (full unit test suite)
  run-pipeline → needs: run-tests → python -m digest_runner.main (live run)
```

This is your safety net before merging. If the tests pass, the live pipeline runs against your real API keys on Horizon. If either step fails, you know the branch is broken before it ever touches `main`.

### 3. `daily-digest.yml` — Production Cron

**Triggers:** Every day at `30 1 * * *` UTC (7:00 AM IST). Also manual via `workflow_dispatch`.

```
Job: generate-digest
  1. Checkout code
  2. Install dependencies
  3. python -m digest_runner.main
  4. Upload outputs/ as artifact (retained 7 days)
```

All publisher secrets are injected as environment variables. The digest is generated and published automatically every morning.

### 4. `deploy-mcp.yml` — MCP Server Deployment

**Triggers:** Push to `main` affecting `mcp/**`. Also manual dispatch.

```
Job: deploy
  1. Install prefect + fastmcp
  2. prefect deploy mcp/main.py → Prefect Horizon
```

Deploys the data server to Prefect Horizon whenever the MCP code changes.

---

## 🔐 Adding GitHub Secrets

All secrets used by the GitHub Actions workflows must be added to your repository's secret store.

### Steps:

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with its exact name and value

### Required Secrets for the Workflows

| Secret Name | Required for | Notes |
|-------------|-------------|-------|
| `GROQ_API_KEY` | Daily digest | Primary LLM provider |
| `GEMINI_API_KEY` | Daily digest | Fallback LLM |
| `CEREBRAS_API_KEY` | Daily digest | Fallback LLM |
| `OPENROUTER_API_KEY` | Daily digest | Fallback LLM |
| `SAMBANOVA_API_KEY` | Daily digest | Fallback LLM |
| `OLLAMA_API_KEY` | Daily digest | Fallback LLM |
| `GH_MODELS_API_KEY` | Daily digest | ⚠️ Must NOT start with `GITHUB_` |
| `GH_PAT_TOKEN` | All workflows | GitHub API token (not `GITHUB_TOKEN`) |
| `MCP_BASE_URL` | Daily digest | Prefect Horizon URL |
| `MCP_BEARER_TOKEN` | Daily digest | Horizon auth token |
| `DISCORD_WEBHOOK_URL` | Publishing | Discord channel webhook |
| `TELEGRAM_BOT_TOKEN` | Publishing | From @BotFather |
| `TELEGRAM_CHAT_ID` | Publishing | Your chat/channel ID |
| `RESEND_API_KEY` | Publishing | Resend.com API key |
| `EMAIL_FROM` | Publishing | Sender email address |
| `EMAIL_TO` | Publishing | Recipient email address(es) |
| `SUPABASE_URL` | Future use | Supabase project URL |
| `SUPABASE_KEY` | Future use | Supabase anon key |

> **Important:** Do NOT add any secret whose name starts with `GITHUB_`. GitHub reserves that prefix for its own internal tokens. Use `GH_PAT_TOKEN` instead of `GITHUB_TOKEN`, and `GH_MODELS_API_KEY` instead of `GITHUB_MODELS_API_KEY`.

---

## 📡 Data Sources

The pipeline fetches from 6 active sources (Reddit disabled since May 2026 — they shut down unauthenticated API access):

| Source | What it fetches | Items/run | Key signal |
|--------|----------------|-----------|------------|
| **ArXiv** | CS/ML/AI papers from last 7 days | ~15 per query | Abstract, arxiv categories |
| **GitHub** | Trending repos + framework releases | ~30 trending + releases | Stars, release notes |
| **HackerNews** | Top AI/ML stories | ~20 | Points, comment count |
| **HuggingFace** | Trending models + blog posts | ~20 models | Trending score, downloads |
| **StackOverflow** | Hot ML/AI questions | ~15 | Score, answer count |
| **RSS Feeds** | 44 curated AI/ML blogs and news sites | ~50–100 | Feed title, summary |

HuggingFace fetches from the public API (`https://huggingface.co/api/models?sort=trending`) and RSS feed — **no token required**.

---

## 🧠 LLM Provider Pool

The system uses 7 LLM providers in a rotating pool with automatic 429 failover. All providers use the OpenAI-compatible API via the `instructor` library for structured output.

| Priority | Provider | Model | RPM Limit |
|----------|----------|-------|-----------|
| 1 | Ollama (Cloud) | `gemma4:31b` | 20 |
| 2 | GitHub Models | `gpt-4o-mini` | 15 |
| 3 | Groq | `llama-3.3-70b-versatile` | 28 |
| 4 | Gemini | `gemini-2.5-flash-lite` | 15 |
| 5 | Cerebras | `gpt-oss-120b` | 25 |
| 6 | OpenRouter | `nvidia/nemotron-3-super-120b` | 15 |
| 7 | SambaNova | `Meta-Llama-3.3-70B-Instruct` | 15 |

**Batching & Round-Robin Logic:**
Because the pipeline fetches hundreds of items simultaneously across 6 parallel branches, hitting LLM rate limits (HTTP 429) is a significant risk on free-tier APIs. The system handles this through strict batching and a thread-safe rotating pool:

1. **Batch-Wise Processing**: Instead of evaluating items one by one, the pipeline groups raw items into batches of 8 (`LLM_BATCH_SIZE`). This drastically reduces the number of HTTP calls to the LLM providers. The batch is sent as a single prompt for relevance scoring, and a second batch call is made for insight extraction on surviving items.
2. **Global Semaphore**: The `ProviderPool` maintains a global semaphore that restricts the entire pipeline to exactly **1 concurrent LLM call** at any given time, regardless of how many source branches are running in parallel.
3. **Round-Robin Rotation**: Every time a batch needs processing, the `ProviderPool` hands out the next available provider in the list (Ollama → GitHub → Groq → Gemini → Cerebras → OpenRouter → SambaNova), ensuring the load is evenly spread and rate limits are preserved.
4. **Cooldown Windows**: It enforces a minimum of 3.0 seconds between any two global LLM calls. If a provider throws an HTTP 429, it is instantly placed in a 65-second cooldown and skipped by the round-robin mechanism. If a provider returns a 404/401 (e.g., bad API key), it is put in a 10-minute cooldown.

---

## 📬 Publishing Channels

### Discord
Posts a short message plus the `.md` file as an attachment (bypasses the 2000-character limit). Users download the file or view it in any Markdown editor.

### Telegram
Sends the `.md` file as a `sendDocument` call with a caption. Works in groups and channels.

### Email
Converts the Markdown to HTML using the `markdown` library (with table and fenced code block extensions), wraps it in minimal CSS, and sends a `MIMEMultipart` email with both plain text and HTML parts via SMTP/STARTTLS.

---

## 🧪 Running Tests

```bash
# All unit tests
pytest tests/unit/ -v

# All tests including integration
pytest tests/ -v

# Specific file
pytest tests/unit/test_render_node.py -v

# With coverage
pytest tests/unit/ --cov=digest_runner --cov-report=term-missing
```

Unit tests are fast (<2 seconds for all 150 tests) and require no external services.

---

## 📁 Project Structure

```
ai-daily-digest/
├── digest_runner/              # Main pipeline (LangGraph)
│   ├── main.py                 # CLI entry point
│   ├── config/settings.py      # Pydantic settings (all env vars)
│   ├── graph/
│   │   ├── digest_graph.py     # StateGraph builder + node wiring
│   │   └── state.py            # DigestRunState TypedDict
│   ├── nodes/
│   │   ├── fetch_node.py       # run_source_pipeline() — parallel dispatcher
│   │   ├── merger_node.py      # merge_subgraph_outputs() — 3-pass dedup
│   │   ├── final_llm_node.py   # run_final_llm() — narrative writing
│   │   └── render_node.py      # render_digest() — Markdown file writer
│   ├── subgraphs/
│   │   ├── base.py             # BaseSubgraph + enrich_normalized_items()
│   │   ├── arxiv_subgraph.py
│   │   ├── hackernews_subgraph.py
│   │   ├── github_subgraph.py
│   │   ├── huggingface_subgraph.py
│   │   ├── stackoverflow_subgraph.py
│   │   └── rss_subgraph.py
│   ├── publishers/
│   │   ├── discord_publisher.py
│   │   ├── telegram_publisher.py
│   │   └── email_publisher.py
│   ├── schemas/digest_schemas.py   # All internal Pydantic schemas + enums
│   └── utils/
│       ├── mcp_client.py       # post_fetch() — REST/MCP-RPC auto-select
│       └── provider_pool.py    # ProviderPool — thread-safe LLM rotation
├── mcp/                        # Data server (FastAPI + FastMCP)
│   ├── main.py                 # App + router registration + FastMCP wrapper
│   ├── endpoints/              # One file per source (/fetch/<source>)
│   ├── schemas/common.py       # DigestItem, SourceResponse wire schemas
│   └── utils/                  # Text cleaning helpers
├── tests/
│   ├── unit/                   # 150 fast unit tests (no external services)
│   └── integration/            # Live tests against real APIs
├── docs/
│   └── EXECUTION_TRACE.md      # Complete runtime trace document
├── outputs/                    # Generated digests (gitignored)
├── state/                      # Debug state dumps (gitignored)
├── .github/workflows/
│   ├── ci.yml                  # Lint + tests on every push
│   ├── daily-digest.yml        # Production cron (7:00 AM IST)
│   ├── branch-test.yml         # Integration test on feature/* branches
│   └── deploy-mcp.yml          # Deploy MCP server to Prefect Horizon
├── Dockerfile.mcp              # Container for MCP server
├── .env.example                # Environment variable template
└── pyproject.toml              # Project metadata + tool config
```



## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-new-source`
3. Make changes; run `pytest tests/unit/` — must pass all 150 tests
4. Push to your fork: `git push origin feature/my-new-source`
5. Open a pull request; `branch-test.yml` will automatically run the full pipeline

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with [LangGraph](https://github.com/langchain-ai/langgraph) · Served by [Prefect Horizon](https://www.prefect.io/) · Powered by  LLMs

</div>
