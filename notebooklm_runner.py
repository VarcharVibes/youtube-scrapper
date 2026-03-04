#!/usr/bin/env python3
"""
notebooklm_runner.py — CLI wrapper around notebooklm-py.
All stdout output is JSON. Errors go to stderr as JSON.

Prerequisite (one-time):
    pip install "notebooklm-py[browser]"
    notebooklm login

Usage:
    python3 notebooklm_runner.py create "My Research"
    python3 notebooklm_runner.py list
    python3 notebooklm_runner.py add-sources NB_ID --urls https://youtube.com/watch?v=abc
    python3 notebooklm_runner.py add-sources NB_ID --urls-file videos.json
    python3 notebooklm_runner.py ask NB_ID "What are the key themes?"
    python3 notebooklm_runner.py generate NB_ID audio --wait
    python3 notebooklm_runner.py generate NB_ID report --format study_guide --wait --output report.pdf
    python3 notebooklm_runner.py download NB_ID infographic --output diagram.png
    python3 notebooklm_runner.py batch-generate NB_ID --types audio,report,infographic --output-dir ./out/
    python3 notebooklm_runner.py pipeline NB_ID --urls url1 url2 --ask "Summary?" --generate report --output report.pdf
"""

import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import Optional
import concurrent.futures


# ── Utilities ─────────────────────────────────────────────────────────────────

def _run_async(coro):
    """Run an async coroutine from a sync context. Handles nested event loops."""
    try:
        asyncio.get_running_loop()
        # Already inside an event loop — dispatch to a worker thread with its own loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


def _print_json(data):
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _exit_error(message: str, code: int = 1):
    print(json.dumps({"error": message}), file=sys.stderr)
    sys.exit(code)


# ── URL helpers ───────────────────────────────────────────────────────────────

def _load_urls_from_file(path: str) -> list[str]:
    """
    Load URLs from a JSON file. Accepts:
      - Plain string array: ["url1", "url2"]
      - yt_search.py output (array of objects with "url" key): [{"url": "...", ...}]
    """
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        _exit_error(f"File not found: {path}")
    except json.JSONDecodeError as e:
        _exit_error(f"Invalid JSON in {path}: {e}")

    if not isinstance(data, list):
        _exit_error(f"Expected a JSON array in {path}, got {type(data).__name__}")

    urls = []
    for item in data:
        if isinstance(item, str):
            urls.append(item)
        elif isinstance(item, dict) and "url" in item:
            urls.append(item["url"])

    if not urls:
        _exit_error(f"No URLs found in {path}")
    return urls


def _batch_urls(urls: list, limit: int = 50) -> list[list]:
    return [urls[i:i + limit] for i in range(0, len(urls), limit)]


def _is_youtube_url(url: str) -> bool:
    return "youtube.com/watch" in url or "youtu.be/" in url


