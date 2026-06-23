# AI/ML Daily Digest - Test Suite

**All data collection and API testing scripts are organized here.**

---

## 📁 Folder Structure

```
tests/
├── README.md                          # This file
├── run_all_tests.py                   # ⭐ MAIN TEST RUNNER (use this!)
├── outputs/                           
│   ├── collected_api_data.json        # 🎯 ALL API data aggregated here
│   ├── test_results.json              # Test execution metadata
│   └── *.txt                          # Test logs
├── docs/                              # Documentation archive
│   ├── ACCOUNTS_SETUP.md
│   ├── TESTING_GUIDE.md
│   └── ...
│
├── test_*.py                          # Individual API test scripts
│   ├── test_arxiv.py                  # ArXiv papers (cs.AI, cs.LG, etc.)
│   ├── test_reddit.py                 # Reddit posts (5 subreddits)
│   ├── test_hackernews.py             # Hacker News stories
│   ├── test_kaggle.py                 # Kaggle datasets
│   ├── test_huggingface.py            # HuggingFace models + datasets
│   ├── test_semantic_scholar.py       # Semantic Scholar papers
│   ├── test_stackoverflow.py          # Stack Overflow questions
│   ├── test_rss_feeds.py              # RSS feeds (61 feeds)
│   ├── test_github.py                 # GitHub trending + releases
│   ├── test_groq_api.py               # Groq API status
│   ├── test_gemini_api.py             # Gemini API (optional)
│   ├── test_supabase.py               # Supabase integration
│   └── test_papers_with_code.py       # Papers With Code
│
└── run_*.py                           # Alternative test runners
    ├── run_comprehensive_tests.py          # All tests including experimental
    ├── run_comprehensive_tests_with_data.py # Older version (use run_all_tests.py)
    └── run_tests_simple.py                  # Simplified runner
```

---

## 🚀 Quick Start

### Run All Tests (Recommended)

```bash
conda activate ai
python tests/run_all_tests.py
```

**Output:**
- **Console:** Test status, summaries
- **File:** `tests/outputs/collected_api_data.json` (all API data)
- **File:** `tests/outputs/test_results.json` (execution metadata)

---

## 📊 Individual Test Scripts

Each test script can be run independently:

```bash
# Test individual APIs
python tests/test_arxiv.py              # ArXiv papers
python tests/test_reddit.py             # Reddit posts
python tests/test_github.py             # GitHub repos + releases
python tests/test_rss_feeds.py          # All RSS feeds (61 feeds)
python tests/test_kaggle.py             # Kaggle datasets
python tests/test_huggingface.py        # HuggingFace models + datasets
```

Each script outputs JSON to console in this format:
```json
{
  "source": "api_name",
  "collected_at": "2026-02-25T...",
  "total_items": 100,
  "items": [...]
}
```

---

## 🎯 Main Output File

**`tests/outputs/collected_api_data.json`** contains ALL collected data:

```json
{
  "collection_date": "2026-02-25T...",
  "apis": {
    "groq_api": { "status": "working", ... },
    "arxiv": { "total_papers": 239, "papers": [...] },
    "reddit": { "total_posts": 125, "posts": [...] },
    "hacker_news": { "total_stories": 60, "stories": [...] },
    "huggingface": { "total_models": 20, "total_datasets": 20, "data": {...} },
    "semantic_scholar": { "total_papers": 15, "papers": [...] },
    "stack_overflow": { "total_questions": 0, "questions": [] },
    "rss_feeds": { "total_entries": 89, "entries": [...] },
    "kaggle": { "total_datasets": 40, "datasets": [...] },
    "github": { "trending_repos": [...], "framework_releases": [...] }
  }
}
```

**Daily collection:** ~645 items across all sources

---

## 📝 Test Coverage

### Working APIs (10/10)

