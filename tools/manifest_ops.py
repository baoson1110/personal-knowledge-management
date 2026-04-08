"""manifest_ops.py — Manifest operations library for personal wiki.

Provides functions to load, save, and query compile and file-back
manifests. Handles JSON validation, corruption recovery (backup + fresh
create), source/output status classification, and idempotency checks.

Uses only the Python standard library (no external dependencies).
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


# --- Constants ---

_EMPTY_COMPILE_MANIFEST: Dict = {"version": 1, "sources": {}}
_EMPTY_FILEBACK_MANIFEST: Dict = {"version": 1, "outputs": {}}


# --- Internal helpers ---


def _load_manifest(path: Path, empty_template: dict) -> dict:
    """Load a JSON manifest from *path*.

    - If the file does not exist, create and return a fresh manifest.
    - If the file contains invalid JSON, back it up as ``<name>.bak``
      and return a fresh manifest.
    - Validates that the top-level structure has a ``version`` key.
    """
    if not path.exists():
        save_path = path
        _save_manifest(save_path, empty_template)
        return _deep_copy(empty_template)

    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        _backup_corrupt(path)
        _save_manifest(path, empty_template)
        return _deep_copy(empty_template)

    if not isinstance(data, dict) or "version" not in data:
        _backup_corrupt(path)
        _save_manifest(path, empty_template)
        return _deep_copy(empty_template)

    return data


def _save_manifest(path: Path, data: dict) -> None:
    """Write *data* as pretty-printed JSON to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _backup_corrupt(path: Path) -> None:
    """Copy a corrupt manifest to ``<path>.bak`` before overwriting."""
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(str(path), str(bak))


def _deep_copy(d: dict) -> dict:
    """Return a deep copy of a simple JSON-compatible dict."""
    return json.loads(json.dumps(d))


def _file_mtime_epoch(filepath: str) -> float:
    """Return the mtime of *filepath* as a UTC epoch float."""
    return os.path.getmtime(filepath)


def _iso_to_epoch(iso_ts: str) -> float:
    """Parse an ISO 8601 timestamp string to a UTC epoch float.

    Handles both ``Z`` suffix and ``+00:00`` offset forms.
    """
    ts = iso_ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    return dt.timestamp()


# --- Compile manifest operations ---


def load_compile_manifest(path: Path) -> dict:
    """Load and validate the compile manifest at *path*.

    Returns a dict with ``version`` and ``sources`` keys.
    If the file is missing or corrupt, creates a fresh manifest
    (backing up the corrupt file as ``.bak`` if applicable).
    """
    manifest = _load_manifest(path, _EMPTY_COMPILE_MANIFEST)
    # Ensure the sources key exists
    if "sources" not in manifest:
        manifest["sources"] = {}
    return manifest


def save_compile_manifest(path: Path, manifest: dict) -> None:
    """Save the compile manifest *manifest* as JSON to *path*."""
    _save_manifest(path, manifest)


def classify_source(source_path: str, manifest: dict) -> str:
    """Classify a raw source file's status against the manifest.

    Returns one of:
    - ``"new"`` — not in manifest, or manifest status is ``"new"``,
      or ``compiled_at`` is missing/null.
    - ``"compiled"`` — in manifest with status ``"compiled"`` and the
      file has not been modified since ``compiled_at``.
    - ``"modified"`` — in manifest with status ``"compiled"`` but the
      file's mtime is later than ``compiled_at``.
    """
    sources = manifest.get("sources", {})
    entry = sources.get(source_path)

    if entry is None:
        return "new"

    status = entry.get("status", "new")
    if status != "compiled":
        return "new"

    compiled_at = entry.get("compiled_at")
    if not compiled_at:
        return "new"

    try:
        file_mtime = _file_mtime_epoch(source_path)
        compiled_epoch = _iso_to_epoch(compiled_at)
    except (OSError, ValueError):
        # If we can't read the file or parse the timestamp, treat as new
        return "new"

    if file_mtime > compiled_epoch:
        return "modified"

    return "compiled"


def is_compile_idempotent(source_path: str, manifest: dict) -> bool:
    """Return True if *source_path* is already compiled and unmodified.

    This is the skip-case: the source does not need recompilation.
    """
    return classify_source(source_path, manifest) == "compiled"


# --- File-back manifest operations ---


def load_fileback_manifest(path: Path) -> dict:
    """Load and validate the file-back manifest at *path*.

    Returns a dict with ``version`` and ``outputs`` keys.
    If the file is missing or corrupt, creates a fresh manifest
    (backing up the corrupt file as ``.bak`` if applicable).
    """
    manifest = _load_manifest(path, _EMPTY_FILEBACK_MANIFEST)
    # Ensure the outputs key exists
    if "outputs" not in manifest:
        manifest["outputs"] = {}
    return manifest


def save_fileback_manifest(path: Path, manifest: dict) -> None:
    """Save the file-back manifest *manifest* as JSON to *path*."""
    _save_manifest(path, manifest)


def classify_output(output_path: str, manifest: dict) -> str:
    """Classify an output file's file-back status against the manifest.

    Returns one of:
    - ``"pending"`` — not in manifest, or manifest status is
      ``"pending"`` or anything other than ``"filed"``.
    - ``"filed"`` — in manifest with status ``"filed"``.
    """
    outputs = manifest.get("outputs", {})
    entry = outputs.get(output_path)

    if entry is None:
        return "pending"

    status = entry.get("status", "pending")
    if status == "filed":
        return "filed"

    return "pending"


def is_fileback_idempotent(output_path: str, manifest: dict) -> bool:
    """Return True if *output_path* is already filed back.

    This is the skip-case: the output does not need to be filed again.
    """
    return classify_output(output_path, manifest) == "filed"