def _obj_to_dict(obj) -> dict:
    """Normalise library return values to plain dict for JSON serialisation."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {"raw": str(obj)}


# ── Async implementations ─────────────────────────────────────────────────────

async def _async_create(name: str) -> dict:
    from notebooklm import NotebookLMClient
    async with await NotebookLMClient.from_storage() as client:
        nb = await client.notebooks.create(title=name)
    nb_id = nb.id if hasattr(nb, "id") else str(nb)
    return {"notebook_id": nb_id, "name": name, "status": "created"}


async def _async_list() -> list:
    from notebooklm import NotebookLMClient
    async with await NotebookLMClient.from_storage() as client:
        notebooks = await client.notebooks.list()
    return [_obj_to_dict(nb) for nb in (notebooks or [])]


async def _async_add_sources(nb_id: str, urls: list[str]) -> list[dict]:
    from notebooklm import NotebookLMClient
    results = []
    async with await NotebookLMClient.from_storage() as client:
        for url in urls:
            try:
                await client.sources.add_url(nb_id, url)
                results.append({"url": url, "status": "added"})
            except Exception as e:
                results.append({"url": url, "status": "error", "error": str(e)})
    return results


async def _async_ask(nb_id: str, question: str) -> dict:
    from notebooklm import NotebookLMClient
    async with await NotebookLMClient.from_storage() as client:
        result = await client.chat.ask(nb_id, question)
    return _obj_to_dict(result)


# Map artifact type → (generate_method_name, kwargs_builder)
_GENERATE_MAP = {
    "audio":       ("generate_audio",      lambda opts: {
        "focus":        opts.get("focus"),
        "audio_length": int(opts.get("audio_length", 10)),
        "language":     opts.get("language", "en"),
    }),
    "video":       ("generate_video",      lambda opts: {"visual_style": opts.get("format")}),
    "report":      ("generate_report",     lambda opts: {
        "report_type": opts.get("format", "study_guide"),
        "append":      opts.get("append"),
    }),
    "quiz":        ("generate_quiz",       lambda opts: {
        "variant":    int(opts.get("variant", 1)),
        "difficulty": opts.get("format", "medium"),
    }),
    "flashcards":  ("generate_flashcards", lambda opts: {}),
    "infographic": ("generate_infographic",lambda opts: {}),
    "mindmap":     ("generate_mind_map",   lambda opts: {}),
    "slide":       ("generate_slide_deck", lambda opts: {}),
    "table":       ("generate_data_table", lambda opts: {}),
}

_DOWNLOAD_MAP = {
    "audio":       ("download_audio",      "mp4"),
    "report":      ("download_report",     "pdf"),
    "quiz":        ("download_quiz",       "pdf"),
    "flashcards":  ("download_flashcards", "pdf"),
    "infographic": ("download_infographic","png"),
    "mindmap":     ("download_mind_map",   "png"),
    "slide":       ("download_slide_deck", "pdf"),
}


async def _async_generate(nb_id: str, artifact_type: str, opts: dict, wait: bool) -> dict:
    from notebooklm import NotebookLMClient

    entry = _GENERATE_MAP.get(artifact_type)
    if not entry:
        raise ValueError(f"Unknown artifact type '{artifact_type}'. Valid: {', '.join(_GENERATE_MAP)}")

    method_name, kwargs_fn = entry
    kwargs = {k: v for k, v in kwargs_fn(opts).items() if v is not None}

    async with await NotebookLMClient.from_storage() as client:
        gen_method = getattr(client.artifacts, method_name)
        status = await gen_method(nb_id, **kwargs)

        result = {"artifact_type": artifact_type, "status": "submitted"}
        task_id = getattr(status, "task_id", None) or (
            status.get("task_id") if isinstance(status, dict) else None
        )
        if task_id:
            result["task_id"] = task_id

        if wait and task_id:
            final = await client.artifacts.wait_for_completion(nb_id, task_id)
            result["status"] = "completed"
            result["result"] = _obj_to_dict(final)
        elif wait:
            result["status"] = "completed"

    return result


async def _async_download(nb_id: str, artifact_type: str, output_path: str) -> dict:
    from notebooklm import NotebookLMClient

    entry = _DOWNLOAD_MAP.get(artifact_type)
    if not entry:
        raise ValueError(
            f"Download not supported for '{artifact_type}'. "
            f"Downloadable types: {', '.join(_DOWNLOAD_MAP)}"
        )

    method_name, _ = entry
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    async with await NotebookLMClient.from_storage() as client:
        dl_method = getattr(client.artifacts, method_name)
        await dl_method(nb_id, output_path)

    return {"artifact_type": artifact_type, "output": output_path, "status": "downloaded"}


# ── Subcommand handlers (sync, called by argparse) ────────────────────────────

def cmd_create(args):
    _print_json(_run_async(_async_create(args.name)))


def cmd_list(args):
    _print_json(_run_async(_async_list()))


def cmd_add_sources(args):
    if args.urls:
        urls = args.urls
    elif args.urls_file:
        urls = _load_urls_from_file(args.urls_file)
    else:
        _exit_error("Provide --urls or --urls-file")

    batches = _batch_urls(urls, limit=50)
    if len(batches) > 1:
        print(json.dumps({
            "info": f"{len(urls)} URLs → {len(batches)} batches of max 50"
        }), file=sys.stderr)

    all_results = []
    for i, batch in enumerate(batches):
        if len(batches) > 1:
            print(json.dumps({"batch": i + 1, "of": len(batches), "count": len(batch)}),
                  file=sys.stderr)
        all_results.extend(_run_async(_async_add_sources(args.notebook_id, batch)))

    _print_json({
        "notebook_id": args.notebook_id,
        "total": len(urls),
        "results": all_results,
    })


def cmd_ask(args):
    _print_json(_run_async(_async_ask(args.notebook_id, args.question)))


def cmd_generate(args):
    opts = {
        "format": getattr(args, "format", None),
        "append": getattr(args, "append", None),
    }
    wait = getattr(args, "wait", False)
    result = _run_async(_async_generate(args.notebook_id, args.type, opts, wait))

    # Auto-download if --output given and generation completed
    output = getattr(args, "output", None)
    if output and result.get("status") == "completed" and args.type in _DOWNLOAD_MAP:
        result["download"] = _run_async(_async_download(args.notebook_id, args.type, output))

    _print_json(result)


def cmd_download(args):
    _print_json(_run_async(_async_download(args.notebook_id, args.type, args.output)))


def cmd_batch_generate(args):
    types = [t.strip() for t in args.types.split(",")]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for artifact_type in types:
        try:
            gen_result = _run_async(_async_generate(
                args.notebook_id, artifact_type, {}, wait=True
            ))
            entry = _DOWNLOAD_MAP.get(artifact_type)
            if entry:
                _, ext = entry
                out_path = str(output_dir / f"{artifact_type}.{ext}")
                dl_result = _run_async(_async_download(args.notebook_id, artifact_type, out_path))
                results.append({"type": artifact_type, "generate": gen_result, "download": dl_result})
            else:
                results.append({"type": artifact_type, "generate": gen_result})
        except Exception as e:
            results.append({"type": artifact_type, "error": str(e)})

    _print_json({"notebook_id": args.notebook_id, "results": results})


def cmd_pipeline(args):
    result = {"notebook_id": args.notebook_id}

    # Step 1: add sources
    if args.urls:
        batches = _batch_urls(args.urls, limit=50)
        all_source_results = []
        for batch in batches:
            all_source_results.extend(_run_async(_async_add_sources(args.notebook_id, batch)))
        result["sources"] = all_source_results

    # Step 2: ask
    if args.ask:
        result["question"] = {
            "query": args.ask,
            "result": _run_async(_async_ask(args.notebook_id, args.ask)),
        }

    # Step 3: generate
    if args.generate:
        opts = {"format": getattr(args, "format", None)}
        gen_result = _run_async(_async_generate(args.notebook_id, args.generate, opts, wait=True))
        result["generate"] = gen_result

        # Step 4: download
        output = getattr(args, "output", None)
        if output and args.generate in _DOWNLOAD_MAP:
            result["download"] = _run_async(
                _async_download(args.notebook_id, args.generate, output)
            )

    _print_json(result)


# ── Argparse setup ────────────────────────────────────────────────────────────

_TYPES = list(_GENERATE_MAP.keys())
_DL_TYPES = list(_DOWNLOAD_MAP.keys())


def main():
    parser = argparse.ArgumentParser(
        description="NotebookLM CLI wrapper. Requires: notebooklm login",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
One-time auth setup:
    pip install "notebooklm-py[browser]"
    notebooklm login

Quick examples:
    python3 notebooklm_runner.py create "AI Research"
    python3 notebooklm_runner.py list
    python3 notebooklm_runner.py add-sources NB_ID --urls-file videos.json
    python3 notebooklm_runner.py generate NB_ID report --format study_guide --wait --output report.pdf
    python3 notebooklm_runner.py batch-generate NB_ID --types audio,report,infographic --output-dir ./out/
        """
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p = sub.add_parser("create", help="Create a new notebook")
    p.add_argument("name", help="Notebook name")
    p.set_defaults(func=cmd_create)

    # list
    p = sub.add_parser("list", help="List all notebooks")
    p.set_defaults(func=cmd_list)

    # add-sources
    p = sub.add_parser("add-sources", help="Add URL sources to a notebook (max 50 per notebook)")
    p.add_argument("notebook_id")
    p.add_argument("--urls", nargs="+", metavar="URL")
    p.add_argument("--urls-file", metavar="FILE",
                   help="JSON file with URLs (plain array or yt_search.py output)")
    p.set_defaults(func=cmd_add_sources)

    # ask
    p = sub.add_parser("ask", help="Ask a question; returns answer with source citations")
    p.add_argument("notebook_id")
    p.add_argument("question")
    p.set_defaults(func=cmd_ask)

    # generate
    p = sub.add_parser("generate", help="Generate an AI artifact from notebook sources")
    p.add_argument("notebook_id")
    p.add_argument("type", choices=_TYPES, metavar=f"type ({'/'.join(_TYPES)})")
    p.add_argument("--format",
                   help="Sub-format: study_guide|faq|timeline|briefing (report); easy|medium|hard (quiz)")
    p.add_argument("--output",
                   help="If set and --wait is used, auto-downloads artifact to this path")
    p.add_argument("--wait", action="store_true",
                   help="Block until generation completes")
    p.add_argument("--append", help="Extra instructions appended to the generation prompt")
    p.set_defaults(func=cmd_generate)

    # download
    p = sub.add_parser("download", help="Download the latest completed artifact")
    p.add_argument("notebook_id")
    p.add_argument("type", choices=_DL_TYPES, metavar=f"type ({'/'.join(_DL_TYPES)})")
    p.add_argument("--output", required=True, help="Local file path to save the artifact")
    p.set_defaults(func=cmd_download)

    # batch-generate
    p = sub.add_parser("batch-generate",
                        help="Generate and download multiple artifact types sequentially")
    p.add_argument("notebook_id")
    p.add_argument("--types", required=True,
                    help="Comma-separated types, e.g. audio,report,infographic")
    p.add_argument("--output-dir", default="./outputs",
                    help="Directory for downloaded artifacts (default: ./outputs)")
    p.set_defaults(func=cmd_batch_generate)

    # pipeline
    p = sub.add_parser("pipeline",
                        help="Add sources + ask a question + generate artifact in one command")
    p.add_argument("notebook_id")
    p.add_argument("--urls", nargs="+", metavar="URL")
    p.add_argument("--ask", metavar="QUESTION")
    p.add_argument("--generate", metavar="TYPE", choices=_TYPES)
    p.add_argument("--format", help="Artifact sub-format")
    p.add_argument("--output", help="Download path for the generated artifact")
    p.set_defaults(func=cmd_pipeline)

    args = parser.parse_args()

    try:
        args.func(args)
    except ImportError as e:
        _exit_error(
            f"notebooklm-py not installed: {e}. "
            "Run: pip install 'notebooklm-py[browser]' && notebooklm login"
        )
    except KeyboardInterrupt:
        _exit_error("Interrupted", code=130)
    except Exception as e:
        _exit_error(str(e))


if __name__ == "__main__":
    main()
