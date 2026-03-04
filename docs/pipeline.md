# Pipeline Architecture

## Overview

```
YouTube Search (yt_search.py)
        ↓
  Video URLs + Metadata
        ↓
NotebookLM Setup (notebooklm_runner.py)
  - Create notebook
  - Add all URLs as sources
  - Wait for processing
        ↓
AI Extraction
  - Key Takeaways (10 insights)
  - Practical Action Steps (10 steps)
  - Mind Map (stays in NotebookLM)
        ↓
Notion Logging (one row per search)
  - NLM notebook link
  - Key Takeaways
  - Action Steps
```

## Data Flow

### What goes WHERE

| Data | Destination |
|------|-------------|
| Video titles, views, URLs | NOT saved anywhere (used only to feed NLM) |
| AI-generated takeaways | Notion page |
| AI-generated action steps | Notion page |
| NotebookLM notebook link | Notion page |
| Mind map | NotebookLM only (view at notebooklm.google.com) |
| Raw metadata | Optionally printed to terminal (`--output table`) |

## Step-by-Step Internals

### Step 1 — YouTube Search
- Uses `yt-dlp` in flat-extract mode (`extract_flat: "in_playlist"`)
- One HTTP request per search — no video downloads
- Count clamped to 1–50 (reliable yt-dlp limit for `ytsearchN`)
- Returns: title, channel, view_count, duration, upload_date, url

### Step 2 — NotebookLM Notebook
- Creates notebook with name `"{query} — {date}"`
- Adds all video URLs via `sources.add_url()` (works for YouTube + any web URL)
- Waits up to 5 minutes for all sources to process before asking questions
- NotebookLM 50-source limit enforced server-side

### Step 3 — AI Extraction
Two questions asked sequentially:
1. **Takeaways** — top 10 insights from all sources combined (numbered list)
2. **Action Steps** — 10 specific, actionable steps (numbered list)

NLM responses parsed with `_split_numbered_lines()` — handles `1.`, `1)`, and continuation lines.

### Step 4 — Mind Map
- `client.artifacts.generate_mind_map(nb_id)` triggered
- Waits for completion
- NOT downloaded locally — view at notebooklm.google.com
- Skip with `--no-mindmap` flag

### Step 5 — Notion
- Creates one DB row in `📚 Research Sessions` database
- Page content: NLM callout link + Takeaways (bullets) + Action Steps (numbered)
- Notion API v2022-06-28 (required — newer versions strip properties)
- Blocks sent in batches of 100 (Notion API limit)

## CLI Reference

```
python3 yt_pipeline.py "query" [options]

Arguments:
  query               YouTube search query (required)

Options:
  --count, -n INT     Number of videos (default: 10, max: 50)
  --output, -o        json | table (default: table)
  --no-mindmap        Skip mind map generation (faster)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NOTION_API_KEY` | Yes | Notion integration key |
