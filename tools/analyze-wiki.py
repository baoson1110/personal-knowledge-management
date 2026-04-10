#!/usr/bin/env python3
"""analyze-wiki.py — Wiki health metrics and opportunity detection.

Analyzes the wiki structure to report:
  - Concepts per domain (with MOC threshold indicators)
  - Topic emergence candidates (concept clusters without a topic page)
  - Concept deduplication candidates (similar titles/tags)
  - Cross-linking density metrics
  - Overall wiki health dashboard

Uses only the Python standard library (no external dependencies).
"""

import argparse
import os
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
WIKI_DIR = REPO_ROOT / "wiki"

DOMAIN_MOC_THRESHOLD = 10
DOMAIN_MOC_WARNING_THRESHOLD = 8
TOPIC_CANDIDATE_MIN_CONCEPTS = 3
DUPLICATE_TAG_OVERLAP_THRESHOLD = 3

_BACKLINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")


# --- Frontmatter & file parsing ---

def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter key-value pairs from markdown text."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict = {}
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
    """Extract all [[...]] backlink references from text."""
    return _BACKLINK_RE.findall(text)


def load_wiki_files(subdir: str) -> list[dict]:
    """Load all .md files from a wiki subdirectory."""
    dirpath = WIKI_DIR / subdir
    if not dirpath.is_dir():
        return []
    files = []
    for fpath in sorted(dirpath.iterdir()):
        if not fpath.is_file() or fpath.suffix != ".md":
            continue
        if fpath.name.startswith((".", "_")):
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
            "frontmatter": fm,
            "backlinks": backlinks,
            "line_count": len(content.splitlines()),
        })
    return files


# --- Domain analysis ---

def analyze_domains(concepts: list[dict]) -> dict:
    """Analyze concept distribution across domains.

    Returns dict with:
      - domain_counts: {domain: count}
      - moc_ready: domains with 10+ concepts and no MOC
      - moc_approaching: domains with 8-9 concepts and no MOC
      - existing_mocs: list of existing domain MOC slugs
    """
    domain_counts: dict[str, int] = Counter()
    domain_concepts: dict[str, list[str]] = defaultdict(list)

    for c in concepts:
        domain = c["frontmatter"].get("domain", "unknown")
        domain_counts[domain] += 1
        domain_concepts[domain].append(c["slug"])

    # Check which domain MOCs already exist
    domains_dir = WIKI_DIR / "domains"
    existing_mocs: set[str] = set()
    if domains_dir.is_dir():
        for f in domains_dir.iterdir():
            if f.suffix == ".md" and not f.name.startswith("."):
                existing_mocs.add(f.stem)

    moc_ready = []
    moc_approaching = []
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
        if domain in existing_mocs:
            continue
        if count >= DOMAIN_MOC_THRESHOLD:
            moc_ready.append((domain, count, domain_concepts[domain]))
        elif count >= DOMAIN_MOC_WARNING_THRESHOLD:
            moc_approaching.append((domain, count, domain_concepts[domain]))

    return {
        "domain_counts": dict(domain_counts),
        "domain_concepts": dict(domain_concepts),
        "moc_ready": moc_ready,
        "moc_approaching": moc_approaching,
        "existing_mocs": sorted(existing_mocs),
    }


# --- Topic candidate detection ---

def find_topic_candidates(concepts: list[dict], existing_topics: list[dict]) -> list[dict]:
    """Find clusters of 3+ concepts that could form a topic page.

    A cluster is a group of concepts that share the same domain AND have
    overlapping tags (2+ shared tags between any pair in the cluster).
    Excludes clusters already covered by an existing topic file.
    """
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for c in concepts:
        domain = c["frontmatter"].get("domain", "unknown")
        by_domain[domain].append(c)

    covered_slugs: set[str] = set()
    for t in existing_topics:
        covered_slugs.update(t["backlinks"])

    candidates = []

    for domain, domain_concepts in by_domain.items():
        if len(domain_concepts) < TOPIC_CANDIDATE_MIN_CONCEPTS:
            continue

        # Build adjacency based on tag overlap
        adjacency: dict[str, set[str]] = defaultdict(set)
        for a, b in combinations(domain_concepts, 2):
            tags_a = set(a["frontmatter"].get("tags", []))
            tags_b = set(b["frontmatter"].get("tags", []))
            shared = tags_a & tags_b
            if len(shared) >= 2:
                adjacency[a["slug"]].add(b["slug"])
                adjacency[b["slug"]].add(a["slug"])

        # Find connected components via BFS
        visited: set[str] = set()
        for concept in domain_concepts:
            slug = concept["slug"]
            if slug in visited or slug not in adjacency:
                continue
            cluster: set[str] = set()
            queue = [slug]
            while queue:
                node = queue.pop(0)
                if node in cluster:
                    continue
                cluster.add(node)
                for neighbor in adjacency.get(node, set()):
                    if neighbor not in cluster:
                        queue.append(neighbor)
            visited.update(cluster)

            if len(cluster) >= TOPIC_CANDIDATE_MIN_CONCEPTS:
                if cluster & covered_slugs == cluster:
                    continue
                cluster_tags: list[set[str]] = []
                for c in domain_concepts:
                    if c["slug"] in cluster:
                        cluster_tags.append(set(c["frontmatter"].get("tags", [])))
                common_tags = set.intersection(*cluster_tags) if cluster_tags else set()

                candidates.append({
                    "domain": domain,
                    "concepts": sorted(cluster),
                    "common_tags": sorted(common_tags),
                    "size": len(cluster),
                })

    candidates.sort(key=lambda x: -x["size"])
    return candidates


