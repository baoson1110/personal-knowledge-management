---
inclusion: fileMatch
fileMatch: "raw/**"
---

# Ingest Workflow

Step-by-step procedure for compiling a raw source document into the wiki. This steering file is automatically loaded when operating on any file matching `raw/**`.

## Pre-Flight Check

1. Read `tools/.compile-manifest.json` and look up the source path.
2. If the source status is `compiled` and the file has not been modified since `compiled_at`, **skip** it. Report: "Already compiled — no changes detected." Do not proceed further.
3. If the source status is `modified` (compiled but changed since), proceed with recompilation and note it is a re-ingest.

## Step 1 — Read the Raw Source

- Read the full contents of the raw source file.
- Identify the document type (article, paper, repo README, image caption, etc.).
- Note the file path — it becomes the `source:` frontmatter value for all generated wiki files.

## Step 2 — Create the Summary File

Create a single summary file at `wiki/summaries/<source-slug>.md` with:

- Valid YAML frontmatter containing all 7 required fields (`title`, `domain`, `tags`, `created`, `updated`, `source`, `confidence`).
- Set `confidence: high` (content derives directly from a raw source).
- Set `source:` to the raw file path (e.g. `raw/articles/my-article.md`).
- The body MUST contain exactly these four sections:
  1. **Executive Summary** — concise overview of the source.
  2. **Deep Analysis** — detailed breakdown of key content.
  3. **Key Insights** — the most important takeaways.
  4. **Related Concepts** — list of related concept links using `[[backlink]]` syntax.

## Step 3 — Extract Concepts

- Identify between **1 and 3** macro concepts from the source.
- For each concept, create a file at `wiki/concepts/<concept-slug>.md`.
- Each concept file MUST have:
  - Valid YAML frontmatter with all 7 required fields.
  - A `domain:` frontmatter field identifying the owning domain.
  - `confidence: high` and `source:` pointing to the raw file.
  - At most **150 lines**.
  - At least one `[[backlink]]` to an existing wiki file.
- Use lowercase hyphen-separated slugs for filenames.
- If a concept file already exists, **update** it with new information from this source rather than creating a duplicate.

## Step 4 — Update the Domain MOC

- Determine the `domain:` value assigned to the new concept files.
- If a domain MOC exists at `wiki/domains/<domain-slug>.md`, add links to the new summary and concept files in the appropriate sections.
- If no domain MOC exists yet and there are now 10+ concept files sharing this domain, create one with:
  - Domain overview
  - List of all concept files in the domain with `[[links]]`
  - List of related topic files
  - Bridge notes to other domains
- If fewer than 10 concepts share the domain and no MOC exists, skip MOC creation.

## Step 5 — Update Index

- **`wiki/index.md`**: Add entries for the new summary and concept files under the appropriate sections (Concepts, Summaries). Each entry needs a `[[link]]` and a one-line summary. Update the `updated:` frontmatter field.
- The index MUST be updated before reporting completion.

## Step 6 — Update the Compile Manifest

Update `tools/.compile-manifest.json` with an entry for the compiled source:

```json
{
  "status": "compiled",
  "compiled_at": "<ISO 8601 timestamp>",
  "key_insight": "<one-line key takeaway>",
  "wiki_files": [
    "wiki/summaries/<slug>.md",
    "wiki/concepts/<concept1>.md",
    "wiki/concepts/<concept2>.md"
  ]
}
```

## Post-Flight

- Report a summary of what was created: number of concept files, summary file path, whether the domain MOC was updated or created, and the key insight.
- If any issues were encountered (e.g. ambiguous domain, overlapping concepts), note them for the user.
