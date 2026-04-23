---
inclusion: manual
---

# Lint Rules

Rules and procedures for running wiki health checks. Activate this steering file when the user issues a `lint` or `web-impute:` command.

## Available Tools

Before running ad-hoc shell commands, use the dedicated lint tools:

- **`python3 tools/wiki_lint.py`** — Checks 1-4 and 10: broken links, orphans, missing frontmatter, missing concepts, LaTeX formatting. Supports `--fix` (auto-fix LaTeX), `--check <name>` (single check), `--json` (machine-readable output).
- **`python3 tools/wiki_lint.py --fix`** — Same as above but auto-fixes LaTeX issues.
- **`python3 tools/analyze-wiki.py --all`** — Checks 5-9: topic synthesis, domain MOC readiness, duplicates, cross-linking gaps, tag registry violations.

Run both tools for a complete lint pass. The wiki_lint tool handles content-level checks; analyze-wiki handles structural/relational checks.

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
- Exclude `wiki/index.md` from orphan detection (it is a structural file).
- Report each orphan file path.

### 3. Missing Frontmatter

- Check each wiki file for the 7 required YAML frontmatter fields: `title`, `domain`, `tags`, `created`, `updated`, `source`, `confidence`.
- Report each file that is missing one or more required fields, listing which fields are absent.

### 4. Missing Concept Files

- Scan all wiki files for concept names referenced via `[[...]]` backlinks.
- If a referenced concept does not have a corresponding file in `wiki/concepts/`, flag it as a missing concept.
- Exclude references that resolve to files in `wiki/summaries/`, `wiki/topics/`, or `wiki/domains/` — only flag truly missing pages.

### 5. Topic Synthesis

Lint should actively create topic files when overlap is strong, not just report suggestions.

#### 5a — Detect Overlap

1. Run `python3 tools/analyze-wiki.py --topic-candidates` to detect concept clusters.
2. For each cluster found, check for **summary overlap**: scan summaries in the same domain for content that answers the same questions, explains the same processes, or covers the same techniques from different angles.

#### 5b — Auto-Create Topics (Strong Overlap)

A topic MUST be created when ALL of the following are true:

- **2+ summaries** in the same domain discuss substantially overlapping content.
- **3+ concepts** from those summaries are thematically related (overlapping tags or mutual backlinks).
- No existing topic file already covers this cluster.

When auto-creating:

1. Create the file at `wiki/topics/<topic-slug>.md` with valid YAML frontmatter (all 7 required fields).
2. Set `confidence: high` and `source:` to the primary summary that anchors the cluster.
3. The topic body MUST follow the Required Structure from wiki-conventions (Overview, Detailed Comparison or Narrative, Linked Pages, See Also).
4. Include a Mermaid diagram or static image if the relationships or processes benefit from visual illustration.
5. Update the linked concept files to add a backlink to the new topic in their "See Also" sections.

#### 5c — Suggest Topics (Weaker Overlap)

If overlap signals are present but do not meet the auto-creation threshold (e.g. only 2 related concepts, or summaries overlap on a subtopic rather than a main theme):

- Report as a suggestion in the lint summary: `Topic candidate: <topic-name>` — list the concepts and summaries it would connect.
- Present these as suggestions, not errors.

### 6. Domain MOC Readiness

- Run `python3 tools/analyze-wiki.py --domain-status` to check domain concept counts.
- Report any domain with 10+ concepts that lacks a domain MOC file in `wiki/domains/`.
- Report any domain with 8-9 concepts as "approaching threshold."

### 7. Duplicate Concept Detection

- Run `python3 tools/analyze-wiki.py --duplicates` to find concept pairs with high tag overlap (3+ shared tags) and similar titles (2+ shared title words).
- Report potential duplicates for manual review and merge.

### 8. Cross-Linking Gaps

- Run `python3 tools/analyze-wiki.py --cross-linking` to analyze link density.
- Report concepts with fewer than 2 outbound links to other concepts (weakly linked).
- Report concept pairs in the same domain that have no link between them.

