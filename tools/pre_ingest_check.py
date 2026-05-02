#!/usr/bin/env python3
"""pre_ingest_check.py — Pre-flight validation for a staging source before compilation.

Checks a single source file and reports go/no-go with actionable warnings:
  1. Compile status (new / compiled / modified — skip if already compiled)
  2. Unlocalized images (external URLs that need Local Images Plus)
  3. Deduplication search (existing wiki content covering similar topics)
  4. Domain context (existing concepts in the likely domain)

Usage:
  python3 tools/pre_ingest_check.py <source-path>
  python3 tools/pre_ingest_check.py vault/staging/articles/my-article.md
  python3 tools/pre_ingest_check.py --help
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from manifest_ops import load_compile_manifest, classify_source

MANIFEST_PATH = REPO_ROOT / "tools" / ".compile-manifest.json"
WIKI_DIR = REPO_ROOT / "vault" / "wiki"

_EXTERNAL_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(https?://[^)]+\)")
_ASSET_IMAGE_RE = re.compile(r"!\[\[asset/([^\]]+)\]\]")


# ── Checks ───────────────────────────────────────────────────────────────────

def check_compile_status(source_path: str) -> tuple[str, str]:
    """Return (status, message) for the source's compile state."""
    manifest = load_compile_manifest(MANIFEST_PATH)
    status = classify_source(source_path, manifest)
    if status == "compiled":
        return "SKIP", f"Already compiled — no changes detected."
    elif status == "modified":
        return "WARN", f"Previously compiled but modified since. Will recompile."
    else:
        return "OK", "New source — ready for compilation."


def check_unlocalized_images(source_path: str) -> tuple[str, list[str]]:
    """Check for external image URLs not yet localized to asset/.

    Returns (status, details) where details is a list of warning strings.
    """
    full_path = REPO_ROOT / source_path
    try:
        content = full_path.read_text(encoding="utf-8")
    except OSError:
        return "ERROR", [f"Cannot read file: {source_path}"]

    # Strip code blocks
    no_code = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    no_code = re.sub(r"`[^`]+`", "", no_code)

    external = _EXTERNAL_IMAGE_RE.findall(no_code)
    local = _ASSET_IMAGE_RE.findall(no_code)

    if external:
        return "BLOCK", [
            f"{len(external)} external image URL(s) found — run Local Images Plus in Obsidian first.",
            f"{len(local)} image(s) already localized to asset/.",
            "External URLs will not render in wiki pages.",
        ]
    elif local:
        return "OK", [f"{len(local)} localized image(s) found in asset/."]
    else:
        return "OK", ["No images in source (text-only article)."]


def check_deduplication(source_path: str) -> tuple[str, list[str]]:
    """Search existing wiki for content that may overlap with this source.

    Uses the source's title and first ~200 words to find potential duplicates.
    """
    full_path = REPO_ROOT / source_path
    try:
        content = full_path.read_text(encoding="utf-8")
    except OSError:
        return "ERROR", [f"Cannot read file: {source_path}"]

    # Extract title from frontmatter
    title = ""
    lines = content.splitlines()
    in_fm = False
    for line in lines:
        if line.strip() == "---":
            if not in_fm:
                in_fm = True
                continue
            else:
                break
        if in_fm and line.startswith("title:"):
            title = line.partition(":")[2].strip().strip('"').strip("'")

    if not title:
        return "WARN", ["No title found in frontmatter — cannot run dedup search."]

    # Run search.py as a subprocess to find overlapping content
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "search.py"), title],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT),
        )
        output = result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return "WARN", ["Search timed out or failed — manual dedup check recommended."]

    if not output or "No results" in output:
        return "OK", [f"No existing wiki content matches '{title}'."]

    # Parse top results
    matches = []
    for line in output.splitlines():
        line = line.strip()
        if line and line[0].isdigit() and "]" in line:
            # Extract score and path
            matches.append(line)
        elif line.startswith("Title:") or line.startswith("Snippet:"):
            matches.append(f"  {line}")

    if matches:
        return "WARN", [
            f"Potential overlaps found for '{title}':",
            *matches[:15],  # Top 5 results (3 lines each)
            "",
            "Review these before creating new concepts — update existing ones if overlap is strong.",
        ]
    return "OK", [f"No strong overlaps found for '{title}'."]


