"""wiki_validator.py — Shared validation library for personal wiki files.

Provides functions to parse and validate YAML frontmatter, check file
naming conventions, extract backlinks, and verify structural requirements
for wiki concept and summary files.

Uses only the Python standard library (no external dependencies).
"""

import re
from typing import List

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