# --- Duplicate detection ---

def find_duplicate_candidates(concepts: list[dict]) -> list[dict]:
    """Find concept pairs that may be duplicates based on tag overlap and title similarity."""
    duplicates = []

    for a, b in combinations(concepts, 2):
        tags_a = set(a["frontmatter"].get("tags", []))
        tags_b = set(b["frontmatter"].get("tags", []))
        shared_tags = tags_a & tags_b

        if len(shared_tags) >= DUPLICATE_TAG_OVERLAP_THRESHOLD:
            title_a = set(a["frontmatter"].get("title", "").lower().split())
            title_b = set(b["frontmatter"].get("title", "").lower().split())
            title_overlap = title_a & title_b - {"the", "a", "an", "of", "in", "for", "and", "or"}

            if len(title_overlap) >= 2:
                duplicates.append({
                    "concept_a": a["slug"],
                    "concept_b": b["slug"],
                    "shared_tags": sorted(shared_tags),
                    "title_overlap": sorted(title_overlap),
                })

    return duplicates


# --- Cross-linking density ---

def analyze_cross_linking(concepts: list[dict]) -> dict:
    """Analyze cross-linking density across concept files."""
    concept_slugs = {c["slug"] for c in concepts}

    outbound: dict[str, set[str]] = {}
    for c in concepts:
        links = set(c["backlinks"]) & concept_slugs
        outbound[c["slug"]] = links - {c["slug"]}

    inbound: dict[str, set[str]] = defaultdict(set)
    for src, targets in outbound.items():
        for tgt in targets:
            inbound[tgt].add(src)

    total_out = sum(len(v) for v in outbound.values())
    total_in = sum(len(v) for v in inbound.values())
    n = len(concepts) or 1

    weakly_linked = [
        slug for slug, links in outbound.items()
        if len(links) < 2
    ]

    by_domain: dict[str, list[str]] = defaultdict(list)
    for c in concepts:
        domain = c["frontmatter"].get("domain", "unknown")
        by_domain[domain].append(c["slug"])

    unlinked_pairs = []
    for domain, slugs in by_domain.items():
        for a, b in combinations(slugs, 2):
            if b not in outbound.get(a, set()) and a not in outbound.get(b, set()):
                unlinked_pairs.append((a, b, domain))

    return {
        "avg_outbound": round(total_out / n, 2),
        "avg_inbound": round(total_in / n, 2),
        "weakly_linked": sorted(weakly_linked),
        "unlinked_same_domain": unlinked_pairs[:20],
        "total_concepts": n,
    }


# --- CLI output formatting ---

def print_domain_status(domain_info: dict) -> None:
    """Print domain analysis report."""
    print("=== Domain Status ===")
    print()
    counts = domain_info["domain_counts"]
    if not counts:
        print("  No concepts found.")
        return

    for domain, count in sorted(counts.items(), key=lambda x: -x[1]):
        moc_marker = ""
        if domain in domain_info["existing_mocs"]:
            moc_marker = " [MOC exists]"
        elif count >= DOMAIN_MOC_THRESHOLD:
            moc_marker = " [MOC READY — 10+ concepts]"
        elif count >= DOMAIN_MOC_WARNING_THRESHOLD:
            moc_marker = f" [approaching MOC threshold: {count}/{DOMAIN_MOC_THRESHOLD}]"
        concepts_list = domain_info["domain_concepts"].get(domain, [])
        print(f"  {domain}: {count} concepts{moc_marker}")
        for slug in concepts_list:
            print(f"    - {slug}")
    print()

    if domain_info["moc_ready"]:
        print("ACTION REQUIRED — Create domain MOCs for:")
        for domain, count, slugs in domain_info["moc_ready"]:
            print(f"  {domain} ({count} concepts)")
        print()


