---
inclusion: manual
---

# Personal Synthesis Workflow

Procedure for consolidating and synthesizing personal notes into refined documents. This steering file is manually loaded via `#personal-synthesis-workflow` or triggered by hooks.

## Folder Structure

```
vault/life/
  inbox/        # raw personal input — brainstorms, conversations, plans, journal entries
  notes/        # consolidated per-item — cleaned up, structured, one note per inbox item
```

The pipeline flows: `inbox/ → notes/`

- **inbox → notes** is a 1:1 cleanup (one messy inbox item produces one clean note)
- **notes → notes** is a many:1 merge (multiple notes on the same topic produce one synthesis note)

## Personal Note Conventions

### Inbox Items (`vault/life/inbox/`)

Inbox items are freeform. They can be:
- Chat transcripts (e.g., brainstorming with an LLM)
- Bullet-point brainstorms
- Journal entries
- Decision logs
- Rough plans

Inbox items have **minimal frontmatter** — just enough to identify them:

```yaml
---
title: "Human-readable title"
tags: [tag1, tag2]
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
---
```

No `domain`, `confidence`, or `source` fields required. Tags are freeform and do NOT need to comply with `vault/wiki/tags.yml`.

### Notes (`vault/life/notes/`)

Notes are cleaned-up, structured versions of individual inbox items. One note per source inbox item. They use this frontmatter:

```yaml
---
title: "Human-readable title"
tags: [tag1, tag2]
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
source: "vault/life/inbox/original-item.md"
---
```

The `source` field points to the single inbox item this note was consolidated from.

### Synthesis Documents (`vault/life/notes/`)

Synthesis documents are refined, structured outputs produced by merging multiple related notes. They use this frontmatter:

```yaml
---
title: "Human-readable title"
tags: [tag1, tag2]
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
sources:
  - "vault/life/notes/note-a.md"
  - "vault/life/notes/note-b.md"
---
```

The `sources` field lists all notes that contributed to the synthesis.

---

## Phase 1 — Consolidation (inbox → notes)

Triggered when the user asks to consolidate a personal inbox item (e.g., "consolidate my gap year note", "clean up vault/life/inbox/gap-year-plan.md").

### Step 1.1 — Read the Raw Inbox Item

1. Read the full contents of the item in `vault/life/inbox/`.
2. Identify the document type: chat transcript, bullet brainstorm, journal entry, decision log, etc.
3. Note the language used (Vietnamese, English, mixed) — the note should preserve the **original language** of the substantive content.

### Step 1.2 — Extract Substance

Strip away conversational scaffolding and noise. Specifically:

- **Remove**: greeting/closing pleasantries, filler phrases ("Let me think about this..."), repeated questions that were already answered, meta-commentary about the conversation itself.
- **Preserve**: all factual claims, numbers, dates, arguments, recommendations, action items, emotional considerations, and qualitative reasoning.
- **Deduplicate**: when the same point is made multiple times (common in chat transcripts), consolidate into a single, clear statement. If later iterations refined the point, keep the most refined version.
- **Flag contradictions**: if the inbox item contradicts itself (e.g., early in the chat says "I should quit" but later says "I should stay"), preserve both positions and mark them with `⚠️ Contradiction:` so the reader sees the tension.

### Step 1.3 — Organize by Theme

Restructure the extracted content into logical sections. Do NOT preserve the original chronological order of a conversation — organize by **theme**.

The note MUST contain these sections (skip any that have no content):

1. **Context** — what this item is about, what prompted it.
2. **Key Points** — the main arguments, findings, or ideas, organized by sub-theme.
3. **Data & Figures** — any concrete numbers, financial calculations, KPIs, timelines, or measurable criteria. Present these in tables or lists for easy scanning.
4. **Decisions** — any decisions that were made (or leaned toward) in this item. Mark each as `✅ Decided`, `🔶 Leaning`, or `❓ Undecided`.
5. **Open Questions** — unresolved items from this item.
6. **Action Items** — concrete next steps mentioned in the item.

### Step 1.4 — Write the Note

1. Create the note at `vault/life/notes/<item-slug>.md` (use the same slug as the source inbox item).
2. Set `source:` to the path of the original inbox item.
3. The note should be **significantly shorter** than the raw inbox item — aim for 30-50% of the original length for chat transcripts, closer to 70-80% for already-structured items.
4. Write in clear, direct prose. No conversational tone.

### Step 1.5 — Report

After consolidation, report:
- Source inbox item path and line count
- Note path and line count (with compression ratio)
- Number of contradictions flagged
- Number of open questions found
- Number of action items extracted

