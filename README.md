# 🧠 AI/ML Daily Digest - Production System
**Zero-Cost, Fully Automated, PC-Independent AI/ML News Aggregator**

---

## 🎯 **WHAT IS THIS?**

A production-grade system that:
- ☀️ Runs every morning at 7:00 AM IST (even when your PC is off)
- 📰 Collects news from **95%+ of the AI/ML internet** (papers, blogs, GitHub, Reddit, HN, HuggingFace)
- 🤖 Uses **Groq API** (with Gemini backup) to summarize, score, and tag every item
- 💾 Saves everything to **Supabase PostgreSQL**
- 📬 Delivers digest to **Email, Telegram, and Discord** simultaneously
- 🌐 Exposes a searchable **Next.js dashboard** on Vercel
- 💰 **Total monthly cost: $0**

---

## 📚 **DOCUMENTATION INDEX**

| Document | Purpose | Status |
|----------|---------|--------|
| **[TESTING_GUIDE.md](TESTING_GUIDE.md)** | Step-by-step API testing before building | 📘 Ready |
| **[PROJECT_ROADMAP.md](PROJECT_ROADMAP.md)** | 4-week build timeline with checkboxes | 🗺️ Ready |
| **[ACCOUNTS_SETUP.md](ACCOUNTS_SETUP.md)** | Setup guide for all required accounts | 🔑 Ready |
| **[TESTING_RESULTS.md](TESTING_RESULTS.md)** | Document your test results here | 📊 Empty (fill during testing) |
| **[AI_ML_Digest_MCP_Blueprint.md](AI_ML_Digest_MCP_Blueprint.md)** | Complete technical blueprint | 📖 Reference |
| **[vscode_copilot_prompt.md](vscode_copilot_prompt.md)** | Production build prompt (2500+ lines) | 🤖 Reference |

---

## 🚀 **QUICK START**

### **Phase 0: Setup & Testing (Week 0)**

1. **Set up accounts** (1 day):
   ```bash
   # Follow the guide:
   open ACCOUNTS_SETUP.md
   ```
   Required accounts:
   - ✅ Groq API (Primary AI)
   - ✅ Gemini API (Backup AI)
   - ✅ Supabase (Database)
   - ✅ GitHub (Code + CI/CD)
   - ✅ Prefect Horizon (MCP hosting)
   - ✅ Telegram Bot
   - ✅ Discord Webhook
   - ✅ Resend Email

2. **Test all APIs** (3-5 days):
   ```bash
   # Follow the testing guide:
   open TESTING_GUIDE.md
   
   # Run tests in tests/ folder
   python tests/test_groq_api.py
   python tests/test_gemini_api.py
   python tests/test_arxiv.py
   # ... etc
   ```

3. **Document results**:
   ```bash
   # Fill out your findings:
   open TESTING_RESULTS.md
   ```

4. **Ready to build?**
   ```bash
   # Follow the roadmap:
   open PROJECT_ROADMAP.md
   ```

---

## 🏗️ **SYSTEM ARCHITECTURE**

```
┌─────────────────────────────────────────────────────────────────┐
│          GITHUB ACTIONS (Cron Trigger - 7 AM IST)              │
│                   Runs on GitHub's cloud                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│ Research    │  │ Community   │  │ Utility      │
│ Server      │  │ Server      │  │ Server       │
│ (Horizon)   │  │ (Horizon)   │  │ (Horizon)    │
│             │  │             │  │              │
│ • ArXiv     │  │ • Reddit    │  │ • Crawl4ai   │
│ • PWC       │  │ • HN        │  │ • Search     │
│ • RSS Feeds │  │ • HF API    │  │ • Memory     │
│ • Kaggle    │  │ • Stack OF  │  │              │
└─────────────┘  └─────────────┘  └──────────────┘
        │                │                │
        └────────────────┼────────────────┘
                         ▼
            ┌────────────────────────┐
            │   GROQ / GEMINI API    │
            │  Summarize + Score +   │
            │  Tag + Flag Breaking   │
            └────────┬───────────────┘
                     ▼
            ┌────────────────────────┐
            │   SUPABASE (Database)  │
            │  • news_items          │
            │  • papers              │
            │  • github_repos        │
            │  • digest_runs         │
            └────────┬───────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    📧 Email    🤖 Telegram  🎮 Discord
                     │
                     ▼
             🌐 Next.js Dashboard
                  (Vercel)
```

