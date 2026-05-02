#!/usr/bin/env python3
"""post_ingest_check.py — Post-compilation validation for a staging source.

Validates that all wiki files created from a source are correct:
  1. Manifest updated (source has compiled entry with wiki_files)
  2. All wiki_files exist on disk
  3. Frontmatter valid (7 required fields, valid confidence, tags in registry)
  4. Concept files ≤ 150 lines
  5. Summary files have 4 required sections
  6. Image coverage (summary has images if source has images)
  7. No broken links from new files
  8. Index completeness (new files appear in index.md)
  9. Domain MOC status (threshold check)

Usage:
  python3 tools/post_ingest_check.py <source-path>
  python3 tools/post_ingest_check.py vault/staging/articles/my-article.md
  python3 tools/post_ingest_check.py --all          # check all compiled sources
  python3 tools/post_ingest_check.py --help
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from manifest_ops import load_compile_manifest
from wiki_validator import (
    parse_frontmatter,
    validate_frontmatter,
    validate_wiki_filename,
    validate_concept_length,
    validate_summary_sections,
    extract_backlinks,
    load_tag_registry,
    validate_tags,
)

MANIFEST_PATH = REPO_ROOT / "tools" / ".compile-manifest.json"
WIKI_DIR = REPO_ROOT / "vault" / "wiki"
INDEX_PATH = WIKI_DIR / "index.md"
CONCEPT_MAX_LINES = 150

_ASSET_IMAGE_RE = re.compile(r"!\[\[asset/([^\]]+)\]\]")
_EXTERNAL_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(https?://[^)]+\)")
_BACKLINK_RE = re.compile(r"\[\[([a-zA-Z0-9_-]+)\]\]")

WIKI_SUBDIRS = ["concepts", "summaries", "topics", "domains", "reference"]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _count_asset_images(text: str) -> int:
    no_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    no_code = re.sub(r"`[^`]+`", "", no_code)
    return len(_ASSET_IMAGE_RE.findall(no_code))


def _load_all_wiki_slugs() -> set[str]:
    slugs: set[str] = set()
    for subdir in WIKI_SUBDIRS:
        dirpath = WIKI_DIR / subdir
        if not dirpath.is_dir():
            continue
        for fpath in dirpath.iterdir():
            if fpath.is_file() and fpath.suffix == ".md" and not fpath.name.startswith("."):
                slugs.add(fpath.stem)
    return slugs


def _load_index_backlinks() -> set[str]:
    if not INDEX_PATH.exists():
        return set()
    content = INDEX_PATH.read_text(encoding="utf-8")
    no_code = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    no_code = re.sub(r"`[^`]+`", "", no_code)
    return set(_BACKLINK_RE.findall(no_code))


# ── Check functions ──────────────────────────────────────────────────────────

class CheckResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.messages: list[tuple[str, str]] = []  # (level, message)

    def ok(self, msg: str):
        self.messages.append(("OK", msg))

    def warn(self, msg: str):
        self.messages.append(("WARN", msg))

    def fail(self, msg: str):
        self.passed = False
        self.messages.append(("FAIL", msg))

    def info(self, msg: str):
        self.messages.append(("INFO", msg))


def check_manifest(source_path: str) -> tuple[CheckResult, list[str]]:
    """Check that the manifest has a compiled entry for this source.

    Returns (result, wiki_files) where wiki_files is the list from the manifest.
    """
    r = CheckResult("Manifest Entry")
    manifest = load_compile_manifest(MANIFEST_PATH)
    sources = manifest.get("sources", {})
    entry = sources.get(source_path)

    if entry is None:
        r.fail(f"Source not found in compile manifest: {source_path}")
        return r, []

    status = entry.get("status", "")
    if status != "compiled":
        r.fail(f"Manifest status is '{status}', expected 'compiled'.")
        return r, []

    compiled_at = entry.get("compiled_at", "")
    if not compiled_at:
        r.fail("Missing 'compiled_at' timestamp in manifest entry.")
        return r, []

    key_insight = entry.get("key_insight", "")
    if not key_insight:
        r.warn("Missing 'key_insight' in manifest entry.")

    wiki_files = entry.get("wiki_files", [])
    if not wiki_files:
        r.fail("No 'wiki_files' listed in manifest entry.")
        return r, []

    r.ok(f"Compiled at {compiled_at}, {len(wiki_files)} wiki file(s) listed.")
    return r, wiki_files


def check_files_exist(wiki_files: list[str]) -> CheckResult:
    """Check that all wiki_files from the manifest exist on disk."""
    r = CheckResult("Files Exist")
    for wf in wiki_files:
        full = REPO_ROOT / wf
        if full.is_file():
            r.ok(f"  {wf}")
        else:
            r.fail(f"  MISSING: {wf}")
    return r


def check_frontmatter_valid(wiki_files: list[str]) -> CheckResult:
    """Validate frontmatter on all wiki files from this ingest."""
    r = CheckResult("Frontmatter")

    try:
        canonical_map, alias_map = load_tag_registry()
        registry_loaded = True
    except FileNotFoundError:
        registry_loaded = False
        r.warn("Tag registry not found — skipping tag validation.")

    for wf in wiki_files:
        full = REPO_ROOT / wf
        if not full.is_file():
            continue
        content = full.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        errors = validate_frontmatter(fm)

        if errors:
            for e in errors:
                r.fail(f"  {wf}: {e}")
        else:
            r.ok(f"  {wf}: all 7 fields valid")

        # Tag validation
        if registry_loaded:
            tags = fm.get("tags", [])
            if isinstance(tags, list):
                unreg, alias_hits = validate_tags(tags, canonical_map, alias_map)
                for tag in unreg:
                    r.fail(f"  {wf}: unregistered tag '{tag}'")
                for alias, canonical in alias_hits:
                    r.warn(f"  {wf}: alias '{alias}' should be '{canonical}'")

        # Filename validation
        filename = Path(wf).name
        if not validate_wiki_filename(filename):
            r.warn(f"  {wf}: filename doesn't match slug pattern [a-z0-9]+(-[a-z0-9]+)*.md")

    return r


def check_concept_length(wiki_files: list[str]) -> CheckResult:
    """Check that concept files are ≤ 150 lines."""
    r = CheckResult("Concept Length")
    concepts = [wf for wf in wiki_files if "/concepts/" in wf]
    if not concepts:
        r.ok("No concept files in this ingest.")
        return r

    for wf in concepts:
        full = REPO_ROOT / wf
        if not full.is_file():
            continue
        content = full.read_text(encoding="utf-8")
        line_count = len(content.splitlines())
        if line_count <= CONCEPT_MAX_LINES:
            r.ok(f"  {wf}: {line_count} lines (≤{CONCEPT_MAX_LINES})")
        else:
            r.fail(f"  {wf}: {line_count} lines (>{CONCEPT_MAX_LINES} limit)")
    return r


def check_summary_sections(wiki_files: list[str]) -> CheckResult:
    """Check that summary files have all 4 required sections."""
    r = CheckResult("Summary Sections")
    summaries = [wf for wf in wiki_files if "/summaries/" in wf]
    if not summaries:
        r.ok("No summary files in this ingest.")
        return r

    for wf in summaries:
        full = REPO_ROOT / wf
        if not full.is_file():
            continue
        content = full.read_text(encoding="utf-8")
        missing = validate_summary_sections(content)
        if missing:
            r.fail(f"  {wf}: missing sections: {', '.join(missing)}")
        else:
            r.ok(f"  {wf}: all 4 sections present")
    return r


def check_image_coverage(source_path: str, wiki_files: list[str]) -> CheckResult:
    """Check that wiki files include images when the source has them."""
    r = CheckResult("Image Coverage")

    source_full = REPO_ROOT / source_path
    if not source_full.is_file():
        r.warn("Cannot read source file for image check.")
        return r

    source_content = source_full.read_text(encoding="utf-8")
    source_images = _count_asset_images(source_content)

    # Also check for external images still present
    no_code = re.sub(r"```.*?```", "", source_content, flags=re.DOTALL)
    no_code = re.sub(r"`[^`]+`", "", no_code)
    external_count = len(_EXTERNAL_IMAGE_RE.findall(no_code))

    if external_count > 0:
        r.warn(f"Source still has {external_count} external image URL(s) — some images may be missing.")

    if source_images == 0 and external_count == 0:
        r.ok("Source has no images — no image coverage expected.")
        return r

    r.info(f"Source has {source_images} localized + {external_count} external image(s).")

    for wf in wiki_files:
        full = REPO_ROOT / wf
        if not full.is_file():
            continue
        content = full.read_text(encoding="utf-8")
        wiki_images = _count_asset_images(content)

        if "/summaries/" in wf:
            if source_images > 0 and wiki_images == 0:
                r.fail(f"  {wf}: 0 images (source has {source_images}) — summaries MUST include key diagrams")
            elif source_images > 0:
                pct = round(wiki_images / source_images * 100)
                if pct < 50:
                    r.warn(f"  {wf}: {wiki_images}/{source_images} images ({pct}%) — consider adding more")
                else:
                    r.ok(f"  {wf}: {wiki_images}/{source_images} images ({pct}%)")
            else:
                r.ok(f"  {wf}: {wiki_images} images")
        elif "/concepts/" in wf:
            r.ok(f"  {wf}: {wiki_images} images (max 5 recommended)")

    return r


def check_broken_links(wiki_files: list[str]) -> CheckResult:
    """Check for broken [[backlinks]] in the new wiki files.

    Excludes image embeds (![[asset/...]]) which are not wiki backlinks.
    """
    r = CheckResult("Broken Links")
    all_slugs = _load_all_wiki_slugs()

    for wf in wiki_files:
        full = REPO_ROOT / wf
        if not full.is_file():
            continue
        content = full.read_text(encoding="utf-8")

        # Extract backlinks but exclude image embeds (![[asset/...]])
        # Remove image embeds first, then extract backlinks
        no_images = re.sub(r"!\[\[asset/[^\]]+\]\]", "", content)
        links = extract_backlinks(no_images)

        broken = [link for link in links if link not in all_slugs]
        if broken:
            for b in broken:
                r.fail(f"  {wf}: broken link [[{b}]]")
        else:
            r.ok(f"  {wf}: all {len(links)} links resolve")
    return r


def check_index_completeness(wiki_files: list[str]) -> CheckResult:
    """Check that new wiki files appear in index.md."""
    r = CheckResult("Index Completeness")
    index_slugs = _load_index_backlinks()

    for wf in wiki_files:
        slug = Path(wf).stem
        if slug in index_slugs:
            r.ok(f"  [[{slug}]] found in index.md")
        else:
            r.fail(f"  [[{slug}]] NOT found in index.md — update the index")
    return r


def check_domain_moc(wiki_files: list[str]) -> CheckResult:
    """Check domain MOC status for concepts created in this ingest."""
    r = CheckResult("Domain MOC Status")
    concepts = [wf for wf in wiki_files if "/concepts/" in wf]
    if not concepts:
        r.ok("No concept files — domain MOC check not applicable.")
        return r

    # Collect domains from new concepts
    domains: dict[str, list[str]] = {}
    for wf in concepts:
        full = REPO_ROOT / wf
        if not full.is_file():
            continue
        fm = parse_frontmatter(full.read_text(encoding="utf-8"))
        domain = fm.get("domain", "unknown")
        domains.setdefault(domain, []).append(Path(wf).stem)

    # Count total concepts per domain
    concepts_dir = WIKI_DIR / "concepts"
    for domain, new_slugs in domains.items():
        total = 0
        if concepts_dir.is_dir():
            for fpath in concepts_dir.iterdir():
                if not fpath.is_file() or fpath.suffix != ".md":
                    continue
                try:
                    fm = parse_frontmatter(fpath.read_text(encoding="utf-8"))
                except OSError:
                    continue
                if fm.get("domain") == domain:
                    total += 1

        moc_path = WIKI_DIR / "domains" / f"{domain}.md"
        has_moc = moc_path.is_file()

        if has_moc:
            # Check if MOC was updated (contains links to new concepts)
            moc_content = moc_path.read_text(encoding="utf-8")
            moc_links = set(extract_backlinks(moc_content))
            missing_from_moc = [s for s in new_slugs if s not in moc_links]
            if missing_from_moc:
                r.fail(f"  {domain}: MOC exists but missing links to: {', '.join(missing_from_moc)}")
            else:
                r.ok(f"  {domain}: MOC exists and includes new concepts ({total} total)")
        elif total >= 5:
            r.fail(f"  {domain}: {total} concepts but NO MOC — create vault/wiki/domains/{domain}.md")
        elif total >= 3:
            r.warn(f"  {domain}: {total}/5 concepts — approaching MOC threshold")
        else:
            r.ok(f"  {domain}: {total} concepts (below MOC threshold)")

    return r


# ── Runner ───────────────────────────────────────────────────────────────────

def run_checks(source_path: str) -> bool:
    """Run all post-ingest checks for a source. Returns True if all pass."""
    print(f"\n{'=' * 60}")
    print(f"  POST-INGEST CHECK: {source_path}")
    print(f"{'=' * 60}")

    icon = {"OK": "✓", "WARN": "⚠", "FAIL": "✗", "INFO": "ℹ"}

    # 1. Manifest
    manifest_result, wiki_files = check_manifest(source_path)
    checks = [manifest_result]

    if not wiki_files:
        # Can't run further checks without wiki_files
        _print_check(manifest_result, icon)
        print(f"\n{'=' * 60}")
        print(f"  RESULT: ✗ FAIL — manifest issues prevent further checks.")
        print(f"{'=' * 60}")
        return False

    # 2-9. Run all checks
    checks.extend([
        check_files_exist(wiki_files),
        check_frontmatter_valid(wiki_files),
        check_concept_length(wiki_files),
        check_summary_sections(wiki_files),
        check_image_coverage(source_path, wiki_files),
        check_broken_links(wiki_files),
        check_index_completeness(wiki_files),
        check_domain_moc(wiki_files),
    ])

    # Print results
    total_pass = 0
    total_fail = 0
    total_warn = 0

    for check in checks:
        _print_check(check, icon)
        if check.passed:
            total_pass += 1
        else:
            total_fail += 1
        total_warn += sum(1 for level, _ in check.messages if level == "WARN")

    # Summary
    all_passed = total_fail == 0
    print(f"\n{'=' * 60}")
    if all_passed and total_warn == 0:
        print(f"  RESULT: ✓ ALL CHECKS PASSED ({total_pass}/{len(checks)})")
    elif all_passed:
        print(f"  RESULT: ⚠ PASSED WITH WARNINGS ({total_pass}/{len(checks)} passed, {total_warn} warning(s))")
    else:
        print(f"  RESULT: ✗ FAILED ({total_fail}/{len(checks)} failed, {total_warn} warning(s))")
    print(f"{'=' * 60}")

    return all_passed


def _print_check(check: CheckResult, icon: dict[str, str]):
    print(f"\n── {check.name} {'─' * (50 - len(check.name))}")
    status = "✓ PASS" if check.passed else "✗ FAIL"
    print(f"  [{status}]")
    for level, msg in check.messages:
        print(f"  {icon.get(level, '?')} {msg}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="post_ingest_check.py",
        description="Post-compilation validation for a staging source.",
    )
    parser.add_argument(
        "source", nargs="?",
        help="Path to a staging source (e.g. vault/staging/articles/my-article.md)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Check all compiled sources in the manifest.",
    )
    args = parser.parse_args()

    if args.all:
        manifest = load_compile_manifest(MANIFEST_PATH)
        sources = manifest.get("sources", {})
        compiled = [k for k, v in sources.items() if v.get("status") == "compiled"]
        if not compiled:
            print("No compiled sources found in manifest.")
            return 0

        all_passed = True
        for source_path in sorted(compiled):
            if not run_checks(source_path):
                all_passed = False

        print(f"\n{'=' * 60}")
        print(f"  TOTAL: {len(compiled)} source(s) checked")
        print(f"{'=' * 60}")
        return 0 if all_passed else 1

    if not args.source:
        parser.print_help()
        return 1

    source_path = args.source
    full_path = REPO_ROOT / source_path

    if not full_path.is_file():
        print(f"ERROR: File not found: {source_path}")
        return 1
    if not source_path.startswith("vault/staging/"):
        print(f"ERROR: File is not under vault/staging/: {source_path}")
        return 1

    return 0 if run_checks(source_path) else 1


if __name__ == "__main__":
    sys.exit(main())