def check_domain_context(source_path: str) -> tuple[str, list[str]]:
    """Report existing concepts in domains likely relevant to this source.

    Reads the source's tags to guess the domain, then lists existing concepts.
    """
    full_path = REPO_ROOT / source_path
    try:
        content = full_path.read_text(encoding="utf-8")
    except OSError:
        return "ERROR", [f"Cannot read file: {source_path}"]

    # Extract tags from frontmatter
    tags: list[str] = []
    lines = content.splitlines()
    in_fm = False
    for line in lines:
        if line.strip() == "---":
            if not in_fm:
                in_fm = True
                continue
            else:
                break
        if in_fm and line.strip().startswith("tags:"):
            val = line.partition(":")[2].strip()
            if val.startswith("[") and val.endswith("]"):
                tags = [t.strip().strip('"').strip("'") for t in val[1:-1].split(",") if t.strip()]

    # Load tag registry to map tags → domains
    from wiki_validator import load_tag_registry
    try:
        canonical_map, alias_map = load_tag_registry()
    except FileNotFoundError:
        return "WARN", ["Tag registry not found — cannot determine domain context."]

    # Find likely domains from source tags
    domains: set[str] = set()
    for tag in tags:
        canonical = tag
        if tag in alias_map:
            canonical = alias_map[tag]
        if canonical in canonical_map:
            domain = canonical_map[canonical].get("domain", "")
            if domain:
                domains.add(domain)

    if not domains:
        return "OK", ["No domain tags detected in source — domain context unavailable."]

    # Count existing concepts per detected domain
    details: list[str] = []
    concepts_dir = WIKI_DIR / "concepts"
    if not concepts_dir.is_dir():
        return "OK", [f"Likely domains: {', '.join(sorted(domains))}. No concepts directory found."]

    from wiki_validator import parse_frontmatter as parse_fm
    for domain in sorted(domains):
        domain_concepts: list[str] = []
        for fpath in concepts_dir.iterdir():
            if not fpath.is_file() or fpath.suffix != ".md":
                continue
            try:
                fm = parse_fm(fpath.read_text(encoding="utf-8"))
            except OSError:
                continue
            if fm.get("domain") == domain:
                domain_concepts.append(fpath.stem)

        # Check if domain MOC exists
        moc_path = WIKI_DIR / "domains" / f"{domain}.md"
        moc_status = "MOC exists" if moc_path.is_file() else f"no MOC ({len(domain_concepts)}/5 threshold)"

        details.append(f"  {domain}: {len(domain_concepts)} concepts ({moc_status})")
        if domain_concepts:
            for slug in sorted(domain_concepts)[:10]:
                details.append(f"    - {slug}")
            if len(domain_concepts) > 10:
                details.append(f"    ... and {len(domain_concepts) - 10} more")

    return "OK", [f"Likely domains from source tags:", *details]


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="pre_ingest_check.py",
        description="Pre-flight validation for a staging source before compilation.",
    )
    parser.add_argument(
        "source", nargs="?",
        help="Path to a staging source file (e.g. vault/staging/articles/my-article.md)",
    )
    args = parser.parse_args()

    if not args.source:
        parser.print_help()
        return 1

    source_path = args.source
    full_path = REPO_ROOT / source_path

    # Basic validation
    if not full_path.is_file():
        print(f"ERROR: File not found: {source_path}")
        return 1
    if not source_path.startswith("vault/staging/"):
        print(f"ERROR: File is not under vault/staging/: {source_path}")
        return 1

    print(f"{'=' * 60}")
    print(f"  PRE-INGEST CHECK: {source_path}")
    print(f"{'=' * 60}")

    all_ok = True
    blocked = False

    # 1. Compile status
    print(f"\n── Check 1: Compile Status ──")
    status, msg = check_compile_status(source_path)
    icon = {"OK": "✓", "WARN": "⚠", "SKIP": "⏭", "ERROR": "✗", "BLOCK": "🚫"}
    print(f"  {icon.get(status, '?')} [{status}] {msg}")
    if status == "SKIP":
        print(f"\n{'=' * 60}")
        print(f"  RESULT: SKIP — source already compiled, no changes detected.")
        print(f"{'=' * 60}")
        return 0

    # 2. Unlocalized images
    print(f"\n── Check 2: Image Localization ──")
    status, details = check_unlocalized_images(source_path)
    for d in details:
        print(f"  {icon.get(status, '?')} [{status}] {d}")
    if status == "BLOCK":
        blocked = True
    if status not in ("OK",):
        all_ok = False

    # 3. Deduplication
    print(f"\n── Check 3: Deduplication Search ──")
    status, details = check_deduplication(source_path)
    for d in details:
        print(f"  {icon.get(status, '?')} [{status}] {d}")
    if status not in ("OK",):
        all_ok = False

    # 4. Domain context
    print(f"\n── Check 4: Domain Context ──")
    status, details = check_domain_context(source_path)
    for d in details:
        print(f"  {icon.get(status, '?')} {d}")

    # Final verdict
    print(f"\n{'=' * 60}")
    if blocked:
        print(f"  RESULT: 🚫 BLOCKED — fix blocking issues before compilation.")
        print(f"{'=' * 60}")
        return 1
    elif all_ok:
        print(f"  RESULT: ✓ GO — source is ready for compilation.")
        print(f"{'=' * 60}")
        return 0
    else:
        print(f"  RESULT: ⚠ GO WITH WARNINGS — review warnings before compilation.")
        print(f"{'=' * 60}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
