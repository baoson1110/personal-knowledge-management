#!/usr/bin/env python3
"""
Comprehensive wiki lint tool.

Covers all lint checks defined in .kiro/steering/lint-rules.md:
  1. Broken internal [[backlinks]]
  2. Orphan files (no inbound links)
  3. Missing frontmatter fields
  4. Missing concept files
  5. Topic synthesis (delegates to analyze-wiki.py)
  6. Domain MOC readiness (delegates to analyze-wiki.py)
  7. Duplicate concept detection (delegates to analyze-wiki.py)
  8. Cross-linking gaps (delegates to analyze-wiki.py)
  9. Tag registry violations (delegates to analyze-wiki.py)
 10. LaTeX formula formatting (audit + auto-fix)
 11. Index completeness (files missing from index, dangling index refs)
 12. Image coverage (summaries/concepts missing images from source)
 13. Unlocalized images (raw sources with external URLs not downloaded)

Usage:
  python3 tools/wiki_lint.py                  # Full audit (report only)
  python3 tools/wiki_lint.py --fix            # Audit + auto-fix LaTeX
  python3 tools/wiki_lint.py --check broken   # Run a single check
  python3 tools/wiki_lint.py --check latex    # LaTeX audit only
  python3 tools/wiki_lint.py --check latex --fix  # LaTeX audit + fix
  python3 tools/wiki_lint.py --check index    # Index completeness only
  python3 tools/wiki_lint.py --check images   # Image coverage only
  python3 tools/wiki_lint.py --check unlocalized  # Unlocalized images only
  python3 tools/wiki_lint.py --json           # Machine-readable output
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = REPO_ROOT / "wiki"
INDEX_PATH = WIKI_DIR / "index.md"
TAGS_PATH = WIKI_DIR / "tags.yml"
SUBDIRS = ["concepts", "summaries", "topics", "domains", "reference"]

REQUIRED_FIELDS = ["title", "domain", "tags", "created", "updated", "source", "confidence"]

_BACKLINK_RE = re.compile(r"\[\[([a-zA-Z0-9_-]+)\]\]")

# Image reference patterns
_ASSET_IMAGE_RE = re.compile(r"!\[\[asset/([^\]]+)\]\]")
_EXTERNAL_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(https?://[^)]+\)")


# ── Unicode math characters that are ALWAYS mathematical ─────────────────────
MATH_CHARS: dict[str, str] = {
    "γ": r"\gamma",  "π": r"\pi",     "α": r"\alpha",  "β": r"\beta",
    "δ": r"\delta",  "ε": r"\epsilon", "θ": r"\theta",  "λ": r"\lambda",
    "μ": r"\mu",     "σ": r"\sigma",   "Σ": r"\sum",    "τ": r"\tau",
    "∈": r"\in",     "≤": r"\leq",     "≥": r"\geq",
    "∝": r"\propto", "∞": r"\infty",
}

# Unicode superscript → ASCII digit mapping
SUP_MAP: dict[str, str] = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁻": "-", "ⁿ": "n",
}
SUP_CHARS = set(SUP_MAP.keys())

# Unicode subscript characters (for detection)
SUB_CHARS = set("ₜₛₐₑₒᵢₙₖ₀₁₂₃₄₅₆₇₈₉")


# ── File loading helpers ─────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict[str, Any]:
    """Extract YAML frontmatter from markdown text."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict[str, Any] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        key = key.strip()
        value = raw_value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            fm[key] = [
                item.strip().strip('"').strip("'")
                for item in inner.split(",")
                if item.strip()
            ]
        else:
            fm[key] = value.strip('"').strip("'")
    return fm


def extract_backlinks(text: str) -> list[str]:
    """Extract all [[...]] backlink targets, excluding code blocks."""
    no_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    no_code = re.sub(r"`[^`]+`", "", no_code)
    return _BACKLINK_RE.findall(no_code)


def load_wiki_files() -> list[dict[str, Any]]:
    """Load all .md wiki files from all subdirectories."""
    files: list[dict[str, Any]] = []
    for subdir in SUBDIRS:
        dirpath = WIKI_DIR / subdir
        if not dirpath.is_dir():
            continue
        for fpath in sorted(dirpath.iterdir()):
            if not fpath.is_file() or fpath.suffix != ".md" or fpath.name.startswith("."):
                continue
            try:
                content = fpath.read_text(encoding="utf-8")
            except OSError:
                continue
            fm = parse_frontmatter(content)
            backlinks = extract_backlinks(content)
            files.append({
                "slug": fpath.stem,
                "path": str(fpath.relative_to(REPO_ROOT)),
                "subdir": subdir,
                "frontmatter": fm,
                "backlinks": backlinks,
                "content": content,
            })
    return files