def print_topic_candidates(candidates: list[dict]) -> None:
    """Print topic emergence candidates."""
    print("=== Topic Candidates ===")
    print()
    if not candidates:
        print("  No topic candidates found.")
        print()
        return

    for i, cand in enumerate(candidates, 1):
        print(f"  {i}. Topic candidate in domain '{cand['domain']}' ({cand['size']} concepts)")
        print(f"     Common tags: {', '.join(cand['common_tags']) or '(none)'}")
        print(f"     Concepts: {', '.join(cand['concepts'])}")
        print()


def print_duplicate_candidates(duplicates: list[dict]) -> None:
    """Print potential duplicate concept pairs."""
    print("=== Duplicate Candidates ===")
    print()
    if not duplicates:
        print("  No potential duplicates found.")
        print()
        return

    for d in duplicates:
        print(f"  {d['concept_a']}  <-->  {d['concept_b']}")
        print(f"    Shared tags: {', '.join(d['shared_tags'])}")
        print(f"    Title overlap: {', '.join(d['title_overlap'])}")
        print()


def print_cross_linking(linking: dict) -> None:
    """Print cross-linking density report."""
    print("=== Cross-Linking Density ===")
    print()
    print(f"  Total concepts: {linking['total_concepts']}")
    print(f"  Avg outbound links (to other concepts): {linking['avg_outbound']}")
    print(f"  Avg inbound links (from other concepts): {linking['avg_inbound']}")
    print()

    if linking["weakly_linked"]:
        print(f"  Weakly linked (<2 outbound concept links): {len(linking['weakly_linked'])}")
        for slug in linking["weakly_linked"]:
            print(f"    - {slug}")
        print()

    if linking["unlinked_same_domain"]:
        print(f"  Unlinked pairs in same domain (top {len(linking['unlinked_same_domain'])}):")
        for a, b, domain in linking["unlinked_same_domain"]:
            print(f"    - {a} <-/-> {b}  ({domain})")
        print()


def print_full_dashboard(domain_info: dict, topic_cands: list[dict],
                         duplicates: list[dict], linking: dict) -> None:
    """Print the full wiki health dashboard."""
    print("=" * 60)
    print("  WIKI ANALYSIS DASHBOARD")
    print("=" * 60)
    print()
    print_domain_status(domain_info)
    print_topic_candidates(topic_cands)
    print_duplicate_candidates(duplicates)
    print_cross_linking(linking)

    issues = 0
    if domain_info["moc_ready"]:
        issues += len(domain_info["moc_ready"])
    if topic_cands:
        issues += len(topic_cands)
    if duplicates:
        issues += len(duplicates)
    if linking["weakly_linked"]:
        issues += len(linking["weakly_linked"])

    print("=" * 60)
    print(f"  Total opportunities found: {issues}")
    print("=" * 60)


# --- Main CLI ---

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="analyze-wiki.py",
        description="Wiki health metrics and opportunity detection.",
    )
    parser.add_argument(
        "--domain-status", action="store_true",
        help="Show concept counts per domain and MOC threshold status",
    )
    parser.add_argument(
        "--topic-candidates", action="store_true",
        help="Find concept clusters that could become topic pages",
    )
    parser.add_argument(
        "--duplicates", action="store_true",
        help="Find potential duplicate concept pairs",
    )
    parser.add_argument(
        "--cross-linking", action="store_true",
        help="Analyze cross-linking density between concepts",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all analyses and show full dashboard",
    )
    args = parser.parse_args()

    if not any([args.domain_status, args.topic_candidates,
                args.duplicates, args.cross_linking, args.all]):
        args.all = True

    try:
        concepts = load_wiki_files("concepts")
        topics = load_wiki_files("topics")

        if not concepts:
            print("No concept files found in wiki/concepts/")
            return 0

        domain_info = analyze_domains(concepts)
        topic_cands = find_topic_candidates(concepts, topics)
        duplicates = find_duplicate_candidates(concepts)
        linking = analyze_cross_linking(concepts)

        if args.all:
            print_full_dashboard(domain_info, topic_cands, duplicates, linking)
        else:
            if args.domain_status:
                print_domain_status(domain_info)
            if args.topic_candidates:
                print_topic_candidates(topic_cands)
            if args.duplicates:
                print_duplicate_candidates(duplicates)
            if args.cross_linking:
                print_cross_linking(linking)

        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
