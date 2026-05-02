"""wiki_validator.py — Shared validation library for personal wiki files.

Provides functions to parse and validate YAML frontmatter, check file
naming conventions, extract backlinks, verify structural requirements
for wiki concept and summary files, and validate tags against the
canonical tag registry (wiki/tags.yml).

Uses only the Python standard library (no external dependencies).
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --- Constants ---

REQUIRED_FRONTMATTER_FIELDS = [
    "title",
    "domain",
    "tags",
    "created",
    "updated",
    "source",
    "confidence",
]

VALID_CONFIDENCE_VALUES = {"high", "medium", "low"}

# Wiki filename: lowercase hyphen-separated slug
_WIKI_FILENAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.md$")

# Output filename: report-<slug>-YYYY-MM-DD.md or note-<slug>-YYYY-MM-DD.md
_OUTPUT_FILENAME_RE = re.compile(
    r"^(report|note)-[a-z0-9]+(-[a-z0-9]+)*-\d{4}-\d{2}-\d{2}\.md$"
)

# Backlink pattern: [[...]]
_BACKLINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

SUMMARY_REQUIRED_SECTIONS = [
    "Executive Summary",
    "Deep Analysis",
    "Key Insights",
]

# We check for a "related concepts" section with case-insensitive matching
_RELATED_CONCEPTS_PATTERN = re.compile(r"related\s+concepts", re.IGNORECASE)

CONCEPT_MAX_LINES = 150


# --- Frontmatter Parsing & Validation ---


def parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from markdown text.

    Extracts the block between the opening and closing ``---`` delimiters.
    Handles simple ``key: value`` pairs and bracket-list values like
    ``tags: [a, b, c]``.  Returns an empty dict if no frontmatter is found.
    """
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

        # Handle bracket-list values: [tag1, tag2, tag3]
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


def validate_frontmatter(fm: dict) -> List[str]:
    """Return a list of error messages for missing or invalid frontmatter fields.

    Checks that all 7 required fields are present and that ``confidence``
    has a valid value (``high``, ``medium``, or ``low``).
    """
    errors: List[str] = []

    for field in REQUIRED_FRONTMATTER_FIELDS:
        if field not in fm:
            errors.append(f"Missing required field: {field}")
        elif isinstance(fm[field], str) and not fm[field]:
            errors.append(f"Empty required field: {field}")

    # Validate confidence value if present
    if "confidence" in fm:
        conf = fm["confidence"]
        if isinstance(conf, str):
            conf = conf.strip().lower()
        if conf not in VALID_CONFIDENCE_VALUES:
            errors.append(
                f"Invalid confidence value: '{fm['confidence']}' "
                f"(must be one of: {', '.join(sorted(VALID_CONFIDENCE_VALUES))})"
            )

    # Validate tags is a list
    if "tags" in fm and not isinstance(fm["tags"], list):
        errors.append("Field 'tags' must be a list")

    return errors


# --- Confidence Validation ---


def validate_confidence(confidence: str) -> bool:
    """Check if *confidence* is one of the valid values (high, medium, low)."""
    return isinstance(confidence, str) and confidence.strip().lower() in VALID_CONFIDENCE_VALUES


# --- Filename Validation ---


def validate_wiki_filename(filename: str) -> bool:
    """Check *filename* against the wiki naming pattern.

    Valid pattern: ``[a-z0-9]+(-[a-z0-9]+)*\\.md``
    Examples: ``self-attention.md``, ``scaling-laws.md``, ``transformers.md``
    """
    return bool(_WIKI_FILENAME_RE.match(filename))


def validate_output_filename(filename: str) -> bool:
    """Check *filename* against output naming patterns.

    Valid patterns:
    - ``report-<slug>-YYYY-MM-DD.md``
    - ``note-<slug>-YYYY-MM-DD.md``
    """
    return bool(_OUTPUT_FILENAME_RE.match(filename))


