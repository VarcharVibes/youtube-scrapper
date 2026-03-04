# YouTube Scrapper + NotebookLM Research Pipeline

Automate YouTube research: search for videos → ingest into Google NotebookLM → extract AI insights → log to Notion.

---

## What It Does

1. **Search YouTube** — scrape video metadata (title, channel, views, duration, URL) using yt-dlp. No downloads.
2. **Create a NotebookLM notebook** — automatically adds all video URLs as sources.
3. **Extract AI insights** — asks NotebookLM for key takeaways and practical action steps.
4. **Generate a mind map** — triggered inside NotebookLM (viewable at notebooklm.google.com).
5. **Log to Notion** — saves one row per research session with AI-generated content only (no raw video data).

---

## Scripts

| Script | Purpose |
|--------|---------|
| `yt_search.py` | Standalone YouTube metadata scraper |
| `notebooklm_runner.py` | Full CLI wrapper for NotebookLM automation |
| `yt_pipeline.py` | End-to-end orchestrator (search → NLM → Notion) |

---

## Requirements

### Python packages
```bash
pip3 install yt-dlp httpx
pip3 install "notebooklm-py[browser]"
playwright install chromium
```

### One-time NotebookLM auth
```bash
notebooklm login
# Opens browser → log in with your Google account → session saved locally
```

### Environment variables
Set in your shell or `.env` file:
```
NOTION_API_KEY=your_notion_integration_key
NOTION_DB_ID=your_research_sessions_database_id
```

---

## Quick Start

### 1. Search YouTube only
```bash
# Print a formatted table
python3 yt_search.py "AI influencer monetization" --count 20 --output table

# Export as JSON (pipe to other tools)
python3 yt_search.py "AI agents 2025" --count 15 --output json > /tmp/videos.json

# Export as CSV
python3 yt_search.py "ChatGPT tutorials" --count 10 --output csv
```

### 2. Full pipeline (YouTube → NotebookLM → Notion)
```bash
python3 yt_pipeline.py "AI influencer monetization" --count 20
python3 yt_pipeline.py "TikTok growth hacks" --count 15 --output table
python3 yt_pipeline.py "make money AI models" --count 20 --no-mindmap
```

### 3. NotebookLM only (manual control)
```bash
# Create a notebook
NB_ID=$(python3 notebooklm_runner.py create "My Research" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['notebook_id'])")

# Add YouTube sources
python3 notebooklm_runner.py add-sources $NB_ID \
  --urls https://www.youtube.com/watch?v=abc https://www.youtube.com/watch?v=def

# Or add from yt_search.py JSON output
python3 notebooklm_runner.py add-sources $NB_ID --urls-file /tmp/videos.json

# Ask a question
python3 notebooklm_runner.py ask $NB_ID "What are the top 5 takeaways?"

# Generate artifacts
python3 notebooklm_runner.py generate $NB_ID audio --wait --output podcast.mp4
python3 notebooklm_runner.py generate $NB_ID report --format study_guide --wait --output guide.pdf
python3 notebooklm_runner.py generate $NB_ID mindmap --wait --output mindmap.png
python3 notebooklm_runner.py generate $NB_ID infographic --wait --output infographic.png
python3 notebooklm_runner.py generate $NB_ID quiz --format medium --wait --output quiz.pdf
python3 notebooklm_runner.py generate $NB_ID flashcards --wait --output flashcards.pdf
python3 notebooklm_runner.py generate $NB_ID slide --wait --output slides.pdf

# Batch generate multiple types at once
python3 notebooklm_runner.py batch-generate $NB_ID \
  --types audio,report,infographic,mindmap \
  --output-dir ./research_outputs/

# List all notebooks
python3 notebooklm_runner.py list
```

---

## `yt_search.py` — Output Schema

JSON output (per video):
```json
{
  "title": "How I Make $10k/Month with AI Influencers",
  "channel": "TechCreator",
  "view_count": 245000,
  "view_count_fmt": "245K",
  "duration_secs": 742,
  "duration_fmt": "12:22",
  "upload_date": "2024-11-15",
  "url": "https://www.youtube.com/watch?v=abc123"
}
```

---

## `notebooklm_runner.py` — Artifact Types

| Type | `--format` options | Downloads as |
|------|-------------------|-------------|
| `audio` | — | `.mp4` |
| `report` | `study_guide` (default), `faq`, `timeline`, `briefing` | `.pdf` |
| `quiz` | `easy`, `medium` (default), `hard` | `.pdf` |
| `flashcards` | — | `.pdf` |
| `infographic` | — | `.png` |
| `mindmap` | — | `.png` |
| `slide` | — | `.pdf` |
| `video` | — | Not downloadable (view in NotebookLM UI) |

---

## `yt_pipeline.py` — What Gets Saved to Notion

Each research run creates **one Notion row** with:
- NotebookLM notebook link
- Key Takeaways (10 bullet points from all videos combined)
- Practical Action Steps (10 numbered steps, specific and actionable)

