# Personal Wiki

A Kiro-orchestrated personal knowledge base where an LLM incrementally builds and maintains a persistent, interlinked wiki from your source documents. Instead of re-deriving answers at query time (RAG), the LLM compiles sources once into structured markdown and keeps it current — knowledge compounds over time.

Browse the wiki in [Obsidian](https://obsidian.md/) by opening the `vault/` folder as your vault, while the LLM handles all the summarizing, cross-referencing, and bookkeeping.

## Quick Start

### 1. Add a source

Drop a markdown file (article, paper, notes) into `vault/inbox/`:

```
vault/inbox/articles/my-article.md
```

When you're ready to ingest it, promote it to `vault/staging/`:

```bash
tools/promote.sh vault/inbox/articles/my-article.md
```

Or promote everything at once:

```bash
tools/promote.sh --all
```

### 2. Compile into the wiki

Once a file lands in `vault/staging/`, the **auto-ingest hook** fires automatically and the LLM compiles it — creating a summary, extracting concepts, and updating the index.

To manually scan and compile all pending sources:

```bash
tools/scan.sh          # see what's new / compiled / modified
```

Then ask Kiro: `compile vault/staging/articles/my-article.md` or trigger the **Scan** hook.

### 3. Ask questions

In Kiro chat:

```
query: What are the key differences between X and Y?
```

The LLM searches the wiki and synthesizes an answer with citations. It will not hallucinate beyond what the wiki contains.

### 4. Generate reports

```
report: overview of transformer architectures
```

This creates a report in `vault/outputs/reports/` and identifies insights that could be filed back into the wiki.

### 5. File back insights from queries and reports

When a `query:` or `report:` generates new insights not yet in the wiki, here's the process to fold them back:

1. After a query/report, Kiro lists **file-back candidates** — new concepts or updates to existing pages.
2. Review the candidates and decide which ones to file back.
3. Ask Kiro to file them back, or use the `file-back:` command on a report:

```
file-back: vault/outputs/reports/report-transformers-2026-04-08.md
```

4. Kiro updates or creates wiki pages, updates `vault/wiki/index.md`, and records the changes in `tools/.fileback-manifest.json`.
5. To check pending file-backs:

```bash
tools/file-back.sh pending
```

6. To manually mark a report as filed (after you've handled it yourself):

```bash
tools/file-back.sh mark vault/outputs/reports/report-topic-YYYY-MM-DD.md
```

**Important**: Don't run `file-back.sh mark` before the wiki pages are actually updated — the manifest tracks which wiki files were touched. If you mark it first, the workflow thinks it's already done. Let Kiro handle the full `file-back:` flow, or update wiki pages manually before marking.

### 6. Health check

```
lint
```

Detects broken links, orphan pages, missing frontmatter, and missing concepts. Creates skeleton pages for up to 5 missing concepts per run.

## Directory Structure

```
vault/                  # Obsidian vault — all user-facing content lives here
├── .obsidian/          #   Obsidian configuration (single vault config)
├── inbox/              #   Layer 1: Landing zone (human-only, LLM ignores)
│   ├── articles/
│   ├── books/
│   ├── discussion/
│   ├── papers/
│   └── slide/
├── staging/            #   Layer 2: Being processed (LLM reads for compilation)
│   ├── articles/
│   ├── books/
│   ├── discussion/
│   ├── papers/
│   └── slide/
├── wiki/               #   Layer 3: LLM-owned knowledge base
│   ├── concepts/       #     Atomic concept pages (≤150 lines each)
│   ├── summaries/      #     Per-source summary pages
│   ├── topics/         #     Deep-dive topic pages
│   ├── domains/        #     Map of Content entry points
│   ├── reference/      #     Reference material
│   └── index.md        #     Catalog of all wiki pages
├── life/               #   Human-only personal space (LLM does not access)
│   ├── inbox/
│   ├── notes/
│   ├── plans/
│   ├── projects/
│   └── work/
├── bookmarks/          #   URL research queue (human-only, LLM does not access)
├── outputs/            #   LLM-generated reports and notes
│   ├── reports/        #     report-<topic>-YYYY-MM-DD.md
│   └── notes/          #     note-<topic>-YYYY-MM-DD.md
└── asset/              #   Shared images referenced by markdown files

tools/                  # CLI tools and Python libraries (repo root)
tests/                  # Test files (repo root)
docs/                   # System documentation (repo root)
.kiro/                  # Kiro configuration, steering, hooks, specs (repo root)
```

### Human-Only Zones

The following directories are strictly off-limits to the LLM agent:

- **`vault/life/`** — Personal planning, diary, projects, and work notes. Use this space for anything you want to keep private and unmodified by the LLM.
- **`vault/bookmarks/`** — URLs and links to research later. When you clip a bookmark into a full article, move it to `vault/inbox/` for ingestion.
- **`vault/inbox/`** — The landing zone for new content. You can freely edit and prepare files here before promoting them to staging. The LLM only sees content after promotion.

## CLI Tools

| Tool | Description |
|------|-------------|
| `tools/scan.sh` | List staging sources with word counts and compile status |
| `tools/promote.sh` | Move files from `vault/inbox/` to `vault/staging/` |
| `tools/lint.sh` | Run wiki health checks on `vault/wiki/` |
| `tools/file-back.sh` | Manage file-back status for `vault/outputs/` |
| `tools/rebuild-index.py` | Regenerate `vault/wiki/index.md` from all wiki files |
| `tools/search.py` | BM25 full-text search across the wiki |

All tools support `--help`.

## Kiro Hooks

Hooks automate common operations. They live in `.kiro/hooks/`:

| Hook | Trigger | What it does |
|------|---------|-------------|
| Auto Ingest | File created in `vault/staging/` | Compiles new source into wiki |
| Wiki Validate | File edited in `vault/wiki/` | Checks frontmatter, links, formatting |
| Lint Trigger | User-triggered | Runs full lint operation |
| Scan Trigger | User-triggered | Scans and compiles pending sources |
| File-Back Status | User-triggered | Reports pending file-backs |

## Wiki Conventions

- All wiki files use YAML frontmatter with 7 required fields: `title`, `domain`, `tags`, `created`, `updated`, `source`, `confidence`
- Confidence levels: `high` (from staging source), `medium` (secondary), `low` (web-imputed)
- Internal links use Obsidian `[[backlink]]` syntax
- Filenames are lowercase hyphen-separated slugs: `transformer-architecture.md`
- Concept files are capped at 150 lines
- Summary files must include: Executive Summary, Deep Analysis, Key Insights, Related Concepts

## Customization

Edit `.kiro/steering/.local-rules.md` to override language, formatting, and content preferences. Steering files in `.kiro/steering/` govern all LLM behavior and can be evolved as your wiki grows.

## Image Handling

Source articles often contain images (diagrams, charts, figures). These are stored in `vault/asset/` and referenced using Obsidian wikilink syntax (`![[asset/filename.png]]`). Since `vault/asset/` and `vault/wiki/` share the same Obsidian vault root, images resolve correctly without symlinks.

During ingest, the LLM carries relevant images into wiki pages:
- Summary files include all key diagrams and figures from the source
- Concept files include only images closely related to the concept (1–2 max)
- Every embedded image has an italicized caption describing what it shows

### Obsidian Web Clipper

[Obsidian Web Clipper](https://obsidian.md/clipper) is a browser extension that converts web articles to markdown. Use it to clip articles into `vault/inbox/articles/`, then promote them to `vault/staging/` with `tools/promote.sh`.

### Local Images Plus

The [Local Images Plus](https://github.com/Sergei-Korneev/obsidian-local-images-plus) community plugin downloads remote images referenced in clipped articles and rewrites the markdown links to point to local copies.

Configuration (Settings → Community plugins → Local Images Plus):
- **Media folder**: `asset`
- **Folder to save new attachments**: "In the folder specified below"
- **Move/delete/rename media folder**: Off (images are shared across notes)
- **Process all new files**: On (auto-downloads images when Web Clipper creates a note)

After clipping an article, Local Images Plus auto-processes it. For existing articles with remote URLs, trigger manually via Command Palette → "Local Images Plus: Download images locally".

## Tips

- Open `vault/` as your Obsidian vault for a clean sidebar with only content folders
- Use Obsidian Web Clipper to save articles as markdown into `vault/inbox/`
- The wiki is just markdown files in a git repo — you get version history for free
- Domain Maps of Content are created automatically when 10+ concepts share a domain