---

## Phase 2 — Synthesis (notes → synthesis)

Triggered when the user asks to synthesize personal notes on a topic (e.g., "synthesize my gap year notes", "synthesize everything about trading").

### Step 2.1 — Identify Related Notes

1. Scan `vault/life/notes/` for files related to the requested topic.
2. Use filename, tags, and content to determine relevance.
3. If any relevant items in `vault/life/inbox/` do NOT have a corresponding note yet, flag them: "These inbox items haven't been consolidated yet: [list]. Consolidate them first, or proceed with available notes only?"
4. List the identified notes and confirm with the user before proceeding.

### Step 2.2 — Read and Cross-Analyze

1. Read all identified notes in full.
2. Build a unified picture across notes:
   - **Agreements**: points that multiple notes reinforce.
   - **Contradictions**: points where notes disagree (including within-item contradictions flagged in Phase 1). Note which note is more recent.
   - **Evolution**: how thinking has changed over time across notes. The most recent note's position generally takes precedence, but flag when earlier reasoning was stronger.
   - **Gaps**: important questions that no note addresses.

### Step 2.3 — Produce the Synthesis Document

Create or update a file at `vault/life/notes/<topic-slug>.md`.

The synthesis MUST contain these sections:

1. **Context** — what this is about, why it matters, when the thinking started.
2. **Current Position** — where things stand right now. This is the "executive summary" of all the thinking — what has been decided, what the current plan is.
3. **Key Arguments & Analysis** — consolidated reasoning from all notes. Organize by theme, not by source. When notes contradict each other, present both sides and note which is more recent.
4. **Data & Figures** — consolidated numbers, calculations, and KPIs from all notes. Deduplicate and use the most recent figures.
5. **Open Questions** — unresolved items that need further thinking or information.
6. **Action Items** — concrete next steps with timelines if available. Deduplicate across notes.
7. **Related Wiki Concepts** — `[[backlinks]]` to any wiki concepts that are relevant. This is the bridge between personal thinking and the knowledge base.
8. **Sources** — list of notes that fed into this synthesis, with a one-line note on what each contributed.

### Step 2.4 — Incremental Updates

When re-synthesizing (new notes added since last synthesis):

1. Read the existing synthesis document.
2. Read only the new or modified notes.
3. Merge new information into the existing synthesis — don't rewrite from scratch.
4. Move resolved questions from "Open Questions" to "Current Position."
5. Update the `updated:` frontmatter and add new sources to the `sources:` list.

---

## Cross-Linking Rules

- Notes and synthesis docs CAN link to wiki concepts via `[[concept-slug]]`.
- Wiki concepts MUST NOT link back to personal inbox items, notes, or synthesis docs.
- This keeps the wiki knowledge graph clean while letting personal thinking reference accumulated knowledge.

## What Does NOT Happen

- Personal items are NOT ingested into the wiki pipeline. No wiki summaries, no concept extraction, no compile manifest entries.
- Personal tags do NOT need to exist in `vault/wiki/tags.yml`.
- No domain MOC tracking for personal content.

## Manifest Tracking

The personal pipeline uses its own manifest at `tools/.personal-manifest.json` to track processing status. This is separate from the wiki compile manifest.

### Manifest Structure

```json
{
  "version": 1,
  "inbox": {
    "vault/life/inbox/gap-year-plan.md": {
      "status": "consolidated",
      "consolidated_at": "2026-05-02T12:00:00+00:00",
      "note_file": "vault/life/notes/gap-year-plan.md"
    }
  },
  "notes": {
    "vault/life/notes/gap-year-plan.md": {
      "status": "synthesized",
      "synthesized_at": "2026-05-02T13:00:00+00:00",
      "synthesis_file": "vault/life/notes/gap-year.md"
    }
  }
}
```

### Updating the Manifest

After completing Phase 1 (consolidation) for an inbox item, update `tools/.personal-manifest.json`:

```json
{
  "status": "consolidated",
  "consolidated_at": "<ISO 8601 timestamp>",
  "note_file": "vault/life/notes/<slug>.md"
}
```

After completing Phase 2 (synthesis) for a note, update the notes section:

```json
{
  "status": "synthesized",
  "synthesized_at": "<ISO 8601 timestamp>",
  "synthesis_file": "vault/life/notes/<topic-slug>.md"
}
```

### Scanning

Use `python3 tools/scan_personal.py` to check pipeline status:

- `python3 tools/scan_personal.py --pending` — show unconsolidated or modified inbox items
- `python3 tools/scan_personal.py --phase synthesis --pending` — show unsynthesized or modified notes
