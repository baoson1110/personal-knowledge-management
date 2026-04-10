---
inclusion: always
---

# Wiki Conventions

Rules governing wiki file formats, naming, structure, and cross-referencing. These conventions apply to all LLM-generated wiki content.

## File Naming Conventions

All wiki filenames MUST be lowercase hyphen-separated slugs matching the pattern:

```
[a-z0-9]+(-[a-z0-9]+)*.md
```

Examples: `transformer-architecture.md`, `self-attention.md`, `scaling-laws.md`

Output files follow date-stamped patterns:
- Reports: `report-<slug>-YYYY-MM-DD.md` in `outputs/reports/`
- Notes: `note-<slug>-YYYY-MM-DD.md` in `outputs/notes/`

## YAML Frontmatter Schema

Every wiki markdown file MUST begin with a YAML frontmatter block containing all 7 required fields:

```yaml
---
title: "Human-readable title"
domain: "domain-slug"
tags: [tag1, tag2, tag3]
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
source: "raw/path/to/source.md"
confidence: high
---
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Human-readable page title |
| `domain` | string | Owning domain slug (e.g. `machine-learning`) |
| `tags` | list | Keyword tags for categorization |
| `created` | string | ISO date when the file was first created |
| `updated` | string | ISO date of the most recent modification |
| `source` | string | Path to the raw source, or `"web search YYYY-MM-DD"` for web-imputed content |
| `confidence` | enum | One of: `high`, `medium`, `low` |

### Confidence Levels

- **high** — content derives directly from a raw source document in `raw/`
- **medium** — content derives from a single secondary source (not a primary raw source)
- **low** — content is web-imputed, skeleton placeholder, or otherwise unverified

## Backlink Syntax

All internal cross-references between wiki pages MUST use Obsidian-compatible double-bracket backlink syntax:

```
[[concept-name]]
```

- Use the filename slug without the `.md` extension
- Every new wiki file MUST link to at least 1 existing wiki file
- Every concept file MUST be reachable from `wiki/index.md` in at most 2 hops

## Tag Registry (`wiki/tags.yml`)

A canonical tag registry lives at `wiki/tags.yml`. It is the single source of truth for all tags used in wiki frontmatter.

- Every tag in a `tags:` frontmatter field MUST exist as a canonical entry in `wiki/tags.yml`.
- Common abbreviations and synonyms are listed as `aliases:` under their canonical tag (e.g. `rl` is an alias of `reinforcement-learning`).
- When writing new wiki files, always check the registry and use the canonical form.
- If a genuinely new tag is needed, add it to the registry first, then use it.
- Lint check #9 will flag alias violations (auto-fixable) and unregistered tags.

## Concept Files (`wiki/concepts/`)

- One atomic idea per file
- Maximum **150 lines** per concept file
- Must include a `domain:` frontmatter field identifying the owning domain MOC
- Filename is the concept slug: `<concept-slug>.md`

## Summary Files (`wiki/summaries/`)

Every summary file MUST contain these four sections:

1. **Executive Summary** — concise overview of the source
2. **Deep Analysis** — detailed breakdown of key content
3. **Key Insights** — the most important takeaways
4. **Related Concepts** — list of related concept links using `[[backlink]]` syntax

## Topic Files (`wiki/topics/`)

Topic files aggregate and connect multiple concepts into a broader theme. They serve as entry points for understanding a subject area that spans several atomic concepts.

### Classification Rule

- If the content describes a **single atomic idea** → create a concept file in `wiki/concepts/`
- If the content **aggregates, compares, or connects multiple concepts** → create a topic file in `wiki/topics/`
- **Never place wiki content files at the wiki root** — only `wiki/index.md` lives there

### Requirements

- Filename is the topic slug: `<topic-slug>.md`
- Must include valid YAML frontmatter with all 7 required fields
- Must link to at least 2 concept files via `[[backlinks]]`
- Should provide comparative analysis, selection guidance, or a unifying narrative across the linked concepts

## Index File

- `wiki/index.md` — catalog of all wiki pages, each with a `[[link]]` and a one-line summary, organized by category (Concepts, Summaries, Topics, Domains)
- `wiki/index.md` MUST be updated after every ingest, file-back, or lint operation

## Domain Maps of Content (`wiki/domains/`)

Domain MOC files MUST contain:
- Domain overview
- List of all concept files in the domain with `[[links]]`
- List of related topic files
- Bridge notes to other domains

A domain MOC is created when 10+ concept files share the same `domain:` value.
