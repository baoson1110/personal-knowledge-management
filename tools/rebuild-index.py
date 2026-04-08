#!/usr/bin/env python3
"""rebuild-index.py — Regenerate wiki/index.md from all wiki files.

Walks wiki/concepts/, wiki/summaries/, wiki/topics/, wiki/domains/ and
parses YAML frontmatter from each .md file to extract the title and a
one-line summary.  Writes a fresh wiki/index.md with categorized links.

Uses only the Python standard library (no external dependencies).
"""

import argparse
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
WIKI_DIR = REPO_ROOT / "wiki"

CATEGORIES = [
    ("Concepts", "concepts"),
    ("Summaries", "summaries"),
    ("Topics", "topics"),
    ("Domains", "domains"),
]


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML frontmatter fields from markdown text.

    Handles simple key: value pairs (no nested YAML).  Returns a dict
    of string keys to string values.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def extract_summary(text: str) -> str:
    """Return the first non-empty paragraph after frontmatter as a one-liner.

    Skips the frontmatter block (between --- delimiters), then skips any
    blank lines and heading lines (starting with #).  Returns the first
    non-empty, non-heading line trimmed to a single line.
    """
    lines = text.splitlines()
    # Skip frontmatter
    in_fm = False
    start = 0
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_fm = True
            continue
        if in_fm:
            if line.strip() == "---":
                start = i + 1
                break
    # Find first non-empty, non-heading line after frontmatter
    for line in lines[start:]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def collect_entries(subdir: Path) -> list[tuple[str, str, str]]:
    """Collect (slug, title, summary) tuples from .md files in *subdir*.

    Skips files starting with _ or . and .gitkeep files.
    Returns entries sorted by slug.
    """
    entries: list[tuple[str, str, str]] = []
    if not subdir.is_dir():
        return entries
    for fpath in sorted(subdir.iterdir()):
        if not fpath.is_file():
            continue
        if fpath.name.startswith(("_", ".")) or fpath.suffix != ".md":
            continue
        try:
            content = fpath.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = parse_frontmatter(content)
        title = fm.get("title", fpath.stem)
        summary = extract_summary(content)
        slug = fpath.stem
        entries.append((slug, title, summary))
    return entries


def build_index() -> str:
    """Build the full wiki/index.md content."""
    today = date.today().isoformat()
    parts: list[str] = [
        "---",
        f'title: "Wiki Index"',
        f'updated: "{today}"',
        "---",
        "",
        "# Wiki Index",
    ]

    for heading, dirname in CATEGORIES:
        parts.append("")
        parts.append(f"## {heading}")
        entries = collect_entries(WIKI_DIR / dirname)
        if not entries:
            parts.append("")  # blank line for empty section
        for slug, _title, summary in entries:
            if summary:
                parts.append(f"- [[{slug}]] — {summary}")
            else:
                parts.append(f"- [[{slug}]]")

    parts.append("")  # trailing newline
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="rebuild-index.py",
        description="Regenerate wiki/index.md from all wiki files.",
    )
    parser.parse_args()

    try:
        index_content = build_index()
        index_path = WIKI_DIR / "index.md"
        index_path.write_text(index_content, encoding="utf-8")
        print(f"Rebuilt {index_path.relative_to(REPO_ROOT)}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