| API | Status | Items/Day | Description |
|-----|--------|-----------|-------------|
| **ArXiv** | ✅ | ~239 papers | 5 categories (cs.AI, cs.LG, cs.CL, cs.CV, stat.ML) |
| **Reddit** | ✅ | ~125 posts | 5 subreddits (MachineLearning, LocalLLaMA, etc.) |
| **Hacker News** | ✅ | ~60 stories | 3 query categories (AI/LLM, ML, GPT/Claude) |
| **HuggingFace** | ✅ | ~40 items | Trending models + datasets (20 each) |
| **Semantic Scholar** | ✅ | ~15 papers | 4 queries (LLM, ML, DL, NLP) |
| **Stack Overflow** | ✅ | ~0 questions | 5 tags (ml, ai, nlp, llm, dl) |
| **RSS Feeds** | ✅ | ~89 entries | 61 feeds (company blogs, frameworks, podcasts) |
| **Kaggle** | ✅ | ~40 datasets | 4 tags (llm, ml, dl, nlp) |
| **GitHub** | ✅ | ~47 items | Trending repos + 17 framework releases |
| **Groq API** | ✅ | API status | Groq LLM API health check |

**Total:** ~645 items/day

---

## 🔧 Configuration

### Environment Variables (.env)

Required for full functionality:
```bash
# Reddit API
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=your_user_agent

# Kaggle API  
KAGGLE_USERNAME=your_username
KAGGLE_KEY=your_key

# Groq API
GROQ_API_KEY=your_groq_key

# GitHub API (optional, increases rate limits)
GITHUB_TOKEN=your_github_token

# Semantic Scholar (optional)
S2_API_KEY=your_key

# Gemini API (optional)
GEMINI_API_KEY=your_key

# Supabase (optional, for storage)
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
```

---

## 📦 Dependencies

All dependencies in `requirements.txt`:

```bash
pip install -r requirements.txt
```

**Core libraries:**
- `arxiv` - ArXiv API
- `praw` - Reddit API
- `requests` - HTTP requests
- `kaggle` - Kaggle API
- `huggingface_hub` - HuggingFace API
- `feedparser` - RSS feed parsing
- `semanticscholar` - Semantic Scholar API
- `groq` - Groq API
- `httpx` - Async HTTP (GitHub)

---

## 🧪 Test Results

After running `run_all_tests.py`:

```
==================================================
📊 FINAL SUMMARY
==================================================
✅ Passed: 10/10 tests
❌ Failed: 0/10 tests
⏱️  Total time: ~45 seconds

💾 Data saved to: tests/outputs/collected_api_data.json
   Total items: ~645

📁 Execution log: tests/outputs/test_results.json
```

---

## 🐛 Troubleshooting

### Common Issues

**1. Module not found errors**
```bash
# Solution: Install dependencies
pip install -r requirements.txt
```

**2. API authentication errors**
```bash
# Solution: Check .env file has correct credentials
cp .env.example .env
# Edit .env with your API keys
```

**3. Empty data collection**
```bash
# Solution: Check API service status + credentials
python tests/test_<api_name>.py  # Test individually
```

**4. Rate limiting**
```bash
# Solution: Add delays between requests or use API keys
# Most APIs: Already implemented (Kaggle, GitHub, Semantic Scholar)
```

---

## 📚 Documentation

Additional documentation in `tests/docs/`:
- **ACCOUNTS_SETUP.md** - How to get API credentials
- **TESTING_GUIDE.md** - Detailed testing procedures
- **TESTING_RESULTS.md** - Historical test results

---

## 🎯 Next Steps

### For Daily Digest Production:

1. **Schedule:** Run `run_all_tests.py` daily via cron/GitHub Actions
2. **Process:** Parse `collected_api_data.json` with Gemini
3. **Publish:** Send digest to Telegram/Discord/Email
4. **Deploy:** Follow `AI_ML_Digest_MCP_Blueprint.md` for MCP servers

See main [README.md](../README.md) for full project overview.
