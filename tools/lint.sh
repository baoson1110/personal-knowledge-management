#!/usr/bin/env bash
# lint.sh — Health-check the wiki for structural issues.
# Usage: tools/lint.sh [--help]
#
# Scans all markdown files in wiki/ and reports:
#   1. Broken [[...]] links (target file does not exist)
#   2. Orphan files (zero inbound links, excluding index.md)
#   3. Missing frontmatter fields (7 required fields)
#   4. Missing concepts (referenced via [[...]] but no file in wiki/concepts/)
#
# Outputs a structured report to stdout.
# Exit 0 on success (report IS the success), non-zero only on script errors.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WIKI_DIR="$REPO_ROOT/wiki"

# ── help ────────────────────────────────────────────────────────────
usage() {
  cat <<'EOF'
Usage: tools/lint.sh [--help]

Scan the wiki for structural issues and produce a health report.

Checks performed:
  1. Broken links     — [[...]] references where the target .md file
                        does not exist anywhere in wiki/
  2. Orphan files     — wiki files with zero inbound [[...]] links
                        (index.md is excluded)
  3. Missing fields   — wiki files missing any of the 7 required
                        frontmatter fields: title, domain, tags,
                        created, updated, source, confidence
  4. Missing concepts — [[...]] references where no matching file
                        exists in wiki/concepts/

Options:
  --help    Show this help message and exit

Exit codes:
  0  Success (report generated, even if issues found)
  1  Error (missing wiki/ directory, etc.)
EOF
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

# ── pre-flight checks ──────────────────────────────────────────────
if [[ ! -d "$WIKI_DIR" ]]; then
  echo "Error: wiki/ directory not found at $WIKI_DIR" >&2
  exit 1
fi

# ── temp files for portable lookups (no associative arrays needed) ──
TMPDIR_LINT=$(mktemp -d)
trap 'rm -rf "$TMPDIR_LINT"' EXIT

WIKI_FILES_LIST="$TMPDIR_LINT/wiki_files.txt"
SLUG_LIST="$TMPDIR_LINT/slugs.txt"
CONCEPT_SLUGS="$TMPDIR_LINT/concept_slugs.txt"
ALL_LINKS="$TMPDIR_LINT/all_links.txt"
BROKEN_LINKS="$TMPDIR_LINT/broken_links.txt"
ORPHAN_FILES="$TMPDIR_LINT/orphan_files.txt"
MISSING_FIELDS="$TMPDIR_LINT/missing_fields.txt"
MISSING_CONCEPTS="$TMPDIR_LINT/missing_concepts.txt"
INBOUND_TARGETS="$TMPDIR_LINT/inbound_targets.txt"

# Initialize output files
> "$BROKEN_LINKS"
> "$ORPHAN_FILES"
> "$MISSING_FIELDS"
> "$MISSING_CONCEPTS"
> "$ALL_LINKS"
> "$INBOUND_TARGETS"

# ── collect all wiki markdown files ─────────────────────────────────
find "$WIKI_DIR" -type f -name '*.md' ! -name '.gitkeep' | sort > "$WIKI_FILES_LIST"

file_count=$(wc -l < "$WIKI_FILES_LIST" | tr -d ' ')

if [[ "$file_count" -eq 0 ]]; then
  echo "No markdown files found in wiki/"
  echo ""
  echo "=== Wiki Lint Report ==="
  echo "Files scanned:    0"
  echo "Broken links:     0"
  echo "Orphan files:     0"
  echo "Missing fields:   0"
  echo "Missing concepts: 0"
  echo ""
  echo "Total issues: 0"
  exit 0
fi

# ── build slug lists ────────────────────────────────────────────────
# All wiki file slugs (filename without .md)
while IFS= read -r filepath; do
  basename "$filepath" .md
done < "$WIKI_FILES_LIST" | sort -u > "$SLUG_LIST"

# Concept slugs specifically
if [[ -d "$WIKI_DIR/concepts" ]]; then
  find "$WIKI_DIR/concepts" -type f -name '*.md' -exec basename {} .md \; \
    | sort -u > "$CONCEPT_SLUGS"
else
  > "$CONCEPT_SLUGS"
fi

# ── helper: extract [[...]] links from a file ──────────────────────
extract_links() {
  grep -oE '\[\[[^]]+\]\]' "$1" 2>/dev/null \
    | sed 's/\[\[//g; s/\]\]//g' \
    | sort -u
}

# ── helper: extract frontmatter field names from a file ────────────
extract_frontmatter_fields() {
  awk '
    BEGIN { in_fm=0; count=0 }
    /^---[[:space:]]*$/ {
      count++
      if (count == 1) { in_fm=1; next }
      if (count == 2) { exit }
    }
    in_fm && /^[a-zA-Z_][a-zA-Z0-9_-]*:/ {
      sub(/:.*/, "")
      print
    }
  ' "$1"
}

REQUIRED_FIELDS="title domain tags created updated source confidence"

# ── CHECK 1: Broken links ──────────────────────────────────────────
# ── CHECK 2 prep: Collect all inbound link targets ──────────────────
# ── CHECK 4 prep: Collect all referenced link slugs ─────────────────
while IFS= read -r filepath; do
  relpath="${filepath#"$REPO_ROOT"/}"
  links=$(extract_links "$filepath" || true)
  for link in $links; do
    [[ -z "$link" ]] && continue
    # Record inbound target for orphan detection
    echo "$link" >> "$INBOUND_TARGETS"
    # Check if slug exists in any wiki file
    if ! grep -qxF "$link" "$SLUG_LIST"; then
      echo "  $relpath -> [[$link]]" >> "$BROKEN_LINKS"
    fi
  done
done < "$WIKI_FILES_LIST"

# ── CHECK 2: Orphan files ──────────────────────────────────────────
while IFS= read -r filepath; do
  relpath="${filepath#"$REPO_ROOT"/}"
  base="$(basename "$filepath")"
  # Exclude index.md
  if [[ "$base" == "index.md" ]]; then
    continue
  fi
  slug="$(basename "$filepath" .md)"
  # Check if this slug appears in any inbound link
  if ! grep -qxF "$slug" "$INBOUND_TARGETS" 2>/dev/null; then
    echo "  $relpath" >> "$ORPHAN_FILES"
  fi
done < "$WIKI_FILES_LIST"

# ── CHECK 3: Missing frontmatter fields ────────────────────────────
while IFS= read -r filepath; do
  relpath="${filepath#"$REPO_ROOT"/}"
  present=$(extract_frontmatter_fields "$filepath")
  for req in $REQUIRED_FIELDS; do
    if ! echo "$present" | grep -qxF "$req"; then
      echo "  $relpath: missing '$req'" >> "$MISSING_FIELDS"
    fi
  done
done < "$WIKI_FILES_LIST"

# ── CHECK 4: Missing concepts ──────────────────────────────────────
# Find unique link targets that don't have a concept file
sort -u "$INBOUND_TARGETS" > "$TMPDIR_LINT/unique_targets.txt"
while IFS= read -r link; do
  [[ -z "$link" ]] && continue
  if ! grep -qxF "$link" "$CONCEPT_SLUGS" 2>/dev/null; then
    echo "  [[$link]] — no file in wiki/concepts/" >> "$MISSING_CONCEPTS"
  fi
done < "$TMPDIR_LINT/unique_targets.txt"

# ── Count issues ────────────────────────────────────────────────────
broken_count=$(wc -l < "$BROKEN_LINKS" | tr -d ' ')
orphan_count=$(wc -l < "$ORPHAN_FILES" | tr -d ' ')
fields_count=$(wc -l < "$MISSING_FIELDS" | tr -d ' ')
concepts_count=$(wc -l < "$MISSING_CONCEPTS" | tr -d ' ')
total_issues=$(( broken_count + orphan_count + fields_count + concepts_count ))

# ── Output structured report ────────────────────────────────────────
echo "=== Wiki Lint Report ==="
echo ""
echo "Files scanned: $file_count"
echo ""

echo "--- Broken Links ($broken_count) ---"
if [[ "$broken_count" -gt 0 ]]; then
  cat "$BROKEN_LINKS"
else
  echo "  (none)"
fi
echo ""

echo "--- Orphan Files ($orphan_count) ---"
if [[ "$orphan_count" -gt 0 ]]; then
  cat "$ORPHAN_FILES"
else
  echo "  (none)"
fi
echo ""

echo "--- Missing Frontmatter Fields ($fields_count) ---"
if [[ "$fields_count" -gt 0 ]]; then
  cat "$MISSING_FIELDS"
else
  echo "  (none)"
fi
echo ""

echo "--- Missing Concepts ($concepts_count) ---"
if [[ "$concepts_count" -gt 0 ]]; then
  cat "$MISSING_CONCEPTS"
else
  echo "  (none)"
fi
echo ""

echo "Total issues: $total_issues"

exit 0
