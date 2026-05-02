#!/usr/bin/env bash
# file-back.sh — Manage file-back status for outputs.
# Usage: tools/file-back.sh [--help] [pending] [mark <output-path>]
#
# Reads tools/.fileback-manifest.json and lists outputs with their
# status (pending/filed). Supports marking outputs as filed and
# listing only pending outputs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUTS_DIR="$REPO_ROOT/vault/outputs"
MANIFEST="$SCRIPT_DIR/.fileback-manifest.json"

# ── help ────────────────────────────────────────────────────────────
usage() {
  cat <<'EOF'
Usage: tools/file-back.sh [--help] [pending] [mark <output-path>]

Manage file-back status for output files.

Subcommands:
  (none)              List ALL outputs with their status (pending/filed)
  pending             List only outputs with status "pending"
  mark <output-path>  Mark an output as "filed" in the manifest

Arguments:
  <output-path>  Path to an output file relative to repo root
                 (e.g. vault/outputs/reports/report-topic-2025-01-20.md)

Options:
  --help    Show this help message and exit

Status logic:
  pending  — output exists but is not in manifest, or manifest status is "pending"
  filed    — manifest status is "filed"

Exit codes:
  0  Success
  1  Error (missing directories, bad manifest, invalid arguments, etc.)
EOF
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

# ── pre-flight checks ──────────────────────────────────────────────
if [[ ! -d "$OUTPUTS_DIR" ]]; then
  echo "Error: vault/outputs/ directory not found at $OUTPUTS_DIR" >&2
  exit 1
fi

# If manifest is missing, create an empty one
if [[ ! -f "$MANIFEST" ]]; then
  echo '{"version": 1, "outputs": {}}' > "$MANIFEST"
fi

# Validate manifest is valid JSON
if ! jq empty "$MANIFEST" 2>/dev/null; then
  echo "Error: $MANIFEST is not valid JSON" >&2
  exit 1
fi

# ── helper: collect all output files ────────────────────────────────
collect_outputs() {
  find "$OUTPUTS_DIR" -type f -name '*.md' ! -name '.gitkeep' | sort
}

# ── helper: get status of an output from manifest ──────────────────
get_status() {
  local relpath="$1"
  jq -r --arg key "$relpath" '.outputs[$key].status // "pending"' "$MANIFEST"
}

# ── helper: get filed_at timestamp from manifest ───────────────────
get_filed_at() {
  local relpath="$1"
  jq -r --arg key "$relpath" '.outputs[$key].filed_at // ""' "$MANIFEST"
}

# ── helper: get created_at timestamp from manifest ─────────────────
get_created_at() {
  local relpath="$1"
  jq -r --arg key "$relpath" '.outputs[$key].created_at // ""' "$MANIFEST"
}

# ── subcommand: mark ────────────────────────────────────────────────
do_mark() {
  local output_path="$1"

  # Normalize to relative path from repo root
  if [[ "$output_path" == /* ]]; then
    output_path="${output_path#"$REPO_ROOT"/}"
  fi

  # Validate the output path starts with vault/outputs/
  if [[ "$output_path" != vault/outputs/* ]]; then
    echo "Error: path must be under vault/outputs/: $output_path" >&2
    return 1
  fi

  # Validate the file exists
  if [[ ! -f "$REPO_ROOT/$output_path" ]]; then
    echo "Error: file not found: $output_path" >&2
    return 1
  fi

  # Get current ISO timestamp
  local now
  now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  # Update manifest: set status to filed with timestamp
  local tmp
  tmp=$(mktemp)
  jq --arg key "$output_path" \
     --arg ts "$now" \
     '.outputs[$key] = {"status": "filed", "filed_at": $ts, "wiki_files_updated": []}' \
     "$MANIFEST" > "$tmp" && mv "$tmp" "$MANIFEST"

  echo "Marked as filed: $output_path (at $now)"
}

# ── subcommand: pending ─────────────────────────────────────────────
do_pending() {
  local found=0

  while IFS= read -r filepath; do
    [[ -z "$filepath" ]] && continue
    local relpath="${filepath#"$REPO_ROOT"/}"
    local status
    status=$(get_status "$relpath")

    if [[ "$status" == "pending" ]]; then
      local created_at
      created_at=$(get_created_at "$relpath")
      if [[ -n "$created_at" ]]; then
        echo "  $relpath  (created: $created_at)"
      else
        echo "  $relpath"
      fi
      found=$((found + 1))
    fi
  done < <(collect_outputs)

  if [[ "$found" -eq 0 ]]; then
    echo "No pending outputs"
  else
    echo ""
    echo "Pending: $found output(s)"
  fi
}

# ── subcommand: list (default) ──────────────────────────────────────
do_list() {
  local total=0

  printf "%-60s  %s\n" "OUTPUT" "STATUS"
  printf "%-60s  %s\n" "------" "------"

  while IFS= read -r filepath; do
    [[ -z "$filepath" ]] && continue
    local relpath="${filepath#"$REPO_ROOT"/}"
    local status
    status=$(get_status "$relpath")

    printf "%-60s  %s\n" "$relpath" "$status"
    total=$((total + 1))
  done < <(collect_outputs)

  # Also list manifest entries for files that may no longer exist on disk
  local manifest_keys
  manifest_keys=$(jq -r '.outputs | keys[]' "$MANIFEST" 2>/dev/null || true)
  for key in $manifest_keys; do
    if [[ ! -f "$REPO_ROOT/$key" ]]; then
      local status
      status=$(get_status "$key")
      printf "%-60s  %s (file missing)\n" "$key" "$status"
      total=$((total + 1))
    fi
  done

  echo ""
  echo "Total: $total output(s)"
}

# ── dispatch ────────────────────────────────────────────────────────
case "${1:-}" in
  pending)
    do_pending
    ;;
  mark)
    if [[ -z "${2:-}" ]]; then
      echo "Error: mark requires an output path. Usage: file-back.sh mark <output-path>" >&2
      exit 1
    fi
    do_mark "$2"
    ;;
  "")
    do_list
    ;;
  *)
    echo "Error: unknown subcommand '$1'. Use --help for usage." >&2
    exit 1
    ;;
esac

exit 0
