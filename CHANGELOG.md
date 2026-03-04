# Changelog

All notable changes to the YouTube Scrapper project are documented here.
Follows [Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`

- **MAJOR** — breaking changes (incompatible API or workflow changes)
- **MINOR** — new features, new commands, new artifact types (backwards-compatible)
- **PATCH** — bug fixes, prompt tweaks, doc updates, security fixes

---

## [0.3.0] — 2026-03-04

### Added
- `yt_pipeline.py` — end-to-end orchestrator: YouTube search → NotebookLM → Notion
- `CHANGELOG.md` and `VERSION` file for release tracking
- `.githooks/post-commit` — auto-push to GitHub on every commit
- `scripts/release.sh` — one-command versioned releases with tags

### Changed
- Action steps prompt made topic-agnostic (removed hardcoded "AI influencer" reference)
- Notion DB ID moved from hardcoded constant to `NOTION_DB_ID` env var
- `modules/storage.py` — removed hardcoded bucket name default and project name from docstring

### Security
- Removed private Notion DB ID from source code
- Hardened `.gitignore` — blocks `memory/`, `youtube automation/`, `settings.local.json`, credential patterns
- Author X handle added to README: [@varchar_dev](https://x.com/varchar_dev)

---

## [0.2.0] — 2026-03-04

### Added
- `notebooklm_runner.py` — full async CLI wrapper for NotebookLM automation
- `~/.claude/skills/notebooklm.md` — Claude Code skill for NotebookLM commands
- Artifact generation: audio, report, quiz, flashcards, infographic, mindmap, slide, video
- `batch-generate` and `pipeline` subcommands
- README.md with full documentation, cost estimation, use cases (30+ examples)
- `docs/pipeline.md` — architecture and data flow docs
- `docs/setup.md` — step-by-step install and Notion setup guide

### Fixed
- `notebooks.create(title=)` — was incorrectly using `name=`
- Removed non-existent `add_youtube()` — all sources use `add_url()`
- `sources.wait_for_sources()` — fixed incorrect `wait_until_ready()` signature

---

## [0.1.0] — 2026-03-04

### Added
- `yt_search.py` — YouTube metadata scraper (yt-dlp, no downloads)
- `~/.claude/skills/yt_search.md` — Claude Code skill for YouTube searches
- JSON, CSV, and table output formats
- Count clamped to 1–50 (yt-dlp reliable limit)
- Fields: title, channel, view_count, duration, upload_date, url

---

*Maintained by [Varchar Vibes](https://x.com/varchar_dev)*