---

## 📂 **PROJECT STRUCTURE**

This repository is the **planning and testing hub**. The actual code will be in 4 separate repositories:

```
ai-daily-digest/                      ← YOU ARE HERE (Planning & Testing)
├── TESTING_GUIDE.md                  ← Start here
├── PROJECT_ROADMAP.md                ← Then follow this
├── ACCOUNTS_SETUP.md                 ← Account setup guide
├── TESTING_RESULTS.md                ← Fill during testing
├── AI_ML_Digest_MCP_Blueprint.md     ← Technical reference
├── vscode_copilot_prompt.md          ← Implementation reference
├── tests/                            ← Test scripts
│   ├── test_groq_api.py
│   ├── test_gemini_api.py
│   ├── test_arxiv.py
│   ├── test_papers_with_code.py
│   ├── test_rss_feeds.py
│   ├── test_reddit.py
│   ├── test_hackernews.py
│   ├── test_telegram.py
│   ├── test_discord.py
│   ├── test_resend.py
│   └── test_supabase.py
└── .env.example                      ← Copy to .env and fill

ai-digest-research-server/            ← Build in Week 1
ai-digest-community-server/           ← Build in Week 2
ai-digest-utility-server/             ← Build in Week 2
ai-digest-pipeline/                   ← Build in Week 3-4
```

---

## 🛠️ **TECHNOLOGY STACK**

### **Backend (Python)**
- `fastmcp` - FastMCP framework for MCP servers
- `pydantic` - Data validation and settings
- `httpx` - Async HTTP client
- `feedparser` - RSS/Atom parsing
- `arxiv` - ArXiv API client
- `crawl4ai` - Web crawling with JS rendering
- `supabase` - Database client
- `openai` - Groq API (OpenAI-compatible)
- `google-generativeai` - Gemini API (backup)
- `python-telegram-bot` - Telegram integration
- `resend` - Email delivery

### **Frontend (TypeScript)**
- `next.js 14` - App Router
- `tailwindcss` - Styling
- `@supabase/supabase-js` - Database client
- `lucide-react` - Icons

### **Infrastructure (Cloud)**
- **GitHub Actions** - Cron scheduler (free 2,000 min/month)
- **Prefect Horizon** - MCP server hosting (free for personal)
- **Supabase** - PostgreSQL database (free 500MB)
- **Vercel** - Next.js hosting (free 100GB bandwidth)

---

## 🔑 **KEY FEATURES**

### **✅ PC-Independent**
- All servers run on cloud (Prefect Horizon)
- GitHub Actions triggers daily (cloud runner)
- Your computer never needs to be on

### **✅ Zero Cost**
- Every service used remains within free tiers
- No credit cards required for any service
- **Total monthly cost: $0**

### **✅ Production-Grade**
- Structured JSON logging
- Retry logic with exponential backoff
- Circuit breakers for each data source
- Graceful degradation (continues if one source fails)
- Comprehensive error tracking
- Audit logs in database

### **✅ Dual AI Provider**
- **Primary**: Groq (`llama-3.3-70b-versatile`)
- **Backup**: Gemini (`gemini-2.0-flash-exp`)
- Switchable via environment variable
- Automatic fallback on rate limits

### **✅ Comprehensive Coverage**
Collects from:
- 📚 **Research**: ArXiv (5 categories), Papers With Code, Semantic Scholar, OpenReview (6 conferences)
- 📝 **Blogs**: 35+ RSS feeds (OpenAI, Anthropic, HuggingFace, LangChain, etc.)
- 👥 **Community**: Reddit (5 subreddits), Hacker News, Stack Overflow
- 💻 **Code**: GitHub trending + 22 framework releases
- 🛠️ **Tools**: HuggingFace models, Kaggle datasets, PyPI packages

