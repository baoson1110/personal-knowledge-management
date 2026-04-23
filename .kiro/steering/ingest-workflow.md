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
- **Inventory images**: Scan the source for image references (`![[asset/...]]`). For each image found, note its path and the surrounding context (section heading, caption text, nearby paragraph). This inventory will be used in Steps 2 and 3 to carry relevant images into wiki pages.

## Step 2 — Create the Summary File

Create a single summary file at `wiki/summaries/<source-slug>.md` with:

- Valid YAML frontmatter containing all 7 required fields (`title`, `domain`, `tags`, `created`, `updated`, `source`, `confidence`).
- Set `confidence: high` (content derives directly from a raw source).
- Set `source:` to the raw file path (e.g. `raw/articles/my-article.md`).
- The body MUST contain exactly these four sections:
  1. **Executive Summary** — concise overview of the source.
  2. **Deep Analysis** — detailed breakdown of key content. Embed key diagrams and figures from the source here, placed inline near the text that discusses them. Only include informative images (diagrams, charts, architecture figures) — skip decorative ones. Every image MUST have an italicized caption on the line below describing what it shows.
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
  - Images from the source may be included if they are **closely related to the concept itself** (e.g., a defining diagram or core illustration). Prefer at most 1–2 images per concept file. Every image MUST have an italicized caption. If an image is only relevant to one source's framing, keep it in the summary instead.
- Use lowercase hyphen-separated slugs for filenames.

### Tag Registry Compliance

Before assigning tags to any new or updated wiki file:

1. Read `wiki/tags.yml` to load the canonical tag registry.
2. Every tag in the `tags:` frontmatter field MUST exist as a canonical tag in the registry.
3. If you want to use a tag that is listed as an alias (e.g. `rl`), use the canonical form instead (e.g. `reinforcement-learning`).
4. If a tag you need does not exist in the registry at all, add it to `wiki/tags.yml` in the correct alphabetical position before using it.
5. Never introduce abbreviations or synonyms of existing canonical tags — always reuse the canonical form.

## Step 4 — Cross-Link Related Concepts

After creating or updating concepts, perform a cross-linking pass:

1. For each concept created or updated in this ingest, identify related concepts by checking:
   - Same `domain:` value
   - Overlapping tags (2+ shared tags)
   - Concepts mentioned in the summary's "Related Concepts" section
2. For each related concept found, check if a `[[backlink]]` already exists between the two.
3. If no link exists, add a `[[backlink]]` in the "See Also" section of both concept files (bidirectional linking).
4. Do NOT add links that are semantically irrelevant — only link concepts that a reader would benefit from navigating between.

## Step 5 — Synthesis Pass (Topic Creation & Update)

After concept creation and cross-linking, actively synthesize overlapping content into topic pages.

### 5a — Detect Overlap Across Summaries

1. Compare the new summary against all existing summaries in the same domain.
2. Look for **content overlap signals**:
   - Two or more summaries answering the same question or explaining the same process.
   - Two or more summaries covering the same technique from different angles (e.g. theory vs. practice, overview vs. deep-dive).
   - Shared key terms, shared "Related Concepts" entries, or 2+ shared tags.
3. Run `python3 tools/analyze-wiki.py --topic-candidates` to identify concept clusters.

### 5b — Auto-Create Topic When Overlap Is Strong

A topic MUST be created (not just suggested) when ALL of the following are true:

- **2+ summaries** in the same domain discuss substantially overlapping content (same questions, same techniques, same comparisons).
- **3+ concepts** from those summaries are thematically related (overlapping tags or mutual backlinks).
- No existing topic file already covers this cluster.

When auto-creating a topic:

1. Create the file at `wiki/topics/<topic-slug>.md` with valid YAML frontmatter (all 7 required fields).
2. Set `confidence: high` and `source:` to the primary raw file that triggered the synthesis.
3. The topic body MUST include:
   - A **synthesis narrative** that unifies the overlapping content — not just a list of links, but an explanation of how the concepts relate, where they agree, and where they differ.
   - `[[backlinks]]` to all connected concept and summary files.
   - A Mermaid diagram if the relationships or processes involved benefit from visual illustration.
   - A "See Also" section linking to related topics or domains.
4. Update the linked concept files to add a backlink to the new topic in their "See Also" sections.

### 5c — Update Existing Topics

If an existing topic file already covers the cluster but the new summary adds new perspectives or information:

1. Update the topic file with the new insights.
2. Add backlinks to the new summary and any new concepts.
3. Update the `updated:` frontmatter field.

### 5d — Suggest Topics When Overlap Is Weaker

If the overlap signals are present but do not meet the auto-creation threshold (e.g. only 2 related concepts, or summaries overlap on a subtopic rather than a main theme):

1. Include it in the Post-Flight report as a suggestion:
   - `Topic candidate: <topic-name>` — list the concepts and summaries it would connect, and describe the overlapping theme.
2. Ask the user if they want to create the topic now.

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
- Report topics created: list any topic files auto-created during the synthesis pass, with the concepts and summaries they connect.
- Report topic candidates: if the synthesis pass found weaker overlap that didn't meet the auto-creation threshold, list them with the concepts they would connect. Ask the user if they want to create any.
- Report domain status: if any domain is approaching the 10-concept threshold (8+), mention it.
- If any issues were encountered (e.g. ambiguous domain, overlapping concepts, potential duplicates), note them for the user.
