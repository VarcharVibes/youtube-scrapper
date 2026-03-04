#!/usr/bin/env python3
"""
yt_pipeline.py — YouTube search → NotebookLM → Notion knowledge page.

What it does per search:
  1. Scrapes YouTube metadata
  2. Creates a NotebookLM notebook and adds all video URLs as sources
  3. Waits for NotebookLM to process the sources
  4. Asks NotebookLM for: executive summary, key takeaways, practical action steps
  5. Generates a mind map (downloaded locally)
  6. Logs ONE Notion page per search with the AI-extracted knowledge:
       - Executive summary
       - Key takeaways (bullet list)
       - Practical action steps (numbered list)
       - NotebookLM notebook link
       - Local download paths

Raw video metadata (titles, views, etc.) is NOT saved to Notion.

Usage:
    python3 yt_pipeline.py "AI influencer monetization" --count 20
    python3 yt_pipeline.py "TikTok growth hacks" --count 15 --output table
    python3 yt_pipeline.py "make money AI models" --count 20 --no-mindmap

Environment variables (set in ~/.config/credentials/.env):
    NOTION_API_KEY    — Notion integration key
"""

import os
import sys
import json
import asyncio
import argparse
import datetime
import concurrent.futures
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

NOTION_KEY     = os.environ.get("NOTION_API_KEY", "")
NOTION_VER     = "2022-06-28"
RESEARCH_DB_ID = os.environ.get("NOTION_DB_ID", "")   # set in .env or environment
SCRAPPER_DIR   = Path(__file__).parent

