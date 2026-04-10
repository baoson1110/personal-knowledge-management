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

Identify between **1 and 3** macro concepts from the source using the heuristics below.

### Concept Identification Heuristics

- Extract a **BROAD** concept if the source introduces a field, paradigm, or framework (e.g., "reinforcement-learning", "agent-first-engineering"). Broad concepts define a category that other concepts belong to.
- Extract **NARROW** concepts for novel techniques, methods, or ideas that have their own identity and could be referenced independently (e.g., "actor-critic", "activation-steering"). A narrow concept is something another article might link to.
- Do **NOT** extract a concept for something that is merely a supporting detail, example, or illustration within the source. If it only makes sense in the context of this one article, it belongs in the summary, not as a standalone concept.
- When in doubt, prefer fewer, richer concepts over more, thinner ones. A concept file should have enough substance to stand alone.

### Deduplication Before Creation

Before creating any new concept file:

1. Search `wiki/concepts/` for files with overlapping title, tags, or domain.
2. Run `python3 tools/search.py "<concept name>"` to find existing pages that may cover the same idea.
3. If a matching concept exists, **UPDATE** it with new information from this source rather than creating a duplicate. Update the `updated:` and add the new source as a secondary reference in the body.
4. Prefer updating 2 existing concepts + creating 1 new one over creating 3 entirely new concepts.

### Concept File Requirements

- For each concept, create or update a file at `wiki/concepts/<concept-slug>.md`.
- Each concept file MUST have:
  - Valid YAML frontmatter with all 7 required fields.
  - A `domain:` frontmatter field identifying the owning domain.
  - `confidence: high` and `source:` pointing to the raw file.
  - At most **150 lines**.
  - At least one `[[backlink]]` to an existing wiki file.
- Use lowercase hyphen-separated slugs for filenames.

## Step 4 — Cross-Link Related Concepts

After creating or updating concepts, perform a cross-linking pass:

1. For each concept created or updated in this ingest, identify related concepts by checking:
   - Same `domain:` value
   - Overlapping tags (2+ shared tags)
   - Concepts mentioned in the summary's "Related Concepts" section
2. For each related concept found, check if a `[[backlink]]` already exists between the two.
3. If no link exists, add a `[[backlink]]` in the "See Also" section of both concept files (bidirectional linking).
4. Do NOT add links that are semantically irrelevant — only link concepts that a reader would benefit from navigating between.

## Step 5 — Check for Topic Emergence

After concept creation and cross-linking, check if a new topic page should be suggested:

1. Run `python3 tools/analyze-wiki.py --topic-candidates` to identify concept clusters.
2. A topic candidate exists when **3+ concepts** share the same domain AND are thematically related (overlapping tags or mutual backlinks) AND no existing topic file already covers this cluster.
3. If a topic candidate is found, include it in the Post-Flight report as a suggestion:
   - `Topic candidate: <topic-name>` — list the concepts it would connect.
4. Do NOT auto-create topic files during ingest. Present them as suggestions for the user to approve.

## Step 6 — Update the Domain MOC

- Determine the `domain:` value assigned to the new concept files.
- Run `python3 tools/analyze-wiki.py --domain-status` to check concept counts per domain.
- If a domain MOC exists at `wiki/domains/<domain-slug>.md`, add links to the new summary and concept files in the appropriate sections.
- If no domain MOC exists yet and there are now 10+ concept files sharing this domain, create one with:
  - Domain overview
  - List of all concept files in the domain with `[[links]]`
  - List of related topic files
  - Bridge notes to other domains
- If fewer than 10 concepts share the domain and no MOC exists, skip MOC creation.

## Step 7 — Update Index

- **`wiki/index.md`**: Add entries for the new summary and concept files under the appropriate sections (Concepts, Summaries). Each entry needs a `[[link]]` and a one-line summary. Update the `updated:` frontmatter field.
- The index MUST be updated before reporting completion.

## Step 8 — Update the Compile Manifest

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

- Report a summary of what was created: number of concept files (new vs. updated), summary file path, whether the domain MOC was updated or created, and the key insight.
- Report cross-links added: list any new bidirectional links created between concepts.
- Report topic candidates: if the topic emergence check found candidates, list them with the concepts they would connect. Ask the user if they want to create any.
- Report domain status: if any domain is approaching the 10-concept threshold (8+), mention it.
- If any issues were encountered (e.g. ambiguous domain, overlapping concepts, potential duplicates), note them for the user.
