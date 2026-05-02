#!/usr/bin/env python3
"""scan_sources.py — Scan vault/staging/ and classify sources against the compile manifest.

Handles macOS Unicode normalization (NFD filesystem vs NFC manifest keys)
and non-breaking space mismatches. Uses manifest_ops for manifest loading.

Usage:
  python3 tools/scan_sources.py              # Human-readable table
  python3 tools/scan_sources.py --json       # Machine-readable JSON
  python3 tools/scan_sources.py --pending    # Only show new/modified sources
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "vault" / "staging"
MANIFEST_PATH = REPO_ROOT / "tools" / ".compile-manifest.json"

# Allow importing manifest_ops from the same directory
sys.path.insert(0, str(REPO_ROOT / "tools"))
from manifest_ops import load_compile_manifest, classify_source


# ── Unicode normalization helpers ────────────────────────────────────────────

def _normalize_key(s: str) -> str:
    """Normalize a string to NFC and replace non-breaking spaces with regular spaces.

    macOS HFS+/APFS stores filenames in NFD form, while JSON manifest keys
    are typically NFC. Non-breaking spaces (\\xa0) in filenames also cause
    mismatches against regular spaces in manifest keys.
    """
    normalized = unicodedata.normalize("NFC", s)
    normalized = normalized.replace("\xa0", " ")
    return normalized


def _build_normalization_map(manifest: dict) -> dict[str, str]:
    """Build a mapping from normalized manifest keys to original keys.

    Returns {normalized_key: original_key} for all sources in the manifest.
    """
    sources = manifest.get("sources", {})
    return {_normalize_key(k): k for k in sources}


# ── Scanning ─────────────────────────────────────────────────────────────────

SKIP_NAMES = {".gitkeep", ".DS_Store"}
SKIP_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def collect_raw_files() -> list[str]:
    """Collect all staging source files, returning paths relative to REPO_ROOT."""
    files: list[str] = []
    for p in sorted(RAW_DIR.rglob("*")):
        if not p.is_file():
            continue
        if p.name in SKIP_NAMES:
            continue
        if p.suffix.lower() in SKIP_SUFFIXES:
            continue
        files.append(str(p.relative_to(REPO_ROOT)))
    return files


def classify_with_normalization(
    file_path: str, manifest: dict, norm_map: dict[str, str]
) -> str:
    """Classify a source file, handling Unicode normalization mismatches.

    First tries the literal file path against the manifest. If not found,
    tries the NFC-normalized path to handle macOS NFD filenames and
    non-breaking space mismatches.

    When a normalized match is found, we check the manifest entry directly
    (bypassing mtime comparison on the original key, which has a different
    filename than the file on disk).
    """
    # Direct match — file_path exists as-is in the manifest
    status = classify_source(file_path, manifest)
    if status != "new":
        return status

    # Try normalized match
    norm_key = _normalize_key(file_path)
    original_key = norm_map.get(norm_key)
    if original_key is not None:
        # The manifest has this source under a different (NFC) key.
        # classify_source would try to stat the NFC key as a file path,
        # which doesn't exist on disk. Instead, check the manifest entry
        # directly and compare mtime using the actual disk path.
        sources = manifest.get("sources", {})
        entry = sources.get(original_key, {})
        entry_status = entry.get("status", "new")
        if entry_status != "compiled":
            return "new"
        compiled_at = entry.get("compiled_at")
        if not compiled_at:
            return "new"
        try:
            from manifest_ops import _file_mtime_epoch, _iso_to_epoch
            file_mtime = _file_mtime_epoch(file_path)
            compiled_epoch = _iso_to_epoch(compiled_at)
        except (OSError, ValueError):
            return "new"
        return "modified" if file_mtime > compiled_epoch else "compiled"

    return "new"


def scan_all() -> list[dict]:
    """Scan all staging sources and return classification results.

    Returns a list of dicts with keys: path, status, words.
    """
    manifest = load_compile_manifest(MANIFEST_PATH)
    norm_map = _build_normalization_map(manifest)
    raw_files = collect_raw_files()

    results: list[dict] = []
    for file_path in raw_files:
        full_path = REPO_ROOT / file_path
        try:
            content = full_path.read_text(encoding="utf-8")
            word_count = len(content.split())
        except (OSError, UnicodeDecodeError):
            word_count = 0

        status = classify_with_normalization(file_path, manifest, norm_map)
        results.append({
            "path": file_path,
            "status": status,
            "words": word_count,
        })

    return results


# ── Output ───────────────────────────────────────────────────────────────────

def print_table(results: list[dict], pending_only: bool = False) -> None:
    """Print a human-readable table of scan results."""
    if pending_only:
        results = [r for r in results if r["status"] != "compiled"]

    counts = {"new": 0, "compiled": 0, "modified": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    # Also count full totals for summary
    all_results = scan_all() if pending_only else results
    total_counts = {"new": 0, "compiled": 0, "modified": 0}
    for r in all_results:
        total_counts[r["status"]] = total_counts.get(r["status"], 0) + 1

    if not results:
        print("No pending sources found. All staging files are compiled.")
        print(f"\nTotal: {len(all_results)} source(s) — "
              f"{total_counts['compiled']} compiled, "
              f"{total_counts['new']} new, "
              f"{total_counts['modified']} modified")
        return

    print(f"{'FILE':<65} {'WORDS':>6}  STATUS")
    print(f"{'----':<65} {'-----':>6}  ------")

    for r in results:
        status_icon = {"new": "✗", "compiled": "✓", "modified": "~"}
        icon = status_icon.get(r["status"], "?")
        print(f"{r['path']:<65} {r['words']:>6}  {icon} {r['status']}")

    print(f"\nTotal: {len(all_results)} source(s) — "
          f"{total_counts['compiled']} compiled, "
          f"{total_counts['new']} new, "
          f"{total_counts['modified']} modified")


def print_json(results: list[dict], pending_only: bool = False) -> None:
    """Print machine-readable JSON output."""
    if pending_only:
        results = [r for r in results if r["status"] != "compiled"]

    output = {
        "total": len(results),
        "sources": results,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="scan_sources.py",
        description="Scan vault/staging/ sources and classify against the compile manifest.",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output results as JSON.",
    )
    parser.add_argument(
        "--pending", action="store_true",
        help="Only show new or modified sources (skip compiled).",
    )
    args = parser.parse_args()

    results = scan_all()

    if args.json_output:
        print_json(results, pending_only=args.pending)
    else:
        print_table(results, pending_only=args.pending)

    # Exit code: 0 if no pending, 1 if there are new/modified sources
    has_pending = any(r["status"] != "compiled" for r in results)
    return 1 if has_pending else 0


if __name__ == "__main__":
    sys.exit(main())