NLM_QUESTIONS = {
    "takeaways": (
        "List the top 10 most important insights and key takeaways from all sources combined. "
        "Number each one (1. 2. 3. etc). Keep each takeaway to 1-2 sentences."
    ),
    "action_steps": (
        "List exactly 10 practical action steps someone can take RIGHT NOW based on the strategies "
        "and insights in these sources. "
        "Number each step (1. 2. 3. etc). Be specific and actionable."
    ),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _log(msg: str):
    print(msg, file=sys.stderr)


def _exit_error(msg: str):
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


def _text_to_rich(text: str, limit: int = 2000) -> list:
    """Convert plain text to Notion rich_text array (respects 2000-char limit per block)."""
    text = text[:limit]
    return [{"text": {"content": text}}]


def _split_numbered_lines(text: str) -> list[str]:
    """
    Parse a numbered list from NLM response.
    Handles: '1. text', '1) text', lines starting with a digit.
    Returns list of clean strings (without the number prefix).
    """
    import re
    lines = text.strip().split("\n")
    items = []
    current = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # New numbered item
        if re.match(r"^\d+[\.\)]\s+", line):
            if current:
                items.append(current.strip())
            current = re.sub(r"^\d+[\.\)]\s+", "", line)
        else:
            # Continuation of previous item
            current += " " + line if current else line
    if current:
        items.append(current.strip())
    return items


# ── Step 1: YouTube search ────────────────────────────────────────────────────

def run_search(query: str, count: int) -> list[dict]:
    import subprocess
    script = SCRAPPER_DIR / "yt_search.py"
    result = subprocess.run(
        [sys.executable, str(script), query, "--count", str(count), "--output", "json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        _exit_error(f"yt_search.py failed: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        _exit_error(f"yt_search.py invalid JSON: {result.stdout[:200]}")


# ── Step 2: NotebookLM setup ──────────────────────────────────────────────────

async def _setup_notebook(nb_name: str, urls: list[str]) -> str:
    from notebooklm import NotebookLMClient

    async with await NotebookLMClient.from_storage() as client:
        nb = await client.notebooks.create(title=nb_name)
        nb_id = nb.id if hasattr(nb, "id") else str(nb)
        _log(f"  Notebook: {nb_id}")

        # Add sources
        ok = err = 0
        for url in urls:
            try:
                await client.sources.add_url(nb_id, url)
                ok += 1
            except Exception as e:
                err += 1
                _log(f"  ⚠ source error: {e}")
        _log(f"  Sources: {ok} added, {err} errors")

        # Wait for all sources to finish processing
        _log("  Waiting for NotebookLM to process sources...")
        try:
            source_list = await client.sources.list(nb_id)
            source_ids = [s.id for s in source_list if hasattr(s, "id")]
            if source_ids:
                await client.sources.wait_for_sources(nb_id, source_ids, timeout=300)
            _log("  Sources ready.")
        except Exception as e:
            _log(f"  ⚠ source wait: {e} — proceeding anyway")

    return nb_id


async def _ask_notebook(nb_id: str, questions: dict) -> dict:
    """Ask multiple questions and return {key: answer_text}."""
    from notebooklm import NotebookLMClient
    answers = {}
    async with await NotebookLMClient.from_storage() as client:
        for key, question in questions.items():
            try:
                _log(f"  Asking: {key}...")
                result = await client.chat.ask(nb_id, question)
                # Extract plain text from result
                if hasattr(result, "text"):
                    answers[key] = result.text
                elif isinstance(result, dict):
                    answers[key] = result.get("text") or result.get("answer") or str(result)
                else:
                    answers[key] = str(result)
            except Exception as e:
                _log(f"  ⚠ ask({key}) failed: {e}")
                answers[key] = ""
    return answers


async def _generate_mindmap(nb_id: str) -> bool:
    """Trigger mind map generation inside NotebookLM. No local download."""
    from notebooklm import NotebookLMClient
    try:
        async with await NotebookLMClient.from_storage() as client:
            status = await client.artifacts.generate_mind_map(nb_id)
            task_id = getattr(status, "task_id", None) or (
                status.get("task_id") if isinstance(status, dict) else None
            )
            if task_id:
                await client.artifacts.wait_for_completion(nb_id, task_id)
        return True
    except Exception as e:
        _log(f"  ⚠ Mind map generation failed: {e}")
        return False


# ── Step 3: Build Notion page content blocks ──────────────────────────────────

def _build_notion_blocks(
    query: str,
    nb_id: str,
    nb_name: str,
    video_count: int,
    answers: dict,
) -> list:
    """Build the Notion page children blocks."""
    nb_url = f"https://notebooklm.google.com/notebook/{nb_id}"
    blocks = []

    # ── NotebookLM link callout ──
    blocks.append({
        "object": "block", "type": "callout",
        "callout": {
            "rich_text": [{"text": {"content": f"📓 NotebookLM Notebook → {nb_url}"}}],
            "icon": {"emoji": "📓"},
            "color": "blue_background"
        }
    })
    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # ── Key Takeaways ──
    if answers.get("takeaways"):
        blocks.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "✅ Key Takeaways"}}]}
        })
        items = _split_numbered_lines(answers["takeaways"])
        if items:
            for item in items:
                for chunk in [item[i:i+1999] for i in range(0, len(item), 1999)]:
                    blocks.append({
                        "object": "block", "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": _text_to_rich(chunk)}
                    })
        else:
            # Fallback: raw text as paragraph
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": _text_to_rich(answers["takeaways"][:1999])}
            })
        blocks.append({"object": "block", "type": "divider", "divider": {}})

    # ── Practical Action Steps ──
    if answers.get("action_steps"):
        blocks.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "🎯 Practical Action Steps"}}]}
        })
        steps = _split_numbered_lines(answers["action_steps"])
        if steps:
            for step in steps:
                for chunk in [step[i:i+1999] for i in range(0, len(step), 1999)]:
                    blocks.append({
                        "object": "block", "type": "numbered_list_item",
                        "numbered_list_item": {"rich_text": _text_to_rich(chunk)}
                    })
        else:
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": _text_to_rich(answers["action_steps"][:1999])}
            })
        blocks.append({"object": "block", "type": "divider", "divider": {}})

    return blocks


# ── Step 4: Save to Notion ────────────────────────────────────────────────────

