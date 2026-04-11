---
inclusion: manual
---

# Query Workflow

Procedure for answering user queries and generating reports from wiki content. Activate this steering file when the user issues a `query:` or `report:` command.

## Step 1 — Load Context

1. Read `wiki/index.md` to understand the wiki's current coverage and identify candidate pages by title and summary.

## Step 2 — Search the Wiki

1. Search `wiki/` for pages relevant to the user's question.
2. Use `wiki/index.md` entries to identify the most relevant concept, summary, and topic files.
3. Read the most relevant concept files, summary files, and topic files.
4. Follow `[[backlinks]]` to discover related pages that may contain supporting information.
5. If available, use `tools/search.py` for full-text search across wiki files.

## Step 3 — Synthesize the Answer

1. Base the answer **solely** on wiki content. Do NOT introduce information that is absent from the wiki.
2. Synthesize information across multiple wiki pages when the question spans several concepts.
3. Resolve any apparent contradictions between wiki pages by noting both perspectives and their sources.

### Citation Rules

- Every factual claim in the answer MUST include a citation to the specific wiki file(s) it derives from.
- Use the format: `(see [[concept-name]])` or `(source: [[summary-name]])` for inline citations.
- At the end of the answer, list all wiki files consulted under a **Sources** heading.

### When the Wiki Doesn't Cover the Topic

- If the wiki does not contain information relevant to the query, **explicitly state** that the wiki does not cover this topic.
- Offer to research the topic and add it to the wiki via the ingest or web-impute workflow.
- Do NOT fabricate an answer from outside knowledge. The wiki is the single source of truth for queries.

## Step 4 — Report Generation

When the user issues a `report: <topic>` command:

1. Generate a markdown report file at `outputs/reports/report-<topic-slug>-YYYY-MM-DD.md`.
2. Use lowercase hyphen-separated slugs for the topic portion of the filename.
3. Use today's date in `YYYY-MM-DD` format.
4. The report MUST include:
   - A title and date header.
   - Synthesized content drawn from wiki pages.
   - Inline citations to wiki files using `[[backlink]]` syntax.
   - A **Sources** section listing all wiki files consulted.

## Step 5 — File-Back Candidate Identification

After generating a report:

1. Review the report content for insights, analyses, or connections that are **not yet captured** in the wiki.
2. Present these as **file-back candidates** to the user — new concepts, updated summaries, or revised topic pages that could enrich the wiki.
3. Format the candidates as a checklist:
   - `[ ] New concept: <concept-name>` — for insights that warrant a new concept file.
   - `[ ] Update: [[existing-page]]` — for existing pages that should be enriched with new information.
4. Let the user decide which candidates to file back. Do not auto-file without confirmation.
5. If the user approves, follow the file-back-workflow steering file to execute the file-back.