### 9. Tag Registry Violations

- Run `python3 tools/analyze-wiki.py --tag-audit` to validate all tags against `wiki/tags.yml`.
- Report **alias violations**: tags that are known synonyms/abbreviations of a canonical tag (e.g. `rl` should be `reinforcement-learning`). These MUST be auto-fixed by replacing the alias with the canonical tag in the file's frontmatter.
- Report **unregistered tags**: tags that do not appear in the registry at all. Present these to the user for decision:
  - Add the tag to `wiki/tags.yml` as a new canonical tag, OR
  - Replace it with an existing canonical tag.
- Do NOT auto-add unregistered tags to the registry — only auto-fix alias violations.

### 10. LaTeX Formula Formatting

- Scan all wiki files for mathematical expressions that are **not** wrapped in LaTeX delimiters (`$...$` for inline, `$$...$$` for display).
- Detect plain-text math patterns including:
  - Function notation: `V(s)`, `Q(s, a)`, `R(s)`, `P(s'|s)`, `π(a|s)` outside `$` delimiters
  - Operators and symbols: `Σ`, `argmax_a`, `max_a`, `γ`, `π`, `∈`, `≤`, `≥`, `→`, `∝` used as math outside `$` delimiters
  - Standalone equations on their own line (e.g. `V(s) = R(s) + γ Σ P(s'|s) V(s')`) that should be display math `$$...$$`
  - Subscript/superscript notation using Unicode characters (e.g. `Sₜ`, `V₀`, `O(N³)`, `O(n²)`) instead of LaTeX (`$S_t$`, `$V_0$`, `$O(N^3)$`, `$O(n^2)$`)
  - Norm notation using Unicode (`‖...‖`) instead of LaTeX (`$\|...\|$`)
- **Auto-fix**: Convert detected plain-text formulas to proper LaTeX:
  - Inline formulas in prose → wrap with `$...$`
  - Standalone equations on their own line → wrap with `$$...$$`
  - Replace Unicode math symbols with LaTeX equivalents (e.g. `Σ` → `\sum`, `γ` → `\gamma`, `π` → `\pi`, `→` → `\to`, `∝` → `\propto`, `≤` → `\leq`, `≥` → `\geq`)
  - Replace Unicode sub/superscripts with LaTeX notation (e.g. `Sₜ` → `$S_t$`, `N³` → `$N^3$`)
- Report each file and the number of formulas converted.
- **Exclusions**: Do not flag math symbols inside code blocks (`` ` `` or ``` ``` ```), or inside `[[backlink]]` syntax.

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

## Index Update After Lint

After the lint run completes:

1. Update `wiki/index.md` to include entries for any newly created skeleton concept files.
2. Update the `updated:` frontmatter field.

## Lint Summary Report

After all checks and fixes are complete, report a summary to the user:

- **Broken links found**: count and list of broken `[[...]]` references.
- **Orphan files found**: count and list of files with no inbound links.
- **Missing frontmatter**: count and list of files with incomplete frontmatter.
- **Missing concepts detected**: count and list of referenced concepts without files.
- **Topics auto-created**: count and list of topic files created during the synthesis check, with the concepts and summaries they connect.
- **Topic candidates**: count and list of weaker-overlap clusters suggested for user review.
- **Domain MOC status**: domains ready for MOC creation (10+) and approaching threshold (8-9).
- **Duplicate candidates**: count and list of concept pairs that may need merging.
- **Cross-linking gaps**: count of weakly linked concepts and unlinked same-domain pairs.
- **Tag alias violations**: count and list of tags auto-fixed to their canonical form.
- **Unregistered tags**: count and list of tags not in `wiki/tags.yml`, with affected files.
- **LaTeX formatting fixes**: count and list of files where plain-text formulas were converted to LaTeX.
- **Skeleton concepts created**: count and list of new skeleton files created (up to 5).
- **Links fixed**: count of any links that were corrected.
- **Index updated**: confirmation that the index was refreshed.
