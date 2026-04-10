---
inclusion: manual
---

# File-Back Workflow

Procedure for folding insights from outputs (reports, notes) back into the wiki. Activate this steering file when the user issues a `file-back: <output-file>` command.

## Pre-Flight Check

1. Read `tools/.fileback-manifest.json` and look up the specified output file.
2. If the output status is `filed`, report: "Already filed back — no action taken." Do NOT duplicate content in the wiki. Stop here.
3. If the output is not in the manifest or status is `pending`, proceed with the file-back.

## Step 1 — Read the Output

- Read the full contents of the specified output file (e.g. `outputs/reports/report-topic-2025-01-20.md`).
- Identify the key insights, analyses, and connections presented in the output.

## Step 2 — Identify New Insights

1. Read `wiki/index.md` to understand current wiki coverage.
2. Compare the output's content against existing wiki pages.
3. Run `python3 tools/search.py "<key terms>"` to find existing pages that may already cover the insights.
4. Identify insights that are **not yet present** in the wiki:
   - New concepts not covered by any existing concept file.
   - New information that extends or refines existing concept or summary files.
   - New connections between existing concepts not yet documented.
5. Check if the output reveals topic-level connections (comparisons, selection guides, unifying narratives across 3+ concepts). If so, consider creating or updating a topic file in `wiki/topics/`.

### Deduplication Rules

- Before creating a new concept file, check `wiki/concepts/` for existing files that cover the same topic.
- Search for similar titles, overlapping tags, and related domain values.
- If an existing file covers the topic, **update** it with the new insights rather than creating a duplicate.
- If the new insight is a minor addition, append it to the relevant existing file's content.
- Only create a new concept file when the insight represents a genuinely distinct concept not covered elsewhere.

## Step 3 — Update or Create Wiki Pages

For each new insight identified:

1. **Update existing files**: If the insight extends an existing concept or summary, add the new information to that file. Update the `updated:` frontmatter field.
2. **Create new concept files**: If the insight is a new concept, create a file at `wiki/concepts/<concept-slug>.md` with:
   - Valid YAML frontmatter with all 7 required fields.
   - `confidence: medium` (derived from a secondary source — the output).
   - `source:` set to the output file path.
   - At least one `[[backlink]]` to an existing wiki file.
   - Maximum 150 lines.

## Step 4 — Cross-Link and Check Domain Status

1. For each concept created or updated, run the cross-linking pass:
   - Check for other concepts with the same domain or overlapping tags.
   - Add bidirectional `[[backlinks]]` where semantically relevant links are missing.
2. Run `python3 tools/analyze-wiki.py --domain-status` to check if any domain now qualifies for a MOC.
3. If a domain has 10+ concepts and no MOC, create the domain MOC file.

## Step 5 — Update Index

1. **`wiki/index.md`**: Add entries for any new wiki files created. Update summaries for any modified files. Update the `updated:` frontmatter field.
2. The index MUST be updated before reporting completion.

## Step 6 — Update the File-Back Manifest

Update `tools/.fileback-manifest.json` with the filed output:

```json
{
  "status": "filed",
  "filed_at": "<ISO 8601 timestamp>",
  "wiki_files_updated": [
    "wiki/concepts/<concept1>.md",
    "wiki/concepts/<concept2>.md"
  ]
}
```

- Set `status` to `"filed"`.
- Set `filed_at` to the current ISO 8601 timestamp.
- List all wiki files that were created or updated in `wiki_files_updated`.

## Post-Flight

Report a summary of what was filed back:

- Number of existing wiki files updated.
- Number of new concept files created.
- List of all wiki files touched.
- Confirmation that the index was updated.
- If no new insights were found, report: "No new insights to file back — output content is already covered in the wiki."
