---
inclusion: manual
---

# Lint Rules

Rules and procedures for running wiki health checks. Activate this steering file when the user issues a `lint` or `web-impute:` command.

## Lint Checks

When the user issues a `lint` command, scan the entire `wiki/` directory and check for the following issues:

### 1. Broken Internal Links

- Scan all wiki files for `[[...]]` backlinks.
- For each backlink, verify that a corresponding `.md` file exists in the wiki.
- A link `[[concept-name]]` is broken if no file named `concept-name.md` exists in `wiki/concepts/`, `wiki/summaries/`, `wiki/topics/`, or `wiki/domains/`.
- Report each broken link with the source file and the missing target.

### 2. Orphan Files

- Build an inbound link map across all wiki files.
- A file is an orphan if it has **zero** inbound `[[...]]` links from other wiki files.
- Exclude `wiki/index.md` and `wiki/_brief.md` from orphan detection (they are structural files).
- Report each orphan file path.

### 3. Missing Frontmatter

- Check each wiki file for the 7 required YAML frontmatter fields: `title`, `domain`, `tags`, `created`, `updated`, `source`, `confidence`.
- Report each file that is missing one or more required fields, listing which fields are absent.

### 4. Missing Concept Files

- Scan all wiki files for concept names referenced via `[[...]]` backlinks.
- If a referenced concept does not have a corresponding file in `wiki/concepts/`, flag it as a missing concept.
- Exclude references that resolve to files in `wiki/summaries/`, `wiki/topics/`, or `wiki/domains/` — only flag truly missing pages.

## Skeleton Creation Rules

When lint identifies missing concept files:

1. Create skeleton concept files for at most **5** missing concepts per lint run.
2. Prioritize concepts that are referenced most frequently across wiki files.
3. Each skeleton file MUST have:
   - Valid YAML frontmatter with all 7 required fields.
   - `confidence: low` in frontmatter.
   - `source: "web search YYYY-MM-DD"` if web-imputed, or `source: "skeleton"` if not researched.
   - A `[needs verification]` placeholder in the body indicating the content is unverified.
   - At least one `[[backlink]]` to an existing wiki file.
4. Skeleton files are placed in `wiki/concepts/<concept-slug>.md`.
5. If more than 5 concepts are missing, report the remaining ones and let the user decide.

## Web-Impute Rules

When the user issues a `web-impute: <topic>` command:

1. Create a skeleton concept file at `wiki/concepts/<topic-slug>.md`.
2. Research the topic using web search.
3. Fill in the concept file with researched content.
4. Set frontmatter fields:
   - `confidence: low`
   - `source: "web search YYYY-MM-DD"` (using today's date)
5. Include `[needs verification]` markers on any claims that could not be confirmed from multiple sources.
6. Add `[[backlinks]]` to related existing wiki pages.

## Brief Update After Lint

After the lint run completes:

1. Update `wiki/_brief.md` to reflect any changes made during lint (new skeleton files, fixed links).
2. Update `wiki/index.md` to include entries for any newly created skeleton concept files.
3. Update the `updated:` frontmatter field in both files.

## Lint Summary Report

After all checks and fixes are complete, report a summary to the user:

- **Broken links found**: count and list of broken `[[...]]` references.
- **Orphan files found**: count and list of files with no inbound links.
- **Missing frontmatter**: count and list of files with incomplete frontmatter.
- **Missing concepts detected**: count and list of referenced concepts without files.
- **Skeleton concepts created**: count and list of new skeleton files created (up to 5).
- **Links fixed**: count of any links that were corrected.
- **Brief and index updated**: confirmation that both were refreshed.