def save_to_notion(
    query: str,
    nb_id: str,
    nb_name: str,
    video_count: int,
    answers: dict,
) -> str:
    """Create one Notion DB row (with page content) per research session. Returns page URL."""
    try:
        import httpx
    except ImportError:
        _log("⚠ httpx not installed — skipping Notion. Run: pip3 install httpx")
        return ""

    if not NOTION_KEY:
        _log("⚠ NOTION_API_KEY not set — skipping Notion.")
        return ""

    headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Notion-Version": NOTION_VER,
        "Content-Type": "application/json"
    }
    nb_url = f"https://notebooklm.google.com/notebook/{nb_id}"
    today = datetime.date.today().isoformat()
    blocks = _build_notion_blocks(query, nb_id, nb_name, video_count, answers)

    # Notion API limits: max 100 children per request
    # Create the page first with properties + first batch of blocks
    first_batch = blocks[:100]
    body = {
        "parent": {"database_id": RESEARCH_DB_ID},
        "properties": {
            "Topic":        {"title":     [{"text": {"content": query[:200]}}]},
            "Date":         {"date":      {"start": today}},
            "Status":       {"select":    {"name": "Done"}},
            "Videos Found": {"number":    video_count},
            "Notebook ID":  {"rich_text": [{"text": {"content": nb_id}}]},
            "Notebook URL": {"url":       nb_url},
        },
        "children": first_batch
    }

    with httpx.Client(timeout=30) as client:
        r = client.post("https://api.notion.com/v1/pages", headers=headers, json=body)
        if r.status_code != 200:
            _log(f"⚠ Notion page create failed: {r.status_code} {r.json().get('message','')}")
            return ""

        page_id = r.json().get("id", "")
        page_url = r.json().get("url", "")

        # Append remaining blocks if any
        remaining = blocks[100:]
        if remaining and page_id:
            for i in range(0, len(remaining), 100):
                chunk = remaining[i:i+100]
                r2 = client.patch(
                    f"https://api.notion.com/v1/blocks/{page_id}/children",
                    headers=headers,
                    json={"children": chunk}
                )
                if r2.status_code != 200:
                    _log(f"⚠ Notion block append failed: {r2.status_code}")

    return page_url


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(query: str, count: int, output_fmt: str, skip_mindmap: bool):
    today = datetime.date.today().strftime("%Y-%m-%d")

    _log(f"\n🔍 Searching YouTube: \"{query}\" ({count} videos)")
    videos = run_search(query, count)
    if not videos:
        _exit_error("No YouTube results found.")
    _log(f"  Found: {len(videos)} videos")

    if output_fmt == "table":
        import subprocess
        subprocess.run([
            sys.executable, str(SCRAPPER_DIR / "yt_search.py"),
            query, "--count", str(count), "--output", "table"
        ])

    _log("\n📓 Setting up NotebookLM...")
    nb_name = f"{query[:60]} — {today}"
    urls = [v["url"] for v in videos]
    nb_id = _run_async(_setup_notebook(nb_name, urls))

    _log("\n💬 Extracting insights from NotebookLM...")
    answers = _run_async(_ask_notebook(nb_id, NLM_QUESTIONS))

    if not skip_mindmap:
        _log("\n🗺  Generating mind map in NotebookLM...")
        ok = _run_async(_generate_mindmap(nb_id))
        _log("  Mind map ready — view it in NotebookLM." if ok else "  ⚠ Mind map skipped.")

    _log("\n📋 Saving to Notion...")
    page_url = save_to_notion(query, nb_id, nb_name, len(videos), answers)
    if page_url:
        _log(f"  Notion page: {page_url}")

    _log("\n✅ Done\n")

    result = {
        "query":        query,
        "video_count":  len(videos),
        "notebook_id":  nb_id,
        "notebook_url": f"https://notebooklm.google.com/notebook/{nb_id}",
        "notion_page":  page_url,
    }
    if output_fmt == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"\nNotebook : https://notebooklm.google.com/notebook/{nb_id}")
        print(f"Notion   : {page_url}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="YouTube search → NotebookLM → Notion knowledge page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
What gets saved to Notion (per search):
  - Executive summary
  - Key takeaways (bullet list)
  - Practical action steps (numbered list)
  - NotebookLM notebook link
  - Source videos list (collapsible)
  Raw video metadata is NOT saved to Notion.

Examples:
  python3 yt_pipeline.py "AI influencer monetization" --count 20
  python3 yt_pipeline.py "TikTok growth hacks" --count 15 --output table
  python3 yt_pipeline.py "make money AI models" --count 20 --no-mindmap
        """
    )
    parser.add_argument("query",                    help="YouTube search query")
    parser.add_argument("--count",    "-n",         type=int, default=10,
                        help="Number of videos (default: 10, max: 50)")
    parser.add_argument("--output",   "-o",         choices=["json", "table"], default="table",
                        help="Output format (default: table)")
    parser.add_argument("--no-mindmap", action="store_true",
                        help="Skip mind map generation (faster)")

    args = parser.parse_args()
    count = min(max(1, args.count), 50)
    run_pipeline(args.query, count, args.output, args.no_mindmap)


if __name__ == "__main__":
    main()
