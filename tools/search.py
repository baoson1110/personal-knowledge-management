#!/usr/bin/env python3
"""search.py — BM25-style full-text search across wiki markdown files.

Accepts a query string, tokenizes it and all wiki .md files, computes
BM25-style TF-IDF scores, and returns the top results ranked by
relevance with file path, title, and a matching snippet.

Uses only the Python standard library (no external dependencies).
"""

import argparse
import math
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
WIKI_DIR = REPO_ROOT / "wiki"

MAX_RESULTS = 10
SNIPPET_MAX_LEN = 120

# BM25 parameters
K1 = 1.2
B = 0.75

# Tokenisation pattern: split on non-alphanumeric characters
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase and split text on whitespace/punctuation."""
    return _TOKEN_RE.findall(text.lower())


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract simple YAML frontmatter key-value pairs."""
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


def body_lines(text: str) -> list[str]:
    """Return content lines after frontmatter."""
    lines = text.splitlines()
    in_fm = False
    start = 0
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_fm = True
            continue
        if in_fm and line.strip() == "---":
            start = i + 1
            break
    return lines[start:]


def find_snippet(lines: list[str], query_tokens: set[str]) -> str:
    """Return the first line containing a query term, truncated."""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        line_lower = stripped.lower()
        for token in query_tokens:
            if token in line_lower:
                if len(stripped) > SNIPPET_MAX_LEN:
                    return stripped[: SNIPPET_MAX_LEN - 3] + "..."
                return stripped
    return ""


def collect_documents() -> list[dict]:
    """Walk all .md files under wiki/ and return document dicts.

    Each dict has keys: path, title, tokens, lines, token_count.
    Skips files starting with . and .gitkeep files.
    """
    docs: list[dict] = []
    if not WIKI_DIR.is_dir():
        return docs
    for fpath in sorted(WIKI_DIR.rglob("*.md")):
        if fpath.name.startswith("."):
            continue
        try:
            content = fpath.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = parse_frontmatter(content)
        title = fm.get("title", fpath.stem)
        lines = body_lines(content)
        body_text = " ".join(lines)
        tokens = tokenize(title + " " + body_text)
        rel_path = str(fpath.relative_to(REPO_ROOT))
        docs.append(
            {
                "path": rel_path,
                "title": title,
                "tokens": tokens,
                "lines": lines,
                "token_count": len(tokens),
            }
        )
    return docs


def bm25_search(
    query: str, docs: list[dict]
) -> list[tuple[float, dict]]:
    """Score documents against *query* using BM25 and return ranked list."""
    query_tokens = tokenize(query)
    if not query_tokens or not docs:
        return []

    n = len(docs)
    avgdl = sum(d["token_count"] for d in docs) / n if n else 1

    # Build document-frequency map for query terms
    query_token_set = set(query_tokens)
    df: dict[str, int] = {t: 0 for t in query_token_set}
    for doc in docs:
        doc_token_set = set(doc["tokens"])
        for t in query_token_set:
            if t in doc_token_set:
                df[t] += 1

    # Compute IDF for each query term
    idf: dict[str, float] = {}
    for t in query_token_set:
        # Standard BM25 IDF: log((N - df + 0.5) / (df + 0.5) + 1)
        idf[t] = math.log((n - df[t] + 0.5) / (df[t] + 0.5) + 1.0)

    # Score each document
    scored: list[tuple[float, dict]] = []
    for doc in docs:
        score = 0.0
        dl = doc["token_count"]
        tf_map: dict[str, int] = {}
        for t in doc["tokens"]:
            if t in query_token_set:
                tf_map[t] = tf_map.get(t, 0) + 1
        for t in query_token_set:
            tf = tf_map.get(t, 0)
            if tf == 0:
                continue
            numerator = tf * (K1 + 1)
            denominator = tf + K1 * (1 - B + B * dl / avgdl)
            score += idf[t] * numerator / denominator
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:MAX_RESULTS]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="search.py",
        description="BM25-style full-text search across wiki markdown files.",
    )
    parser.add_argument(
        "query",
        help="Search query string",
    )
    args = parser.parse_args()

    try:
        docs = collect_documents()
        if not docs:
            print("No wiki files found.")
            return 0

        results = bm25_search(args.query, docs)
        if not results:
            print(f"No results for: {args.query}")
            return 0

        query_tokens = set(tokenize(args.query))
        for i, (score, doc) in enumerate(results, 1):
            snippet = find_snippet(doc["lines"], query_tokens)
            print(f"{i}. [{score:.4f}] {doc['path']}")
            print(f"   Title: {doc['title']}")
            if snippet:
                print(f"   Snippet: {snippet}")
            print()

        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
