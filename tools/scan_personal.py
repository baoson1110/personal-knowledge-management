#!/usr/bin/env python3
"""scan_personal.py — Scan personal/inbox/ and classify against the personal manifest.

Tracks which inbox items have been consolidated (inbox → notes) and which
notes have been included in a synthesis (notes → synthesis).

Usage:
  python3 tools/scan_personal.py                    # Human-readable table
  python3 tools/scan_personal.py --json              # Machine-readable JSON
  python3 tools/scan_personal.py --pending           # Only unconsolidated/modified inbox items
  python3 tools/scan_personal.py --phase synthesis   # Check notes → synthesis status
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = REPO_ROOT / "personal" / "inbox"
NOTES_DIR = REPO_ROOT / "personal" / "notes"
MANIFEST_PATH = REPO_ROOT / "tools" / ".personal-manifest.json"

SKIP_NAMES = {".gitkeep", ".DS_Store"}

# ── Manifest helpers ─────────────────────────────────────────────────────────

_EMPTY_MANIFEST = {
    "version": 1,
    "inbox": {},
    "notes": {},
}


def _normalize_key(s: str) -> str:
    normalized = unicodedata.normalize("NFC", s)
    return normalized.replace("\xa0", " ")


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        _save_manifest(_EMPTY_MANIFEST)
        return json.loads(json.dumps(_EMPTY_MANIFEST))
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "version" not in data:
            raise ValueError
        data.setdefault("inbox", {})
        data.setdefault("notes", {})
        return data
    except (json.JSONDecodeError, ValueError):
        _save_manifest(_EMPTY_MANIFEST)
        return json.loads(json.dumps(_EMPTY_MANIFEST))


def _save_manifest(data: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _file_mtime_epoch(filepath: str) -> float:
    return (REPO_ROOT / filepath).stat().st_mtime


def _iso_to_epoch(iso_ts: str) -> float:
    ts = iso_ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts).timestamp()


# ── Classification ───────────────────────────────────────────────────────────

def classify_inbox_item(item_path: str, manifest: dict) -> str:
    """Classify an inbox item's consolidation status.

    Returns: 'new', 'consolidated', or 'modified'.
    """
    entries = manifest.get("inbox", {})
    norm = _normalize_key(item_path)

    entry = entries.get(item_path) or entries.get(norm)
    if entry is None:
        return "new"

    status = entry.get("status", "new")
    if status != "consolidated":
        return "new"

    consolidated_at = entry.get("consolidated_at")
    if not consolidated_at:
        return "new"

    try:
        file_mtime = _file_mtime_epoch(item_path)
        ts_epoch = _iso_to_epoch(consolidated_at)
    except (OSError, ValueError):
        return "new"

    return "modified" if file_mtime > ts_epoch else "consolidated"


def classify_note(note_path: str, manifest: dict) -> str:
    """Classify a note's synthesis status.

    Returns: 'new', 'synthesized', or 'modified'.
    """
    entries = manifest.get("notes", {})
    norm = _normalize_key(note_path)

    entry = entries.get(note_path) or entries.get(norm)
    if entry is None:
        return "new"

    status = entry.get("status", "new")
    if status != "synthesized":
        return "new"

    synthesized_at = entry.get("synthesized_at")
    if not synthesized_at:
        return "new"

    try:
        file_mtime = _file_mtime_epoch(note_path)
        ts_epoch = _iso_to_epoch(synthesized_at)
    except (OSError, ValueError):
        return "new"

    return "modified" if file_mtime > ts_epoch else "synthesized"


# ── Scanning ─────────────────────────────────────────────────────────────────

def collect_files(directory: Path) -> list[str]:
    """Collect all .md files in directory, returning paths relative to REPO_ROOT."""
    files: list[str] = []
    if not directory.exists():
        return files
    for p in sorted(directory.rglob("*.md")):
        if p.name in SKIP_NAMES:
            continue
        files.append(str(p.relative_to(REPO_ROOT)))
    return files


def scan_inbox() -> list[dict]:
    manifest = _load_manifest()
    results = []
    for fp in collect_files(INBOX_DIR):
        full = REPO_ROOT / fp
        try:
            words = len(full.read_text(encoding="utf-8").split())
        except (OSError, UnicodeDecodeError):
            words = 0
        status = classify_inbox_item(fp, manifest)
        entry = manifest.get("inbox", {}).get(fp, {})
        results.append({
            "path": fp,
            "status": status,
            "words": words,
            "note": entry.get("note_file"),
        })
    return results


def scan_notes() -> list[dict]:
    manifest = _load_manifest()
    results = []
    for fp in collect_files(NOTES_DIR):
        full = REPO_ROOT / fp
        try:
            words = len(full.read_text(encoding="utf-8").split())
        except (OSError, UnicodeDecodeError):
            words = 0
        status = classify_note(fp, manifest)
        entry = manifest.get("notes", {}).get(fp, {})
        results.append({
            "path": fp,
            "status": status,
            "words": words,
            "synthesis": entry.get("synthesis_file"),
        })
    return results


# ── Output ───────────────────────────────────────────────────────────────────

STATUS_ICONS = {
    "new": "✗", "consolidated": "✓", "modified": "~",
    "synthesized": "✓",
}


def print_table(results: list[dict], pending_only: bool, phase: str) -> None:
    if pending_only:
        done = "consolidated" if phase == "consolidation" else "synthesized"
        results = [r for r in results if r["status"] != done]

    if not results:
        print(f"No pending items for {phase}. Everything is up to date.")
        return

    print(f"{'FILE':<60} {'WORDS':>6}  STATUS")
    print(f"{'----':<60} {'-----':>6}  ------")
    for r in results:
        icon = STATUS_ICONS.get(r["status"], "?")
        print(f"{r['path']:<60} {r['words']:>6}  {icon} {r['status']}")

    done_key = "consolidated" if phase == "consolidation" else "synthesized"
    counts = {"new": 0, done_key: 0, "modified": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"\nTotal: {len(results)} — "
          + ", ".join(f"{v} {k}" for k, v in counts.items() if v > 0))


def print_json(results: list[dict], pending_only: bool, phase: str) -> None:
    done = "consolidated" if phase == "consolidation" else "synthesized"
    if pending_only:
        results = [r for r in results if r["status"] != done]
    print(json.dumps({"phase": phase, "total": len(results),
                       "items": results}, indent=2, ensure_ascii=False))


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan personal inbox/notes against the personal manifest.",
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--pending", action="store_true")
    parser.add_argument(
        "--phase", choices=["consolidation", "synthesis"], default="consolidation",
        help="Which phase to scan: consolidation (inbox→notes) or synthesis (notes→synthesis).",
    )
    args = parser.parse_args()

    if args.phase == "consolidation":
        results = scan_inbox()
    else:
        results = scan_notes()

    if args.json_output:
        print_json(results, args.pending, args.phase)
    else:
        print_table(results, args.pending, args.phase)

    done = "consolidated" if args.phase == "consolidation" else "synthesized"
    has_pending = any(r["status"] != done for r in results)
    return 1 if has_pending else 0


if __name__ == "__main__":
    sys.exit(main())
