#!/usr/bin/env python3
"""
yt_search.py — Search YouTube and extract video metadata using yt-dlp.
No video downloads. Metadata only. CLI-friendly with JSON, CSV, and table output.

Usage:
    python3 yt_search.py "AI automation" --count 10 --output json
    python3 yt_search.py "python tips" --output table
    python3 yt_search.py "machine learning" --count 5 --output csv
    python3 yt_search.py "devops" --count 10 --output json | python3 -c "import sys,json; [print(v['url']) for v in json.load(sys.stdin)]"
"""

import sys
import json
import argparse
import csv
from typing import Optional


# ── Helpers ──────────────────────────────────────────────────────────────────

def _format_duration(seconds: Optional[int]) -> str:
    """Convert integer seconds to HH:MM:SS or MM:SS string."""
    if not seconds:
        return "Unknown"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_views(count: Optional[int]) -> str:
    """Format view count as a human-readable string."""
    if count is None:
        return "Unknown"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.0f}K"
    return str(count)


def _parse_date(upload_date: Optional[str]) -> str:
    """Convert yt-dlp date string '20240315' to ISO '2024-03-15'."""
    if not upload_date or len(upload_date) != 8:
        return upload_date or "Unknown"
    return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"


def _build_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


# ── Core search ───────────────────────────────────────────────────────────────

def search_youtube(query: str, count: int = 10) -> list[dict]:
    """
    Search YouTube using yt-dlp's ytsearch extractor.
    Returns list of video metadata dicts. Never downloads video files.
    Uses extract_flat for speed — one HTTP request per search.
    """
    try:
        import yt_dlp
    except ImportError:
        print(json.dumps({"error": "yt-dlp not installed. Run: pip install yt-dlp"}),
              file=sys.stderr)
        sys.exit(1)

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "ignoreerrors": True,
        "playlist_items": f"1-{count}",
    }

    results = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
    except Exception as e:
        # yt_dlp.utils.DownloadError and other errors
        print(json.dumps({"error": f"yt-dlp search failed: {str(e)}"}), file=sys.stderr)
        sys.exit(1)

    if not info or "entries" not in info:
        return []

    for entry in (info.get("entries") or []):
        if not entry:
            continue

        video_id = entry.get("id") or ""
        if not video_id:
            # Fallback: parse id from url field if present
            raw_url = entry.get("url", "")
            if "v=" in raw_url:
                video_id = raw_url.split("v=")[-1].split("&")[0]
        if not video_id:
            continue

        duration_secs = entry.get("duration")

        results.append({
            "title":          entry.get("title") or "Unknown",
            "channel":        entry.get("uploader") or entry.get("channel") or "Unknown",
            "view_count":     entry.get("view_count"),
            "view_count_fmt": _format_views(entry.get("view_count")),
            "duration_secs":  duration_secs,
            "duration_fmt":   _format_duration(duration_secs),
            "upload_date":    _parse_date(entry.get("upload_date")),
            "url":            _build_url(video_id),
        })

    return results


# ── Output formatters ─────────────────────────────────────────────────────────

def output_json(results: list[dict]) -> None:
    print(json.dumps(results, indent=2, ensure_ascii=False))


def output_csv(results: list[dict]) -> None:
    if not results:
        print("No results found.")
        return
    fields = ["title", "channel", "view_count_fmt", "duration_fmt", "upload_date", "url"]
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=fields,
        extrasaction="ignore",
        lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(results)


def output_table(results: list[dict]) -> None:
    if not results:
        print("No results found.")
        return

    W = {"num": 4, "title": 52, "channel": 20, "views": 8, "duration": 9, "date": 12}

    header = (
        f"{'#':<{W['num']}} "
        f"{'Title':<{W['title']}} "
        f"{'Channel':<{W['channel']}} "
        f"{'Views':<{W['views']}} "
        f"{'Duration':<{W['duration']}} "
        f"{'Date':<{W['date']}}"
    )
    sep = "-" * len(header)

    print(sep)
    print(header)
    print(sep)

    for i, v in enumerate(results, 1):
        title = v["title"]
        if len(title) > W["title"]:
            title = title[:W["title"] - 3] + "..."
        channel = v["channel"]
        if len(channel) > W["channel"]:
            channel = channel[:W["channel"] - 3] + "..."

        print(
            f"{i:<{W['num']}} "
            f"{title:<{W['title']}} "
            f"{channel:<{W['channel']}} "
            f"{v['view_count_fmt']:<{W['views']}} "
            f"{v['duration_fmt']:<{W['duration']}} "
            f"{v['upload_date']:<{W['date']}}"
        )

    print(sep)
    print("\nURLs:")
    for i, v in enumerate(results, 1):
        print(f"  {i}. {v['url']}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Search YouTube and extract video metadata (no downloads).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 yt_search.py "AI automation" --count 10 --output json
  python3 yt_search.py "python tips" --output table
  python3 yt_search.py "devops" --count 5 --output csv
  python3 yt_search.py "LLMs" --output json | python3 -c "import sys,json; [print(v['url']) for v in json.load(sys.stdin)]"
        """
    )
    parser.add_argument("query", help="YouTube search query")
    parser.add_argument("--count", "-n", type=int, default=10,
                        help="Number of results (default: 10, max: 50)")
    parser.add_argument("--output", "-o",
                        choices=["json", "csv", "table"],
                        default="json",
                        help="Output format (default: json)")

    args = parser.parse_args()
    count = min(max(1, args.count), 50)
    results = search_youtube(args.query, count)

    if args.output == "json":
        output_json(results)
    elif args.output == "csv":
        output_csv(results)
    else:
        output_table(results)


if __name__ == "__main__":
    main()