Raw video metadata (titles, views, URLs, etc.) is **not** saved to Notion.
The mind map lives inside NotebookLM — view it at [notebooklm.google.com](https://notebooklm.google.com).

---

## Notion Setup

1. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Copy the integration key → set as `NOTION_API_KEY`
3. Share your target database with the integration
4. Update `RESEARCH_DB_ID` in `yt_pipeline.py` with your database ID

Required database properties:
| Property | Type |
|----------|------|
| Topic | Title |
| Date | Date |
| Status | Select |
| Videos Found | Number |
| Notebook ID | Rich text |
| Notebook URL | URL |

Copy the database ID from the Notion URL and set it as `NOTION_DB_ID` in your environment.

---

## Limits

- YouTube search: max 50 videos per query (yt-dlp reliable limit)
- NotebookLM: max 50 sources per notebook
- NotebookLM is an unofficial API — subject to breakage if Google changes endpoints
- Audio/report generation typically takes 1–10 minutes on Google's servers
- NotebookLM session cookies expire after days/weeks — re-run `notebooklm login` when needed

---

## Cost Estimation

**This pipeline is 100% free to run.** No paid APIs used.

| Service | Cost | Account needed |
|---------|------|---------------|
| YouTube scraping (yt-dlp) | Free | None |
| Google NotebookLM | Free | Free Google account |
| Notion logging | Free | Free Notion account |
| notebooklm-py library | Free | None |

### Per-search cost breakdown

| Search size | Time to complete | Cost |
|-------------|-----------------|------|
| 5 videos, no mindmap | ~2–3 min | $0 |
| 10 videos + mindmap | ~5–8 min | $0 |
| 20 videos + mindmap | ~8–12 min | $0 |
| 50 videos + mindmap | ~12–20 min | $0 |

Most of the time is Google's servers processing NotebookLM sources and generating artifacts — not your machine.

### The only "cost" is time
- Source processing: ~1 min per 10 videos (done on Google's servers)
- Mind map generation: 2–5 min
- Audio podcast generation: 3–10 min
- Study guide / report: 2–5 min
- Infographic / flashcards: 1–3 min

> **NotebookLM Plus** ($20/month) gives higher limits and priority generation. The free tier is sufficient for most use cases.

---

## Use Cases

This tool works for **any topic** you want to research on YouTube. Run it whenever you want to quickly understand a subject without watching hours of videos.

### Business & Entrepreneurship
```bash
python3 yt_pipeline.py "dropshipping 2025 beginners" --count 20
python3 yt_pipeline.py "Amazon FBA product research" --count 15
python3 yt_pipeline.py "cold email sales strategy" --count 20
python3 yt_pipeline.py "agency business model how to start" --count 20
python3 yt_pipeline.py "SaaS startup lessons learned" --count 15
```

### Marketing & Growth
```bash
python3 yt_pipeline.py "YouTube channel growth strategy" --count 20
python3 yt_pipeline.py "TikTok viral content formula" --count 20
python3 yt_pipeline.py "email list building strategies" --count 15
python3 yt_pipeline.py "SEO for beginners 2025" --count 20
python3 yt_pipeline.py "personal branding tips creators" --count 15
```

### AI & Tech
```bash
python3 yt_pipeline.py "AI agent frameworks tutorial" --count 20
python3 yt_pipeline.py "Claude Code tips and tricks" --count 15
python3 yt_pipeline.py "n8n automation workflows" --count 20
python3 yt_pipeline.py "AI tools for content creators" --count 20
python3 yt_pipeline.py "prompt engineering best practices" --count 15
```

### Investing & Finance
```bash
python3 yt_pipeline.py "real estate investing for beginners" --count 20
python3 yt_pipeline.py "stock market investing strategy 2025" --count 15
python3 yt_pipeline.py "passive income ideas that actually work" --count 20
python3 yt_pipeline.py "crypto trading strategies" --count 15
```

### Learning & Skills
```bash
python3 yt_pipeline.py "learn Python fast beginner" --count 20
python3 yt_pipeline.py "public speaking tips" --count 15
python3 yt_pipeline.py "copywriting techniques that convert" --count 20
python3 yt_pipeline.py "negotiation skills salary" --count 15
```

### Health & Lifestyle
```bash
python3 yt_pipeline.py "intermittent fasting results how to" --count 15
python3 yt_pipeline.py "morning routine productivity" --count 20
python3 yt_pipeline.py "sleep optimization science" --count 15
```

### Research & Competitive Intelligence
```bash
# Understand a competitor's content strategy
python3 yt_pipeline.py "MrBeast video strategy breakdown" --count 10

# Quickly onboard to an unfamiliar industry
python3 yt_pipeline.py "supply chain management explained" --count 20

# Generate content ideas from what's already working
python3 yt_pipeline.py "faceless YouTube channel ideas 2025" --count 20
```

Each run gives you:
- A NotebookLM notebook with all videos as sources (ask it anything)
- 10 key takeaways distilled from all videos combined
- 10 specific action steps you can take immediately
- A visual mind map of the topic
- Everything logged to Notion for future reference

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `notebooklm login` auth error | Re-run `notebooklm login` — session expired |
| `ImportError: notebooklm` | `pip3 install "notebooklm-py[browser]" && playwright install chromium` |
| `yt-dlp` not found | `pip3 install yt-dlp` |
| Notion page not created | Check `NOTION_API_KEY` is set and integration has access to the DB |
| Generation never returns | Use `--wait` with complex notebooks (50 sources can take 15 min) |
| Some YouTube URLs fail | Video may be private or age-restricted — reported per-URL, pipeline continues |

---

## Author

Built by **Varchar Vibes**

- X (Twitter): [@varchar_dev](https://x.com/varchar_dev)
