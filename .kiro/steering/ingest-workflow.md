---
inclusion: fileMatch
fileMatch: "vault/staging/**"
---

# Ingest Workflow

Step-by-step procedure for compiling a staging source document into the wiki. This steering file is automatically loaded when operating on any file matching `vault/staging/**`.

## Pre-Flight Check

1. Run `python3 tools/scan_sources.py --json --pending` to get the list of uncompiled/modified sources (handles macOS Unicode normalization automatically).
2. Alternatively, read `tools/.compile-manifest.json` and look up the source path manually.
3. If the source status is `compiled` and the file has not been modified since `compiled_at`, **skip** it. Report: "Already compiled — no changes detected." Do not proceed further.
4. If the source status is `modified` (compiled but changed since), proceed with recompilation and note it is a re-ingest.

### Multi-Part Source Detection

After identifying the source path, check whether it is part of a **multi-part source** (e.g., a book, course, or multi-chapter guide):

- A multi-part source is a **folder** under `vault/staging/` (typically `vault/staging/books/<Title>/`) containing **2 or more related `.md` files** that form a coherent whole (chapters, lectures, parts).
- Detection signals: the source path points to a file inside a subfolder of `vault/staging/books/`, or the folder contains files with sequential naming (e.g., `ch01-`, `ch02-`, `part-1-`, `lecture-01-`).
- If the user asks to ingest a folder path (e.g., `vault/staging/books/My Book/`), treat it as a multi-part source.
- If the user asks to ingest a single file that lives inside a multi-part folder, ask: "This file is part of [Book Name] (N chapters). Ingest just this chapter, or the whole book?"

**If the source IS a multi-part source**, follow the **Multi-Part Source Workflow** below instead of Steps 1–3. Then rejoin at Step 4.

**If the source is a single file**, proceed with Steps 1–3 as normal.

## Multi-Part Source Workflow

This workflow replaces Steps 1–3 for books, courses, and other multi-chapter sources. It produces one summary per chapter plus one book-level overview, and extracts concepts per-chapter rather than per-book.

### MP-1 — Inventory the Source

1. List all `.md` files in the multi-part folder. Sort them in reading order (by filename prefix: `ch01`, `ch02`, etc.).
2. Read each chapter file. For each chapter, note:
   - Chapter number and title
   - Line count (to gauge depth)
   - Key topics covered
   - Image references (`![[vault/asset/...]]`)
3. Group chapters into **thematic clusters** — sets of 2–4 chapters that cover closely related topics. This grouping guides topic creation later. Example: chapters on tools + concurrency form a "Tool System" cluster; chapters on sub-agents + fork agents + coordination form a "Multi-Agent" cluster.

### MP-2 — Create Per-Chapter Summaries

For **each chapter**, create a summary file at:

```
vault/wiki/summaries/<book-slug>-<chapter-slug>.md
```

Example: `vault/wiki/summaries/claude-code-ch05-agent-loop.md`

Each per-chapter summary follows the same rules as Step 2 (Executive Summary, Deep Analysis, Key Insights, Related Concepts) with these adjustments:

- Set `source:` to the **individual chapter file path** (e.g., `vault/staging/books/Claude Code Design/ch05-agent-loop.md`).
- The Executive Summary should briefly note the chapter's place in the larger book (e.g., "Chapter 5 of *Claude Code Design*, covering the core agent loop").
- The Deep Analysis should be **thorough for that chapter** — this is the primary record of the chapter's content. Do not compress to make room for other chapters.
- The Related Concepts section should link to concepts from other chapters in the same book, not just external concepts.

### MP-3 — Create the Book-Level Overview Summary

After all per-chapter summaries are created, create a **book-level overview** at:

```
vault/wiki/summaries/<book-slug>.md
```

Example: `vault/wiki/summaries/claude-code-design.md`

This overview is a **synthesis**, not a concatenation. It MUST contain:

1. **Executive Summary** — what the book is about, its central thesis, intended audience, and why it matters.
2. **Chapter Map** — a brief description of each chapter (2–3 sentences each) with `[[backlinks]]` to the per-chapter summaries. This serves as a navigational table of contents.
3. **Cross-Cutting Themes** — ideas that span multiple chapters (e.g., "prompt cache as architectural constraint" appears in ch04, ch09, ch17). Explain how these themes weave through the book.
4. **Key Insights** — the book's most important takeaways, synthesized across all chapters.
5. **Related Concepts** — links to all concept files extracted from the book.

The overview should be **longer than a typical summary** — up to 200 lines is acceptable for a book with 10+ chapters.

### MP-4 — Extract Concepts Per-Chapter

For each chapter, extract **1–3 concepts** using the same heuristics as Step 3 (Concept Identification Heuristics, Deduplication Before Creation, Concept File Requirements).

Key differences from single-source ingestion:

- The **per-chapter cap is 1–3** (not 1–5), but applied to each chapter independently. For an 18-chapter book, this yields 18–54 concepts before deduplication.
- **Cross-chapter deduplication is critical.** Multiple chapters may discuss the same concept (e.g., "prompt caching" in ch04 and ch09). Deduplicate aggressively: create the concept from the chapter that covers it most deeply, then enrich it with details from other chapters. Update the `source:` to point to the primary chapter and mention secondary chapters in the body.
- Set `source:` on each concept to the **chapter file** that is the primary source for that concept.
- After all chapters are processed, review the full concept list and merge any that overlap significantly. The final count should be **roughly 1–2 concepts per chapter on average** after deduplication.

### MP-5 — Compile Manifest for Multi-Part Sources

Each chapter gets its own entry in `tools/.compile-manifest.json`, with `wiki_files` listing only the files generated from that specific chapter:

```json
{
  "vault/staging/books/Book Name/ch01-intro.md": {
    "status": "compiled",
    "compiled_at": "<ISO timestamp>",
    "key_insight": "<chapter-level insight>",
    "wiki_files": [
      "vault/wiki/summaries/book-name-ch01-intro.md",
      "vault/wiki/concepts/concept-from-ch01.md"
    ]
  }
}
```

The book-level overview summary is listed under the **first chapter's** manifest entry (or a synthetic entry keyed by the folder path).

After MP-5, **rejoin the standard workflow at Step 4** (Cross-Link Related Concepts). Steps 4–8 run once across all chapters, not per-chapter.

---

## Step 1 — Read the Staging Source

- Read the full contents of the staging source file.
- Identify the document type (article, paper, repo README, image caption, etc.).
- Note the file path — it becomes the `source:` frontmatter value for all generated wiki files.
- **Inventory images**: Scan the source for image references in both formats:
  - Obsidian wikilinks: `![[vault/asset/...]]`
  - Standard markdown: `![alt](url)`
  
  For each image found, note its path and the surrounding context (section heading, caption text, nearby paragraph). This inventory will be used in Steps 2 and 3 to carry relevant images into wiki pages.
  
  **If images are external URLs** (`![](https://...)`): The images have not been localized by the Obsidian Local Images Plus plugin. Flag this to the user: "This source has N external images. Run the Local Images Plus plugin in Obsidian first to download them to `vault/asset/`, then re-read the source." If the user cannot run the plugin, proceed without images but note in the summary that visual content is missing.

## Step 2 — Create the Summary File

Create a single summary file at `vault/wiki/summaries/<source-slug>.md` with:

- Valid YAML frontmatter containing all 7 required fields (`title`, `domain`, `tags`, `created`, `updated`, `source`, `confidence`).
- Set `confidence: high` (content derives directly from a staging source).
- Set `source:` to the staging file path (e.g. `vault/staging/articles/my-article.md`).
- The body MUST contain exactly these four sections:
  1. **Executive Summary** — concise overview of the source, including the **context**: what problem or question the source is addressing, why the topic matters, and what motivated the author to write about it.
  2. **Deep Analysis** — detailed breakdown of key content. For each major sub-topic, include the **reasoning**: why this sub-topic is discussed, how it connects to the overall argument, and what problem it solves. When the source presents a solution or recommendation, explain the problem that prompted it. **Embed ALL informative diagrams and figures from the source** — architecture diagrams, data flow charts, comparison visualizations, ablation results, mathematical graphs. Only skip purely decorative images (photos for fun, promotional images, avatars). Place each image inline near the text that discusses it. Every image MUST have an italicized caption on the line below describing what it shows and why it matters.
  3. **Key Insights** — the most important takeaways.
  4. **Related Concepts** — list of related concept links using `[[backlink]]` syntax.
- Follow the **Writing Guidance for Summaries** in wiki-conventions: context before content, reasoning chains over isolated facts, transitions between sub-topics, and preserve the "why" of recommendations.

## Step 3 — Extract Concepts

Identify between **1 and 5** macro concepts from the source using the heuristics below.

### Concept Identification Heuristics

- Extract a **BROAD** concept if the source introduces a field, paradigm, or framework (e.g., "reinforcement-learning", "agent-first-engineering"). Broad concepts define a category that other concepts belong to.
- Extract **NARROW** concepts for novel techniques, methods, or ideas that have their own identity and could be referenced independently (e.g., "actor-critic", "activation-steering"). A narrow concept is something another article might link to.
- Do **NOT** extract a concept for something that is merely a supporting detail, example, or illustration within the source. If it only makes sense in the context of this one article, it belongs in the summary, not as a standalone concept.
- When in doubt, prefer fewer, richer concepts over more, thinner ones. A concept file should have enough substance to stand alone.

### Deduplication Before Creation

Before creating any new concept file:

1. Search `vault/wiki/concepts/` for files with overlapping title, tags, or domain.
2. Run `python3 tools/search.py "<concept name>"` to find existing pages that may cover the same idea.
3. If a matching concept exists, **UPDATE** it with new information from this source rather than creating a duplicate. Update the `updated:` and add the new source as a secondary reference in the body.
4. Prefer updating 2 existing concepts + creating 1 new one over creating 3 entirely new concepts.

### Concept File Requirements

- For each concept, create or update a file at `vault/wiki/concepts/<concept-slug>.md`.
- Each concept file MUST have:
  - Valid YAML frontmatter with all 7 required fields.
  - A `domain:` frontmatter field identifying the owning domain.
  - `confidence: high` and `source:` pointing to the staging file.
  - At most **150 lines**.
  - At least one `[[backlink]]` to an existing wiki file.
  - Images from the source may be included — up to **5 images** per concept file — when they are **closely related to the concept itself** (e.g., a defining diagram, a comparison chart, a process visualization). Prioritize: (1) defining diagrams, (2) comparison charts, (3) process/flow diagrams. Every image MUST have an italicized caption. If an image is only relevant to one source's framing, keep it in the summary instead.
- Use lowercase hyphen-separated slugs for filenames.

### Tag Registry Compliance

Before assigning tags to any new or updated wiki file:

1. Read `vault/wiki/tags.yml` to load the canonical tag registry.
2. Every tag in the `tags:` frontmatter field MUST exist as a canonical tag in the registry.
3. If you want to use a tag that is listed as an alias (e.g. `rl`), use the canonical form instead (e.g. `reinforcement-learning`).
4. If a tag you need does not exist in the registry at all, add it to `vault/wiki/tags.yml` in the correct alphabetical position before using it.
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

1. Create the file at `vault/wiki/topics/<topic-slug>.md` with valid YAML frontmatter (all 7 required fields).
2. Set `confidence: high` and `source:` to the primary staging file that triggered the synthesis.
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
- Run `python3 tools/wiki_lint.py --check domains` to check concept counts per domain.
- If a domain MOC exists at `vault/wiki/domains/<domain-slug>.md`, add links to the new summary and concept files in the appropriate sections.
- If no domain MOC exists yet and there are now **5+ concept files** sharing this domain, **you MUST create one** with:
  - Domain overview
  - List of all concept files in the domain with `[[links]]`
  - List of related topic files
  - Bridge notes to other domains
- If fewer than 5 concepts share the domain and no MOC exists, skip MOC creation but note the count in Post-Flight.

**This step is NOT optional.** If the tool reports "ACTION REQUIRED", you MUST create the domain MOC before proceeding to Step 7. Do not defer this to a future lint run.

## Step 7 — Update Index

- **`vault/wiki/index.md`**: Add entries for the new summary and concept files under the appropriate sections (Concepts, Summaries). Each entry needs a `[[link]]` and a one-line summary. Update the `updated:` frontmatter field.
- The index MUST be updated before reporting completion.

## Step 8 — Update the Compile Manifest

Update `tools/.compile-manifest.json` with an entry for the compiled source:

```json
{
  "status": "compiled",
  "compiled_at": "<ISO 8601 timestamp>",
  "key_insight": "<one-line key takeaway>",
  "wiki_files": [
    "vault/wiki/summaries/<slug>.md",
    "vault/wiki/concepts/<concept1>.md",
    "vault/wiki/concepts/<concept2>.md"
  ]
}
```

## Post-Flight

Report the following items. **Every item is mandatory** — do not skip any line even if the value is "none" or "0".

- **Domain MOC status** (MUST be first line):
  - If a domain MOC was created this ingest: `✅ Domain MOC CREATED: vault/wiki/domains/<domain>.md (<N> concepts)`
  - If a domain MOC was updated: `✅ Domain MOC UPDATED: vault/wiki/domains/<domain>.md`
  - If a domain crossed the 5-concept threshold but MOC was NOT created: `❌ BLOCKED: Domain <domain> has <N> concepts but no MOC — this should not happen, Step 6 was skipped`
  - If no domain crossed the threshold: `Domain MOC: no new domains reached 5-concept threshold`
  - If any domain is approaching the threshold (3-4 concepts): `⚠ Approaching: <domain> (<N>/5 concepts)`
- **Files created**: number of concept files (new vs. updated), summary file path, and the key insight.
- **Cross-links added**: list any new bidirectional links created between concepts.
- **Topics created**: list any topic files auto-created during the synthesis pass, with the concepts and summaries they connect.
- **Topic candidates**: if the synthesis pass found weaker overlap that didn't meet the auto-creation threshold, list them with the concepts they would connect. Ask the user if they want to create any.
- If any issues were encountered (e.g. ambiguous domain, overlapping concepts, potential duplicates), note them for the user.
