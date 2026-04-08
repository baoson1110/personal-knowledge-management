#!/usr/bin/env bash
# promote.sh — Move files from staging/ to the corresponding raw/ subdirectory.
# Usage: tools/promote.sh [--help] [--all] [<staging-path>]
#
# Moves a file from staging/<subdir>/<filename> to raw/<subdir>/<filename>,
# preserving the subdirectory structure. Aborts if the target already exists.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STAGING_DIR="$REPO_ROOT/staging"
RAW_DIR="$REPO_ROOT/raw"

# ── help ────────────────────────────────────────────────────────────
usage() {
  cat <<'EOF'
Usage: tools/promote.sh [--help] [--all] [<staging-path>]

Move files from staging/ to the corresponding raw/ subdirectory.

Arguments:
  <staging-path>  Path to a file under staging/ (e.g. staging/articles/my-doc.md)

Options:
  --all     Move all files from staging/ to raw/ (excluding .gitkeep)
  --help    Show this help message and exit

Behavior:
  - Maps staging/<subdir>/<filename> to raw/<subdir>/<filename>
  - Aborts with an error if the target file already exists in raw/
  - With --all, aborts on the first conflict (no partial moves)

Exit codes:
  0  Success
  1  Error (missing directories, conflict, bad arguments, etc.)
EOF
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

# ── pre-flight checks ──────────────────────────────────────────────
if [[ ! -d "$STAGING_DIR" ]]; then
  echo "Error: staging/ directory not found at $STAGING_DIR" >&2
  exit 1
fi

if [[ ! -d "$RAW_DIR" ]]; then
  echo "Error: raw/ directory not found at $RAW_DIR" >&2
  exit 1
fi

# ── helper: promote a single file ──────────────────────────────────
promote_file() {
  local src="$1"

  # Ensure the file exists
  if [[ ! -f "$src" ]]; then
    echo "Error: file not found: $src" >&2
    return 1
  fi

  # Get path relative to repo root
  local relpath="${src#"$REPO_ROOT"/}"

  # Validate it's under staging/
  if [[ "$relpath" != staging/* ]]; then
    echo "Error: file is not under staging/: $relpath" >&2
    return 1
  fi

  # Map staging/... to raw/...
  local target_rel="raw/${relpath#staging/}"
  local target="$REPO_ROOT/$target_rel"

  # Check for conflict
  if [[ -f "$target" ]]; then
    echo "Error: target already exists: $target_rel (will not overwrite)" >&2
    return 1
  fi

  # Ensure target directory exists
  local target_dir
  target_dir="$(dirname "$target")"
  mkdir -p "$target_dir"

  # Move the file
  mv "$src" "$target"
  echo "Promoted: $relpath -> $target_rel"
}

# ── --all mode ──────────────────────────────────────────────────────
if [[ "${1:-}" == "--all" ]]; then
  FILES=()
  while IFS= read -r f; do
    FILES+=("$f")
  done < <(find "$STAGING_DIR" -type f ! -name '.gitkeep' | sort)

  if [[ ${#FILES[@]} -eq 0 ]]; then
    echo "No files to promote in staging/"
    exit 0
  fi

  # Pre-check all targets for conflicts before moving anything
  for filepath in "${FILES[@]}"; do
    relpath="${filepath#"$REPO_ROOT"/}"
    target_rel="raw/${relpath#staging/}"
    target="$REPO_ROOT/$target_rel"
    if [[ -f "$target" ]]; then
      echo "Error: target already exists: $target_rel (aborting --all)" >&2
      exit 1
    fi
  done

  # All clear — move everything
  for filepath in "${FILES[@]}"; do
    promote_file "$filepath"
  done

  echo ""
  echo "Promoted ${#FILES[@]} file(s)"
  exit 0
fi

# ── single file mode ───────────────────────────────────────────────
if [[ $# -eq 0 ]]; then
  echo "Error: no file specified. Use --help for usage." >&2
  exit 1
fi

# Resolve the argument to an absolute path
INPUT="$1"
if [[ "$INPUT" != /* ]]; then
  INPUT="$REPO_ROOT/$INPUT"
fi

promote_file "$INPUT"
exit 0