def load_index_backlinks() -> list[str]:
    """Extract backlinks from wiki/index.md."""
    if not INDEX_PATH.exists():
        return []
    return extract_backlinks(INDEX_PATH.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 1 — Broken Internal Links
# ══════════════════════════════════════════════════════════════════════════════

def check_broken_links(files: list[dict]) -> list[dict]:
    """Find [[backlinks]] that point to non-existent wiki files."""
    slug_set = {f["slug"] for f in files}
    broken: list[dict] = []

    # Check wiki files
    for f in files:
        for target in f["backlinks"]:
            if target not in slug_set:
                broken.append({"source": f["path"], "target": target})

    # Check index.md
    for target in load_index_backlinks():
        if target not in slug_set:
            broken.append({"source": "wiki/index.md", "target": target})

    return broken


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 2 — Orphan Files
# ══════════════════════════════════════════════════════════════════════════════

def check_orphans(files: list[dict]) -> list[str]:
    """Find wiki files with zero inbound [[backlinks]] from other wiki files."""
    inbound: dict[str, set[str]] = defaultdict(set)

    # Links from wiki files
    for f in files:
        for target in f["backlinks"]:
            inbound[target].add(f["slug"])

    # Links from index
    for target in load_index_backlinks():
        inbound[target].add("index")

    orphans: list[str] = []
    for f in files:
        if f["slug"] not in inbound or len(inbound[f["slug"]]) == 0:
            orphans.append(f["path"])
    return orphans


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 3 — Missing Frontmatter
# ══════════════════════════════════════════════════════════════════════════════

def check_frontmatter(files: list[dict]) -> list[dict]:
    """Find files missing required YAML frontmatter fields."""
    issues: list[dict] = []
    for f in files:
        fm = f["frontmatter"]
        missing = [field for field in REQUIRED_FIELDS if field not in fm or fm[field] is None or fm[field] == ""]
        if missing:
            issues.append({"path": f["path"], "missing_fields": missing})
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 4 — Missing Concept Files
# ══════════════════════════════════════════════════════════════════════════════

def check_missing_concepts(files: list[dict]) -> list[dict]:
    """Find [[backlink]] targets that don't resolve to any wiki file."""
    slug_set = {f["slug"] for f in files}
    ref_counts: Counter = Counter()

    for f in files:
        for target in f["backlinks"]:
            if target not in slug_set:
                ref_counts[target] += 1

    for target in load_index_backlinks():
        if target not in slug_set:
            ref_counts[target] += 1

    return [
        {"slug": slug, "references": count}
        for slug, count in ref_counts.most_common()
    ]


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 10 — LaTeX Formula Formatting
# ══════════════════════════════════════════════════════════════════════════════

def _strip_latex_and_code(line: str) -> str:
    """Replace $...$ and `...` spans with spaces (preserving positions)."""
    cleaned = re.sub(r"\$\$.*?\$\$", lambda m: " " * len(m.group()), line)
    cleaned = re.sub(r"\$.*?\$", lambda m: " " * len(m.group()), cleaned)
    cleaned = re.sub(r"`[^`]+`", lambda m: " " * len(m.group()), cleaned)
    return cleaned


def _audit_latex_line(line: str, lineno: int) -> list[dict]:
    """Audit a single line for Unicode math outside LaTeX delimiters."""
    cleaned = _strip_latex_and_code(line)
    issues: list[dict] = []

    for char, latex in MATH_CHARS.items():
        if char in cleaned:
            issues.append({
                "line": lineno,
                "char": char,
                "latex": latex,
                "context": line.strip()[:120],
            })

    for char in SUB_CHARS | SUP_CHARS:
        if char in cleaned:
            issues.append({
                "line": lineno,
                "char": char,
                "latex": "sub/sup",
                "context": line.strip()[:120],
            })

    return issues


def audit_latex(files: list[dict]) -> list[dict]:
    """Audit all wiki files for Unicode math outside LaTeX delimiters.

    Returns list of {path, issues: [{line, char, latex, context}]}.
    """
    results: list[dict] = []
    for f in files:
        lines = f["content"].split("\n")
        file_issues: list[dict] = []
        in_code_block = False
        fm_count = 0

        for i, line in enumerate(lines, 1):
            if line.strip() == "---":
                fm_count += 1
                continue
            if fm_count == 1:  # inside frontmatter
                continue
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            file_issues.extend(_audit_latex_line(line, i))

        if file_issues:
            results.append({"path": f["path"], "issues": file_issues})
    return results


def _fix_latex_line(line: str) -> tuple[str, int]:
    """Fix Unicode math characters in a single line. Returns (fixed_line, fix_count)."""
    changes = 0

    # Fix Greek letters and math symbols
    for char, latex in MATH_CHARS.items():
        if char not in line:
            continue
        # Only replace occurrences outside $...$ and `...`
        result_parts: list[str] = []
        pos = 0
        while pos < len(line):
            idx = line.find(char, pos)
            if idx == -1:
                result_parts.append(line[pos:])
                break
            # Check if this position is inside LaTeX or code
            prefix = line[:idx]
            cleaned_prefix = _strip_latex_and_code(prefix + char + line[idx + 1:])
            if cleaned_prefix[idx] != " ":  # not masked → outside LaTeX/code
                result_parts.append(line[pos:idx])
                result_parts.append(f"${latex}$")
                changes += 1
                pos = idx + 1
            else:
                result_parts.append(line[pos:idx + 1])
                pos = idx + 1
        line = "".join(result_parts)

    # Fix Unicode superscripts: 10⁻⁵ → $10^{-5}$
    sup_chars_re = "".join(re.escape(c) for c in SUP_MAP)
    pattern = re.compile(r"(\d+)([" + sup_chars_re + r"]+)")

    def _replace_sup(m: re.Match) -> str:
        nonlocal changes
        start = m.start()
        cleaned = _strip_latex_and_code(line)
        if start < len(cleaned) and cleaned[start] == " ":
            return m.group(0)  # inside LaTeX/code
        base = m.group(1)
        exp = "".join(SUP_MAP.get(c, c) for c in m.group(2))
        changes += 1
        return f"${base}^{{{exp}}}$"

    line = pattern.sub(_replace_sup, line)
    return line, changes


def fix_latex(files: list[dict]) -> list[dict]:
    """Auto-fix Unicode math in all wiki files.

    Returns list of {path, fixes: int} for files that were modified.
    """
    results: list[dict] = []
    for f in files:
        lines = f["content"].split("\n")
        new_lines: list[str] = []
        total_fixes = 0
        in_code_block = False
        fm_count = 0

        for line in lines:
            if line.strip() == "---":
                fm_count += 1
                new_lines.append(line)
                continue
            if fm_count == 1:
                new_lines.append(line)
                continue
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                new_lines.append(line)
                continue
            if in_code_block:
                new_lines.append(line)
                continue

            fixed, count = _fix_latex_line(line)
            new_lines.append(fixed)
            total_fixes += count

        if total_fixes > 0:
            filepath = REPO_ROOT / f["path"]
            filepath.write_text("\n".join(new_lines), encoding="utf-8")
            results.append({"path": f["path"], "fixes": total_fixes})

    return results


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 11 — Index Completeness
# ══════════════════════════════════════════════════════════════════════════════

def check_index_completeness(files: list[dict]) -> dict[str, list[str]]:
    """Check that wiki/index.md references all wiki files and has no dangling refs.

    Returns {"missing_from_index": [...], "dangling_in_index": [...]}.
    """
    wiki_slugs = {f["slug"] for f in files}
    index_slugs = set(load_index_backlinks())

    missing_from_index = sorted(wiki_slugs - index_slugs)
    dangling_in_index = sorted(index_slugs - wiki_slugs)

    return {
        "missing_from_index": missing_from_index,
        "dangling_in_index": dangling_in_index,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 12 — Image Coverage
# ══════════════════════════════════════════════════════════════════════════════

def _count_asset_images(text: str) -> int:
    """Count ![[asset/...]] image references in text, excluding code blocks."""
    no_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    no_code = re.sub(r"`[^`]+`", "", no_code)
    return len(_ASSET_IMAGE_RE.findall(no_code))


def _read_source_file(source_path: str) -> str | None:
    """Read a raw source file given its path from frontmatter."""
    fpath = REPO_ROOT / source_path
    if not fpath.is_file():
        return None
    try:
        return fpath.read_text(encoding="utf-8")
    except OSError:
        return None


def check_image_coverage(files: list[dict]) -> dict[str, list[dict]]:
    """Check that wiki files use images from their source when available.

    Returns {
        "summary_missing": [{path, source, source_images, wiki_images}],
        "summary_low": [{path, source, source_images, wiki_images, pct}],
        "concept_missing": [{path, source, source_images}],
    }
    """
    summary_missing: list[dict] = []
    summary_low: list[dict] = []
    concept_missing: list[dict] = []

    for f in files:
        fm = f["frontmatter"]
        source_path = fm.get("source", "")
        if not source_path or not source_path.startswith("raw/"):
            continue

        source_text = _read_source_file(source_path)
        if source_text is None:
            continue

        source_images = _count_asset_images(source_text)
        if source_images == 0:
            continue

        wiki_images = _count_asset_images(f["content"])

        if f["subdir"] == "summaries":
            if wiki_images == 0:
                summary_missing.append({
                    "path": f["path"],
                    "source": source_path,
                    "source_images": source_images,
                    "wiki_images": 0,
                })
            elif source_images > 0:
                pct = round(wiki_images / source_images * 100)
                if pct < 50:
                    summary_low.append({
                        "path": f["path"],
                        "source": source_path,
                        "source_images": source_images,
                        "wiki_images": wiki_images,
                        "pct": pct,
                    })

        elif f["subdir"] == "concepts":
            if wiki_images == 0 and source_images >= 5:
                concept_missing.append({
                    "path": f["path"],
                    "source": source_path,
                    "source_images": source_images,
                })

    return {
        "summary_missing": summary_missing,
        "summary_low": summary_low,
        "concept_missing": concept_missing,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 13 — Unlocalized Images
# ══════════════════════════════════════════════════════════════════════════════

def check_unlocalized_images() -> list[dict]:
    """Scan raw sources for external image URLs not yet localized to asset/.

    Returns list of {path, count} for raw files with external image URLs.
    """
    results: list[dict] = []
    raw_dir = REPO_ROOT / "raw"
    if not raw_dir.is_dir():
        return results

    for fpath in sorted(raw_dir.rglob("*.md")):
        if fpath.name.startswith("."):
            continue
        try:
            content = fpath.read_text(encoding="utf-8")
        except OSError:
            continue

        # Strip code blocks to avoid false positives
        no_code = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        no_code = re.sub(r"`[^`]+`", "", no_code)

        external_count = len(_EXTERNAL_IMAGE_RE.findall(no_code))
        if external_count > 0:
            results.append({
                "path": str(fpath.relative_to(REPO_ROOT)),
                "count": external_count,
            })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Reporting
# ══════════════════════════════════════════════════════════════════════════════

def print_report(
    broken: list[dict],
    orphans: list[str],
    fm_issues: list[dict],
    missing: list[dict],
    latex_audit: list[dict],
    latex_fixes: list[dict] | None,
    index_issues: dict[str, list[str]] | None = None,
    image_coverage: dict[str, list[dict]] | None = None,
    unlocalized: list[dict] | None = None,
) -> None:
    """Print a human-readable lint report."""

    def _header(title: str) -> None:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")

    _header("CHECK 1: Broken Internal Links")
    if broken:
        for b in broken:
            print(f"  BROKEN: {b['source']} → [[{b['target']}]]")
    else:
        print("  ✓ No broken links.")
    print(f"  Total: {len(broken)}")

    _header("CHECK 2: Orphan Files")
    if orphans:
        for o in orphans:
            print(f"  ORPHAN: {o}")
    else:
        print("  ✓ No orphan files.")
    print(f"  Total: {len(orphans)}")

    _header("CHECK 3: Missing Frontmatter")
    if fm_issues:
        for issue in fm_issues:
            print(f"  {issue['path']}: missing {issue['missing_fields']}")
    else:
        print("  ✓ All files have complete frontmatter.")
    print(f"  Total: {len(fm_issues)} files")

    _header("CHECK 4: Missing Concept Files")
    if missing:
        for m in missing:
            print(f"  MISSING: [[{m['slug']}]] (referenced {m['references']} time(s))")
    else:
        print("  ✓ No missing concept files.")
    print(f"  Total: {len(missing)}")

    _header("CHECK 10: LaTeX Formatting")
    total_latex = sum(len(r["issues"]) for r in latex_audit)
    if latex_audit:
        for r in latex_audit:
            print(f"  {r['path']}: {len(r['issues'])} issue(s)")
            for issue in r["issues"][:3]:
                print(f"    L{issue['line']}: '{issue['char']}' → {issue['latex']}")
            if len(r["issues"]) > 3:
                print(f"    ... and {len(r['issues']) - 3} more")
    else:
        print("  ✓ No LaTeX formatting issues.")
    print(f"  Total: {total_latex} across {len(latex_audit)} files")

    if latex_fixes is not None:
        total_fixed = sum(r["fixes"] for r in latex_fixes)
        if latex_fixes:
            print(f"\n  AUTO-FIXED: {total_fixed} issues across {len(latex_fixes)} files:")
            for r in latex_fixes:
                print(f"    {r['path']}: {r['fixes']} fix(es)")
        else:
            print("\n  No fixes needed.")

    _header("CHECK 11: Index Completeness")
    if index_issues is not None:
        missing_idx = index_issues["missing_from_index"]
        dangling_idx = index_issues["dangling_in_index"]
        if missing_idx:
            print(f"  Files NOT referenced in wiki/index.md: {len(missing_idx)}")
            for slug in missing_idx:
                print(f"    MISSING: [[{slug}]]")
        else:
            print("  ✓ All wiki files are referenced in index.md.")
        if dangling_idx:
            print(f"  Dangling index references (no matching file): {len(dangling_idx)}")
            for slug in dangling_idx:
                print(f"    DANGLING: [[{slug}]]")
        elif not missing_idx:
            print("  ✓ No dangling references in index.md.")
        print(f"  Total: {len(missing_idx)} missing, {len(dangling_idx)} dangling")
    else:
        print("  (skipped)")

    _header("CHECK 12: Image Coverage")
    if image_coverage is not None:
        sm = image_coverage["summary_missing"]
        sl = image_coverage["summary_low"]
        cm = image_coverage["concept_missing"]
        if sm:
            print(f"  Summaries with NO images (source has images): {len(sm)}")
            for item in sm:
                print(f"    ERROR: {item['path']}")
                print(f"      Source {item['source']} has {item['source_images']} images, summary has 0")
        if sl:
            print(f"  Summaries with LOW image coverage (<50%): {len(sl)}")
            for item in sl:
                print(f"    WARN: {item['path']}")
                print(f"      Source has {item['source_images']} images, summary has {item['wiki_images']} ({item['pct']}%)")
        if cm:
            print(f"  Concepts with no images (source has 5+): {len(cm)}")
            for item in cm:
                print(f"    SUGGEST: {item['path']}")
                print(f"      Source {item['source']} has {item['source_images']} images — consider adding key diagrams")
        if not sm and not sl and not cm:
            print("  ✓ All wiki files have adequate image coverage.")
        print(f"  Total: {len(sm)} missing, {len(sl)} low, {len(cm)} suggestions")
    else:
        print("  (skipped)")

    _header("CHECK 13: Unlocalized Images")
    if unlocalized is not None:
        if unlocalized:
            total_ext = sum(u["count"] for u in unlocalized)
            print(f"  Raw sources with external image URLs: {len(unlocalized)}")
            for u in unlocalized:
                print(f"    {u['path']}: {u['count']} external URL(s)")
            print(f"  Total: {total_ext} external images across {len(unlocalized)} files")
            print("  Action: Run Obsidian Local Images Plus plugin on these files")
        else:
            print("  ✓ All raw source images are localized to asset/.")
        print(f"  Total: {sum(u['count'] for u in unlocalized) if unlocalized else 0}")
    else:
        print("  (skipped)")

    # ── Summary ──────────────────────────────────────────────────────────
    _header("SUMMARY")
    print(f"  Wiki files scanned:    {_file_count}")
    print(f"  Broken links:          {len(broken)}")
    print(f"  Orphan files:          {len(orphans)}")
    print(f"  Missing frontmatter:   {len(fm_issues)} files")
    print(f"  Missing concepts:      {len(missing)}")
    print(f"  LaTeX issues:          {total_latex} across {len(latex_audit)} files")
    if latex_fixes is not None:
        total_fixed = sum(r["fixes"] for r in latex_fixes)
        print(f"  LaTeX auto-fixed:      {total_fixed} across {len(latex_fixes)} files")
    if index_issues is not None:
        print(f"  Index missing:         {len(index_issues['missing_from_index'])} files")
        print(f"  Index dangling:        {len(index_issues['dangling_in_index'])} refs")
    if image_coverage is not None:
        sm = image_coverage["summary_missing"]
        sl = image_coverage["summary_low"]
        cm = image_coverage["concept_missing"]
        print(f"  Image missing:         {len(sm)} summaries")
        print(f"  Image low coverage:    {len(sl)} summaries")
        print(f"  Image suggestions:     {len(cm)} concepts")
    if unlocalized is not None:
        print(f"  Unlocalized images:    {sum(u['count'] for u in unlocalized)} across {len(unlocalized)} files")
    print()
    print("  Tip: Run `python3 tools/analyze-wiki.py --all` for structural")
    print("  checks (domains, topics, duplicates, cross-linking, tags).")


def build_json_report(
    broken: list[dict],
    orphans: list[str],
    fm_issues: list[dict],
    missing: list[dict],
    latex_audit: list[dict],
    latex_fixes: list[dict] | None,
    index_issues: dict[str, list[str]] | None = None,
    image_coverage: dict[str, list[dict]] | None = None,
    unlocalized: list[dict] | None = None,
) -> dict:
    """Build a machine-readable JSON report."""
    report = {
        "files_scanned": _file_count,
        "broken_links": broken,
        "orphan_files": orphans,
        "missing_frontmatter": fm_issues,
        "missing_concepts": missing,
        "latex_issues": {
            "total": sum(len(r["issues"]) for r in latex_audit),
            "files": len(latex_audit),
            "details": latex_audit,
        },
        "latex_fixes": latex_fixes,
    }
    if index_issues is not None:
        report["index_completeness"] = index_issues
    if image_coverage is not None:
        report["image_coverage"] = image_coverage
    if unlocalized is not None:
        report["unlocalized_images"] = unlocalized
    return report


# ── Global for summary ───────────────────────────────────────────────────────
_file_count: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

CHECKS = ["broken", "orphans", "frontmatter", "missing", "latex", "index", "images", "unlocalized"]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="wiki_lint.py",
        description="Comprehensive wiki lint: broken links, orphans, frontmatter, missing concepts, LaTeX.",
    )
    parser.add_argument(
        "--check",
        choices=CHECKS,
        help="Run a single check instead of all. Choices: " + ", ".join(CHECKS),
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix LaTeX formatting issues (converts Unicode math to $...$).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    global _file_count
    files = load_wiki_files()
    _file_count = len(files)

    run_all = args.check is None
    target = args.check

    # Run requested checks
    broken = check_broken_links(files) if (run_all or target == "broken") else []
    orphans = check_orphans(files) if (run_all or target == "orphans") else []
    fm_issues = check_frontmatter(files) if (run_all or target == "frontmatter") else []
    missing = check_missing_concepts(files) if (run_all or target == "missing") else []
    latex_results = audit_latex(files) if (run_all or target == "latex") else []
    index_issues = check_index_completeness(files) if (run_all or target == "index") else None
    image_coverage = check_image_coverage(files) if (run_all or target == "images") else None
    unlocalized = check_unlocalized_images() if (run_all or target == "unlocalized") else None

    # Auto-fix if requested
    latex_fixes: list[dict] | None = None
    if args.fix and (run_all or target == "latex"):
        latex_fixes = fix_latex(files)

    # Output
    if args.json_output:
        report = build_json_report(broken, orphans, fm_issues, missing, latex_results, latex_fixes, index_issues, image_coverage, unlocalized)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(broken, orphans, fm_issues, missing, latex_results, latex_fixes, index_issues, image_coverage, unlocalized)

    # Exit code: non-zero if any issues found
    has_issues = bool(broken or orphans or fm_issues or missing)
    if index_issues is not None:
        has_issues = has_issues or bool(index_issues["missing_from_index"] or index_issues["dangling_in_index"])
    if image_coverage is not None:
        has_issues = has_issues or bool(image_coverage["summary_missing"])
    if unlocalized is not None:
        has_issues = has_issues or bool(unlocalized)
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
