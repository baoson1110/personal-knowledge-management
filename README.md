# Personal Wiki

A Kiro-orchestrated personal knowledge base where an LLM incrementally builds and maintains a persistent, interlinked wiki from your raw source documents. Instead of re-deriving answers at query time (RAG), the LLM compiles sources once into structured markdown and keeps it current — knowledge compounds over time.

Browse the wiki in [Obsidian](https://obsidian.md/) while the LLM handles all the summarizing, cross-referencing, and bookkeeping.

## Quick Start

### 1. Add a source

Drop a markdown file (article, paper, notes) into `staging/`:

```
staging/articles/my-article.md
```

When you're ready to ingest it, promote it to `raw/`:

```bash
tools/promote.sh staging/articles/my-article.md
```

Or promote everything at once:

```bash
tools/promote.sh --all
```

### 2. Compile into the wiki

Once a file lands in `raw/`, the **auto-ingest hook** fires automatically and the LLM compiles it — creating a summary, extracting concepts, and updating the index.

To manually scan and compile all pending sources:

```bash
tools/scan.sh          # see what's new / compiled / modified
```

Then ask Kiro: `compile raw/articles/my-article.md` or trigger the **Scan** hook.

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

This creates a report in `outputs/reports/` and identifies insights that could be filed back into the wiki.

### 5. File back insights from queries and reports

When a `query:` or `report:` generates new insights not yet in the wiki, here's the process to fold them back:

1. After a query/report, Kiro lists **file-back candidates** — new concepts or updates to existing pages.
2. Review the candidates and decide which ones to file back.
3. Ask Kiro to file them back, or use the `file-back:` command on a report:

```
file-back: outputs/reports/report-transformers-2026-04-08.md
```

4. Kiro updates or creates wiki pages, updates `wiki/index.md`, and records the changes in `tools/.fileback-manifest.json`.
5. To check pending file-backs:

```bash
tools/file-back.sh pending
```

6. To manually mark a report as filed (after you've handled it yourself):

```bash
tools/file-back.sh mark outputs/reports/report-topic-YYYY-MM-DD.md
```

**Important**: Don't run `file-back.sh mark` before the wiki pages are actually updated — the manifest tracks which wiki files were touched. If you mark it first, the workflow thinks it's already done. Let Kiro handle the full `file-back:` flow, or update wiki pages manually before marking.

### 6. Health check

```
lint
```

Detects broken links, orphan pages, missing frontmatter, and missing concepts. Creates skeleton pages for up to 5 missing concepts per run.

## Directory Structure

```
staging/          # Drop files here to prep before ingestion
  articles/       #   (mutable, LLM ignores this directory)
  papers/
  repos/
  images/

raw/              # Immutable source documents (LLM reads, never writes)
  articles/
  papers/
  repos/
  images/

wiki/             # LLM-owned knowledge base (Obsidian-compatible)
  concepts/       #   Atomic concept pages (≤150 lines each)
  summaries/      #   Per-source summary pages
  topics/         #   Deep-dive topic pages
  domains/        #   Map of Content entry points
  index.md        #   Catalog of all wiki pages

outputs/          # Generated reports and notes
  reports/        #   report-<topic>-YYYY-MM-DD.md
  notes/          #   note-<topic>-YYYY-MM-DD.md

tools/            # CLI tools and Python libraries
```

## CLI Tools

| Tool | Description |
|------|-------------|
| `tools/scan.sh` | List raw sources with word counts and compile status |
| `tools/promote.sh` | Move files from `staging/` to `raw/` |
| `tools/lint.sh` | Run wiki health checks |
| `tools/file-back.sh` | Manage file-back status for outputs |
| `tools/rebuild-index.py` | Regenerate `wiki/index.md` from all wiki files |
| `tools/search.py` | BM25 full-text search across the wiki |

All tools support `--help`.

## Kiro Hooks

Hooks automate common operations. They live in `.kiro/hooks/`:

| Hook | Trigger | What it does |
|------|---------|-------------|
| Auto Ingest | File created in `raw/` | Compiles new source into wiki |
| Wiki Validate | File edited in `wiki/` | Checks frontmatter, links, formatting |
| Lint Trigger | User-triggered | Runs full lint operation |
| Scan Trigger | User-triggered | Scans and compiles pending sources |
| File-Back Status | User-triggered | Reports pending file-backs |

## Wiki Conventions

- All wiki files use YAML frontmatter with 7 required fields: `title`, `domain`, `tags`, `created`, `updated`, `source`, `confidence`
- Confidence levels: `high` (from raw source), `medium` (secondary), `low` (web-imputed)
- Internal links use Obsidian `[[backlink]]` syntax
- Filenames are lowercase hyphen-separated slugs: `transformer-architecture.md`
- Concept files are capped at 150 lines
- Summary files must include: Executive Summary, Deep Analysis, Key Insights, Related Concepts

## Customization

Edit `.kiro/steering/.local-rules.md` to override language, formatting, and content preferences. Steering files in `.kiro/steering/` govern all LLM behavior and can be evolved as your wiki grows.

## Tips

- Open the wiki in Obsidian alongside Kiro for real-time browsing with graph view
- Use [Obsidian Web Clipper](https://obsidian.md/clipper) to save articles as markdown into `staging/`
- The wiki is just markdown files in a git repo — you get version history for free
- Domain Maps of Content are created automatically when 10+ concepts share a domain