---

## 📊 **EXPECTED DAILY OUTPUT**

Based on blueprint estimates:
- **~450-500 raw items** collected
- **~200-250 unique items** after deduplication
- **~75,000 Groq tokens** used (75% of daily limit)
- **~5-6 API calls** (batched, 40-45 items each)
- **3 delivery channels** (Email, Telegram, Discord)
- **1 searchable dashboard** (always live)

---

## 🎨 **DIGEST SECTIONS**

Each morning you'll receive:

1. **🚨 Breaking News** - Critical updates (is_breaking = true)
2. **🔧 Framework Updates** - LangChain, LangGraph, CrewAI, FastAPI, etc.
3. **📰 Top News** - Score 7+ items
4. **💻 GitHub Trending** - Repos sorted by stars
5. **📚 Research Papers** - Top 5 by relevance score

---

## 🧪 **CURRENT STATUS**

**Phase**: Testing & Planning (Week 0)

**Progress**:
- ✅ Documentation complete
- ✅ Testing guide ready
- ✅ Project roadmap defined
- ⏳ API testing in progress
- ⏳ Account setup in progress

**Next Steps**:
1. Complete all API tests (see [TESTING_GUIDE.md](TESTING_GUIDE.md))
2. Document results (see [TESTING_RESULTS.md](TESTING_RESULTS.md))
3. Start Week 1: Build Research Server

---

## ❓ **FAQ**

**Q: Do I need to pay for any service?**
A: No. Every service has a generous free tier that covers this use case.

**Q: Does my PC need to be on at 7 AM every day?**
A: No. Everything runs on cloud servers (Prefect Horizon + GitHub Actions).

**Q: What if one data source breaks?**
A: The system continues with other sources. Failed sources are logged.

**Q: Can I customize the sources?**
A: Yes. Edit `config/rss_sources.yaml` to add/remove feeds.

**Q: Can I change the schedule?**
A: Yes. Edit the cron expression in `.github/workflows/daily_digest.yml`.

**Q: Why both Groq AND Gemini?**
A: Redundancy. If Groq hits rate limits or has downtime, the system automatically switches to Gemini.

**Q: How long does the full build take?**
A: ~4 weeks following the roadmap (can be compressed if working full-time).

---

## 🙏 **ACKNOWLEDGMENTS**

This system is built on:
- **FastMCP** by Prefect (MCP framework)
- **Model Context Protocol** by Anthropic
- Open-source libraries: arxiv, feedparser, httpx, etc.
- Cloud providers' generous free tiers

---

## 📄 **LICENSE**

MIT License - Feel free to use, modify, and distribute.

---

## 🤝 **CONTRIBUTING**

This is a personal project, but if you build something similar:
- Share your [TESTING_RESULTS.md](TESTING_RESULTS.md) findings
- Document any new data sources discovered
- Report issues with specific APIs

---

## 📞 **SUPPORT**

Stuck? Check these resources:
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Detailed test instructions
- **[ACCOUNTS_SETUP.md](ACCOUNTS_SETUP.md)** - Setup troubleshooting
- **[AI_ML_Digest_MCP_Blueprint.md](AI_ML_Digest_MCP_Blueprint.md)** - Technical deep dive
- **FastMCP Docs**: https://gofastmcp.com
- **Prefect Horizon**: https://docs.prefect.io/horizon

---

## 🚀 **LET'S BUILD!**

Ready to start? Follow the guides in order:

1. **[ACCOUNTS_SETUP.md](ACCOUNTS_SETUP.md)** ← Set up all accounts (1 day)
2. **[TESTING_GUIDE.md](TESTING_GUIDE.md)** ← Test all APIs (3-5 days)
3. **[TESTING_RESULTS.md](TESTING_RESULTS.md)** ← Document findings (ongoing)
4. **[PROJECT_ROADMAP.md](PROJECT_ROADMAP.md)** ← Build the system (4 weeks)

**Current Phase**: Week 0 - Testing & Validation

---

*Last Updated: 2026-02-24*
*Status: Planning & Testing Phase*
