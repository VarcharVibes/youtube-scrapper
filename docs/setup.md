# Setup Guide

## 1. Install Python Dependencies

```bash
pip3 install yt-dlp httpx
pip3 install "notebooklm-py[browser]"
playwright install chromium
```

## 2. NotebookLM Authentication (One-Time)

```bash
notebooklm login
```

This opens a browser window. Log in with your Google account. The session is saved locally — no API key needed. Re-run this command if you get auth errors (sessions expire after days/weeks).

## 3. Set Environment Variables

Add to your `~/.zshrc` or `~/.bashrc`:
```bash
export NOTION_API_KEY="your_notion_integration_key"
export NOTION_DB_ID="your_research_sessions_database_id"
```

Or pass inline when running:
```bash
NOTION_API_KEY="..." NOTION_DB_ID="..." python3 yt_pipeline.py "your query"
```

## 4. Notion Setup

### Create an Integration
1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **New integration**
3. Give it a name (e.g., "YouTube Scrapper")
4. Copy the **Internal Integration Secret** → this is your `NOTION_API_KEY`

### Connect to Your Database
1. Open your Notion database
2. Click `...` (top right) → **Connect to** → select your integration
3. Copy the database ID from the URL:
   ```
   https://notion.so/workspace/DATABASE_ID_HERE?v=...
   ```
4. Copy the database ID from the URL and set it as `NOTION_DB_ID` in your environment

### Required Database Properties
Create these properties in your Notion database:

| Property Name | Type |
|--------------|------|
| Topic | Title |
| Date | Date |
| Status | Select (add option: "Done") |
| Videos Found | Number |
| Notebook ID | Rich text |
| Notebook URL | URL |

## 5. Verify Everything Works

```bash
# Test YouTube scraper
python3 yt_search.py "test query" --count 3 --output table

# Test NotebookLM auth
python3 notebooklm_runner.py list

# Test full pipeline (uses ~5 videos, fast)
python3 yt_pipeline.py "AI tools" --count 5 --no-mindmap
```
