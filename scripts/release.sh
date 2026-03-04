#!/bin/bash
# release.sh — Bump version, update CHANGELOG, tag, and push.
#
# Usage:
#   ./scripts/release.sh patch "Fix NLM auth timeout"
#   ./scripts/release.sh minor "Add batch download command"
#   ./scripts/release.sh major "Breaking: new pipeline API"
#
# What it does:
#   1. Reads current version from VERSION file
#   2. Bumps patch / minor / major
#   3. Prepends a new entry to CHANGELOG.md
#   4. Commits VERSION + CHANGELOG
#   5. Creates a git tag (e.g. v0.4.0)
#   6. Pushes commit + tag to GitHub

set -e

BUMP="${1:-patch}"
DESCRIPTION="${2:-}"
DATE=$(date +%Y-%m-%d)

if [[ -z "$DESCRIPTION" ]]; then
  echo "Usage: ./scripts/release.sh <patch|minor|major> \"Description of changes\""
  exit 1
fi

# ── Read current version ──────────────────────────────────────────────────────
VERSION_FILE="VERSION"
if [[ ! -f "$VERSION_FILE" ]]; then
  echo "0.0.0" > "$VERSION_FILE"
fi

CURRENT=$(cat "$VERSION_FILE" | tr -d '[:space:]')
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

# ── Bump ──────────────────────────────────────────────────────────────────────
case "$BUMP" in
  major)
    MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor)
    MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch)
    PATCH=$((PATCH + 1)) ;;
  *)
    echo "Error: bump type must be patch, minor, or major"; exit 1 ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
TAG="v$NEW_VERSION"

echo "Bumping $CURRENT → $NEW_VERSION ($BUMP)"

# ── Update VERSION ────────────────────────────────────────────────────────────
echo "$NEW_VERSION" > "$VERSION_FILE"

# ── Collect commits since last tag ───────────────────────────────────────────
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
if [[ -n "$LAST_TAG" ]]; then
  COMMITS=$(git log "$LAST_TAG"..HEAD --oneline --no-decorate 2>/dev/null || echo "")
else
  COMMITS=$(git log --oneline --no-decorate -20 2>/dev/null || echo "")
fi

# ── Build changelog entry ─────────────────────────────────────────────────────
ENTRY="## [$NEW_VERSION] — $DATE\n\n$DESCRIPTION\n"
if [[ -n "$COMMITS" ]]; then
  ENTRY="$ENTRY\n### Commits\n"
  while IFS= read -r line; do
    ENTRY="$ENTRY- $line\n"
  done <<< "$COMMITS"
fi
ENTRY="$ENTRY\n---\n"

# ── Prepend to CHANGELOG.md ───────────────────────────────────────────────────
CHANGELOG="CHANGELOG.md"
if [[ -f "$CHANGELOG" ]]; then
  # Insert after the header block (first --- separator)
  HEADER=$(awk '/^---$/{count++; if(count==1){print; exit}} {print}' "$CHANGELOG")
  BODY=$(awk '/^---$/{count++} count>=1{print}' "$CHANGELOG" | tail -n +2)
  printf "%s\n\n%b%s" "$HEADER" "$ENTRY" "$BODY" > "$CHANGELOG"
else
  printf "# Changelog\n\n---\n\n%b" "$ENTRY" > "$CHANGELOG"
fi

# ── Commit + tag + push ───────────────────────────────────────────────────────
git add VERSION CHANGELOG.md
git commit -m "release: $TAG — $DESCRIPTION

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

git tag -a "$TAG" -m "$DESCRIPTION"
git push origin HEAD
git push origin "$TAG"

echo ""
echo "✓ Released $TAG — https://github.com/VarcharVibes/youtube-scrapper/releases/tag/$TAG"
