"""link_graph.py — Link graph analysis library for the personal wiki.

Builds a directed graph of all ``[[...]]`` backlinks across wiki files and
provides functions to detect broken links, orphan files, concept
reachability from the index, and index completeness.

Uses only the Python standard library (no external dependencies).
Reuses ``extract_backlinks`` from ``tools/wiki_validator.py``.
"""

from __future__ import annotations

import os
from collections import deque
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Import the shared backlink extractor
import sys as _sys

_tools_dir = str(Path(__file__).resolve().parent)
if _tools_dir not in _sys.path:
    _sys.path.insert(0, _tools_dir)

from wiki_validator import extract_backlinks  # noqa: E402


def _slug_from_path(filepath: Path, wiki_dir: Path) -> str:
    """Derive a slug from a wiki file path.

    The slug is the filename without the ``.md`` extension.
    For example ``wiki/concepts/self-attention.md`` → ``self-attention``.
    """
    return filepath.stem


def _collect_md_files(wiki_dir: Path) -> List[Path]:
    """Return all ``.md`` files under *wiki_dir* (recursive)."""
    md_files: List[Path] = []
    for root, _dirs, files in os.walk(wiki_dir):
        for fname in files:
            if fname.endswith(".md"):
                md_files.append(Path(root) / fname)
    return md_files


# ---------------------------------------------------------------------------
# 1. build_link_graph
# ---------------------------------------------------------------------------

def build_link_graph(wiki_dir: Path) -> dict:
    """Walk all ``.md`` files in *wiki_dir*, extract ``[[...]]`` links, and
    return a graph dict with:

    - ``nodes``: set of all file slugs found in the wiki directory
    - ``edges``: dict mapping *source slug* → set of *target slugs*
    - ``inbound``: dict mapping *target slug* → set of *source slugs*
    """
    nodes: Set[str] = set()
    edges: Dict[str, Set[str]] = {}
    inbound: Dict[str, Set[str]] = {}

    md_files = _collect_md_files(wiki_dir)

    # Register every .md file as a node
    for fpath in md_files:
        slug = _slug_from_path(fpath, wiki_dir)
        nodes.add(slug)

    # Build edges from backlinks
    for fpath in md_files:
        slug = _slug_from_path(fpath, wiki_dir)
        text = fpath.read_text(encoding="utf-8", errors="replace")
        targets = extract_backlinks(text)

        target_set: Set[str] = set()
        for target in targets:
            target_set.add(target)
            # Update inbound map
            if target not in inbound:
                inbound[target] = set()
            inbound[target].add(slug)

        edges[slug] = target_set

    return {
        "nodes": nodes,
        "edges": edges,
        "inbound": inbound,
    }


# ---------------------------------------------------------------------------
# 2. find_broken_links
# ---------------------------------------------------------------------------

def find_broken_links(graph: dict) -> List[Tuple[str, str]]:
    """Return a list of ``(source_slug, target_slug)`` pairs where the
    *target_slug* does not correspond to any file in the wiki.

    A link is "broken" when the target slug is not in ``graph["nodes"]``.
    """
    nodes: Set[str] = graph["nodes"]
    edges: Dict[str, Set[str]] = graph["edges"]
    broken: List[Tuple[str, str]] = []

    for source, targets in edges.items():
        for target in sorted(targets):
            if target not in nodes:
                broken.append((source, target))

    return broken


# ---------------------------------------------------------------------------
# 3. find_orphan_files
# ---------------------------------------------------------------------------

def find_orphan_files(graph: dict) -> List[str]:
    """Return slugs that have zero inbound links from other wiki files.

    Excludes ``"index"`` since it is a structural file
    that is not expected to be linked *to* by other pages.
    """
    nodes: Set[str] = graph["nodes"]
    inbound: Dict[str, Set[str]] = graph["inbound"]
    excluded = {"index"}

    orphans: List[str] = []
    for slug in sorted(nodes):
        if slug in excluded:
            continue
        sources = inbound.get(slug, set())
        if len(sources) == 0:
            orphans.append(slug)

    return orphans


# ---------------------------------------------------------------------------
# 4. check_concept_reachability
# ---------------------------------------------------------------------------

def check_concept_reachability(graph: dict, concepts_dir: Path) -> List[str]:
    """Return concept slugs that are NOT reachable from ``"index"`` in ≤2 hops.

    A concept is reachable if there is a path of length 1 or 2 in the
    directed edge graph starting from the ``"index"`` node.

    *concepts_dir* is used to determine which slugs are concept files
    (i.e. files that live in ``wiki/concepts/``).
    """
    edges: Dict[str, Set[str]] = graph["edges"]

    # Collect concept slugs from the concepts directory
    concept_slugs: Set[str] = set()
    if concepts_dir.is_dir():
        for fname in os.listdir(concepts_dir):
            if fname.endswith(".md"):
                concept_slugs.add(Path(fname).stem)

    if not concept_slugs:
        return []

    # BFS from "index" up to depth 2
    reachable: Set[str] = set()
    queue: deque[Tuple[str, int]] = deque()
    queue.append(("index", 0))
    visited: Set[str] = {"index"}

    while queue:
        node, depth = queue.popleft()
        if depth > 2:
            continue
        for neighbor in edges.get(node, set()):
            reachable.add(neighbor)
            if neighbor not in visited and depth + 1 <= 2:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    unreachable = sorted(concept_slugs - reachable)
    return unreachable


# ---------------------------------------------------------------------------
# 5. check_index_completeness
# ---------------------------------------------------------------------------

def check_index_completeness(graph: dict) -> List[str]:
    """Return slugs of wiki pages that do NOT have an entry (link) in
    ``index.md``.

    A page "has an entry" if the ``"index"`` node's outbound edges contain
    a link to that page's slug.  ``index`` is excluded
    from the check since it is a structural file.
    """
    nodes: Set[str] = graph["nodes"]
    edges: Dict[str, Set[str]] = graph["edges"]
    excluded = {"index"}

    index_links = edges.get("index", set())

    missing: List[str] = []
    for slug in sorted(nodes):
        if slug in excluded:
            continue
        if slug not in index_links:
            missing.append(slug)

    return missing