# --- Backlink Extraction ---


def extract_backlinks(text: str) -> List[str]:
    """Extract all ``[[...]]`` backlink references from *text*.

    Returns a list of the inner text of each backlink (without brackets),
    in the order they appear.  Duplicates are preserved.
    """
    return _BACKLINK_RE.findall(text)


# --- Concept File Validation ---


def validate_concept_length(text: str) -> bool:
    """Check that *text* has at most 150 lines (concept file limit)."""
    return len(text.splitlines()) <= CONCEPT_MAX_LINES


# --- Summary File Validation ---


def validate_summary_sections(text: str) -> List[str]:
    """Return a list of missing required sections in a summary file.

    Required sections:
    - Executive Summary
    - Deep Analysis
    - Key Insights
    - Related Concepts (case-insensitive match)
    """
    missing: List[str] = []

    for section in SUMMARY_REQUIRED_SECTIONS:
        # Match as a markdown heading (## Section Name) or just the text
        if section not in text:
            missing.append(section)

    # Check for "related concepts" with case-insensitive matching
    if not _RELATED_CONCEPTS_PATTERN.search(text):
        missing.append("Related Concepts")

    return missing


# --- Tag Registry ---

_TAG_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "vault" / "wiki" / "tags.yml"


def _parse_tags_yml(text: str) -> Tuple[Dict[str, dict], Dict[str, str]]:
    """Parse the tags.yml file into (canonical_map, alias_map).

    canonical_map: {canonical_tag: {aliases: [...], domain: ...}}
    alias_map:     {alias: canonical_tag}

    This is a minimal YAML-subset parser — handles only the flat structure
    used by tags.yml so we don't need PyYAML.
    """
    canonical_map: Dict[str, dict] = {}
    alias_map: Dict[str, str] = {}
    current_tag: Optional[str] = None

    for line in text.splitlines():
        stripped = line.strip()
        # Skip comments and blank lines
        if not stripped or stripped.startswith("#"):
            continue
        # Top-level key (no leading whitespace, ends with ':')
        if not line[0].isspace() and stripped.endswith(":"):
            current_tag = stripped[:-1].strip()
            canonical_map[current_tag] = {"aliases": [], "domain": ""}
            continue
        # Nested key under current tag
        if current_tag and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if key == "domain":
                canonical_map[current_tag]["domain"] = val
            elif key == "aliases":
                # Parse [a, b, c] list
                if val.startswith("[") and val.endswith("]"):
                    aliases = [
                        a.strip().strip('"').strip("'")
                        for a in val[1:-1].split(",")
                        if a.strip()
                    ]
                    canonical_map[current_tag]["aliases"] = aliases
                    for alias in aliases:
                        alias_map[alias] = current_tag

    return canonical_map, alias_map


def load_tag_registry(
    registry_path: Optional[Path] = None,
) -> Tuple[Dict[str, dict], Dict[str, str]]:
    """Load the canonical tag registry from wiki/tags.yml.

    Returns (canonical_map, alias_map).
    Raises FileNotFoundError if the registry file is missing.
    """
    path = registry_path or _TAG_REGISTRY_PATH
    text = path.read_text(encoding="utf-8")
    return _parse_tags_yml(text)


def validate_tags(
    tags: List[str],
    canonical_map: Dict[str, dict],
    alias_map: Dict[str, str],
) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Validate a list of tags against the canonical registry.

    Returns:
      unregistered: tags not found in canonical_map or alias_map
      alias_hits:   [(used_alias, canonical_tag), ...] for tags that
                    should be replaced with their canonical form
    """
    unregistered: List[str] = []
    alias_hits: List[Tuple[str, str]] = []

    for tag in tags:
        if tag in canonical_map:
            continue  # canonical — all good
        if tag in alias_map:
            alias_hits.append((tag, alias_map[tag]))
        else:
            unregistered.append(tag)

    return unregistered, alias_hits
