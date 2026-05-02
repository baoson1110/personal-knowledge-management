#!/usr/bin/env bash
# scan.sh — List staging sources with word counts and compile status.
# Usage: tools/scan.sh [--help]
#
# Reads all files in vault/staging/ (excluding .gitkeep), shows each file's
# word count and compile status (new / compiled / modified).
# Status is determined by comparing against tools/.compile-manifest.json.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RAW_DIR="$REPO_ROOT/vault/staging"
MANIFEST="$SCRIPT_DIR/.compile-manifest.json"

# ── help ────────────────────────────────────────────────────────────
usage() {
  cat <<'EOF'
Usage: tools/scan.sh [--help]

Scan vault/staging/ sources and report compile status.

For each file in vault/staging/ (excluding .gitkeep):
  - file path (relative to repo root)
  - word count
  - status: new | compiled | modified

Status logic:
  new       — file is not in the compile manifest, or manifest status is "new"
  compiled  — manifest status is "compiled" and file has not changed since compiled_at
  modified  — manifest status is "compiled" but file was modified after compiled_at

Options:
  --help    Show this help message and exit

Exit codes:
  0  Success
  1  Error (missing directories, bad manifest, etc.)
EOF
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

# ── pre-flight checks ──────────────────────────────────────────────
if [[ ! -d "$RAW_DIR" ]]; then
  echo "Error: vault/staging/ directory not found at $RAW_DIR" >&2
  exit 1
fi

# If manifest is missing, create an empty one
if [[ ! -f "$MANIFEST" ]]; then
  echo '{"version": 1, "sources": {}}' > "$MANIFEST"
fi

# Validate manifest is valid JSON
if ! jq empty "$MANIFEST" 2>/dev/null; then
  echo "Error: $MANIFEST is not valid JSON" >&2
  exit 1
fi

# ── collect files ───────────────────────────────────────────────────
# Find all files in raw/ excluding .gitkeep, sorted
FILES=()
while IFS= read -r f; do
  FILES+=("$f")
done < <(find "$RAW_DIR" -type f ! -name '.gitkeep' | sort)

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "No source files found in vault/staging/"
  exit 0
fi

# ── helper: get file mtime as epoch seconds (portable) ──────────────
get_mtime_epoch() {
  local filepath="$1"
  if stat --version &>/dev/null; then
    # GNU/Linux stat
    stat -c '%Y' "$filepath"
  else
    # macOS/BSD stat
    stat -f '%m' "$filepath"
  fi
}

# ── helper: convert ISO timestamp to epoch (via python3) ────────────
iso_to_epoch() {
  local iso_ts="$1"
  python3 -c "import sys,datetime as d;print(int(d.datetime.fromisoformat(sys.argv[1].replace('Z','+00:00')).timestamp()))" "$iso_ts"
}

# ── classify and print ──────────────────────────────────────────────
printf "%-60s %8s  %s\n" "FILE" "WORDS" "STATUS"
printf "%-60s %8s  %s\n" "----" "-----" "------"

for filepath in "${FILES[@]}"; do
  # Make path relative to repo root
  relpath="${filepath#"$REPO_ROOT"/}"

  # Word count
  wc_count=$(wc -w < "$filepath" | tr -d ' ')

  # Look up in manifest
  manifest_status=$(jq -r --arg key "$relpath" '.sources[$key].status // "absent"' "$MANIFEST")
  compiled_at=$(jq -r --arg key "$relpath" '.sources[$key].compiled_at // "null"' "$MANIFEST")

  if [[ "$manifest_status" == "absent" || "$manifest_status" == "new" ]]; then
    status="new"
  elif [[ "$manifest_status" == "compiled" ]]; then
    if [[ "$compiled_at" == "null" || -z "$compiled_at" ]]; then
      status="new"
    else
      file_mtime=$(get_mtime_epoch "$filepath")
      compiled_epoch=$(iso_to_epoch "$compiled_at")
      if [[ "$file_mtime" -gt "$compiled_epoch" ]]; then
        status="modified"
      else
        status="compiled"
      fi
    fi
  else
    # Unknown status in manifest — treat as new
    status="new"
  fi

  printf "%-60s %8s  %s\n" "$relpath" "$wc_count" "$status"
done

echo ""
echo "Total: ${#FILES[@]} source(s)"
exit 0
