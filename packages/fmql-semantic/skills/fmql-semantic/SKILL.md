---
name: fmql-semantic
description: Use fmql-semantic when the user wants meaning-based / semantic / hybrid search over a directory of markdown or frontmatter notes — phrasings like "find docs about X concept", "what have I written on …", "semantic search my notes", "retrieve by topic", "RAG over my vault", or when plain grep will miss hits because the user's query wording differs from the documents' wording. Also triggers on "hybrid search", "BM25 plus embeddings", "index my notes vault", "embed my markdown", "rerank results", "dense retrieval", "cosine similarity search over markdown". This is the `semantic` search backend for fmql — it sits on top of fmql's core commands, so also load the fmql skill for anything involving the qlang filter DSL, frontmatter edits, or graph traversal.
---

# fmql-semantic

`fmql-semantic` is a pluggable search backend for [fmql](../../../fmql/skills/fmql/SKILL.md). It registers itself as the `semantic` backend (visible in `fmql list-backends`) and turns a directory of markdown/frontmatter files into a hybrid dense + sparse retrieval index.

Load this skill whenever the user wants *meaning-based* retrieval over their notes. For structured queries (filter by status/priority/tags, bulk-edit frontmatter, traverse dependency links), use the core fmql skill instead.

## What hybrid retrieval buys you

Three retrievers combined:

1. **Dense** — LiteLLM-powered embeddings stored in `sqlite-vec`, cosine similarity. Finds documents by *meaning* — "quarterly planning" matches "Q2 strategy session" even with no shared vocabulary.
2. **Sparse** — BM25 via SQLite's built-in FTS5. Strong on exact-term matching, proper nouns, and rare words where embeddings can drift.
3. **Reciprocal Rank Fusion (RRF)** — combines the two ranked lists (`k_rrf = 60`), letting each retriever cover the other's blind spots.
4. **Optional cross-encoder rerank** — if a LiteLLM rerank model is configured, the top `rerank_top_n` fused candidates are re-sorted by cross-encoder score for better top-k precision.

Why use it over grep: grep only matches literal substrings in file bytes. fmql-semantic finds relevant documents even when the query and the document share zero tokens — which is the usual case when you search a notes vault by topic.

Why use it over pure dense search: embeddings are fuzzy. For a query like "OAuth2 refresh token edge case", a dense-only search often surfaces thematically similar but off-topic docs; BM25 keeps exact-term anchors in the mix.

## Prerequisites and setup

```bash
pip install fmql fmql-semantic
```

Before indexing, the user needs:

- A **LiteLLM-compatible embedding model** — set via `FMQL_EMBEDDING_MODEL` (e.g. `openai/text-embedding-3-small`, `voyage/voyage-3`, `ollama/nomic-embed-text`) or the `--model` flag.
- A **provider API key** matching the model — the usual LiteLLM env vars (`OPENAI_API_KEY`, `VOYAGE_API_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_API_BASE` for a local Ollama, …). LiteLLM reads these directly.

All config can come from a `.env` file loaded via `--env path/to/.env` on either `fmql index` or `fmql search`.

**Important — ask before running if credentials aren't already in place.** Unlike core fmql (entirely local), semantic indexing makes network calls to an embedding provider and costs real tokens. If the user hasn't confirmed which provider/model to use or doesn't have keys loaded, pause and confirm rather than guessing.

Quickest sanity check:

```bash
fmql list-backends
# Should show a row like:   semantic    indexed    0.1.0    fmql_semantic:SemanticBackend
```

If `semantic` doesn't appear, the plugin isn't installed in the active environment.

## The canonical workflow: index → search

Semantic is an *indexed* backend. Unlike `grep` (which scans at query time), you build a persistent index once and then query it many times.

**Build the index:**

```bash
# First build — embeds every packet in the workspace.
fmql index ./vault --backend semantic
# Default location: ./vault/.fmql/semantic.db
```

- **Incremental by default.** Re-running `fmql index` skips packets whose content hash is unchanged and removes deleted ones. Safe to re-run after edits.
- **Partial builds are safe.** If indexing crashes or is interrupted, re-running picks up where it left off. The index stays queryable throughout.
- **Model pinning.** An index remembers which embedding model built it. Building against an existing index with a *different* model fails unless you pass `--force`. The error message names both models — read it, don't reflexively add `--force`, since a full rebuild re-embeds everything and costs accordingly.

Useful `fmql index` flags:

| Flag | Purpose |
|---|---|
| `--backend semantic` | Required. |
| `--out LOCATION` | Override index path. Default: `<workspace>/.fmql/semantic.db`. |
| `--filter "qlang"` | Restrict indexing to packets matching a qlang filter (e.g. `--filter 'type = "note"'` skips tasks). |
| `--field NAME` | Frontmatter field to prepend to the embedded text. Repeatable. Default: first of `title`/`summary`/`name` that exists, plus the body. |
| `--force` | Full rebuild, ignoring incremental cache. |
| `--model`, `--api-base`, `--api-key`, `--batch-size`, `--concurrency`, `--max-tokens` | Embedding-request knobs. |
| `--env PATH` | Load env vars from a dotenv file. |
| `--format {text,json}` | Build stats output. |

**Search the index:**

```bash
fmql search "quarterly planning" --backend semantic --workspace ./vault -k 10
```

The `--workspace` flag lets the backend derive the default index location (`<workspace>/.fmql/semantic.db`). If the index lives elsewhere, use `--index LOCATION` explicitly.

Useful `fmql search` flags (semantic-specific):

| Flag | Purpose |
|---|---|
| `--backend semantic` | Required. |
| `-k N` | Max results. Default: 10. |
| `--dense-only` | Skip BM25 and fusion. Pure embedding search. Doesn't even hit FTS5. |
| `--sparse-only` | Skip embeddings and fusion. Pure BM25. Makes *no* embedding API call. |
| `--rerank` / `--no-rerank` | Force rerank on or off regardless of env config. |
| `--reranker-model MODEL` | LiteLLM rerank model (e.g. `cohere/rerank-english-v3.0`, `voyage/rerank-2`). |
| `--model`, `--api-base`, `--api-key` | Embedding-request overrides for this query. |
| `--env PATH` | Dotenv file. |
| `--format {paths,json,rows}` | Output format. |

## Output shape

```bash
fmql search "quarterly planning" --backend semantic --workspace ./vault -k 5 --format json
```

emits one JSON line per hit: `{"id": "...", "score": 0.87, "snippet": "..."}`.

**Score semantics differ by mode** — it's whatever ranker produced the final order:
- rerank enabled → cross-encoder score
- hybrid (default) → RRF score (roughly 0 – ~0.03, not a probability)
- `--dense-only` → cosine similarity
- `--sparse-only` → BM25 score

**Use scores to rank, not to threshold.** Relative order is meaningful; absolute values aren't comparable across modes, workspaces, or models.

## Choosing a retrieval mode

| User intent | Use |
|---|---|
| Filter by frontmatter field (status, type, due_date, …) | `fmql query` with qlang — no index needed |
| Match an exact literal string in file bytes | `fmql search "…" --backend grep` |
| "Find notes about X concept" (meaning-based) | semantic, hybrid (default) |
| Query has rare/exact proper nouns, API names, error codes | semantic, consider `--sparse-only` if dense keeps drifting |
| Want pure semantic similarity for clustering / nearest-neighbour intent | `--dense-only` |
| Top-k precision matters (LLM context window is tight, every slot counts) | hybrid + `--rerank`, configure a reranker |

Combine structured filter + semantic search in one pipeline via the core `fmql query` command — it accepts a `--search` stage on top of a qlang filter:

```bash
fmql query ./vault 'type = "note" AND tags CONTAINS "review"' \
  --search "migration strategy" --index semantic --index-location ./vault/.fmql/semantic.db
```

## Integrating with downstream fmql commands

Because `fmql search --format paths` emits one packet id per line, you can pipe hits into any fmql edit:

```bash
# Mark semantically-matched notes as reviewed
fmql search "migration strategy" --backend semantic --workspace ./vault -k 20 --format paths \
  | fmql set reviewed=true --workspace ./vault --dry-run
```

For code that feeds hits to an LLM (RAG), prefer `--format json` so you get id + score + snippet in one structured stream.

## Rerank — when it's worth it

Reranking adds a second API call per query and a second point of failure, but it materially improves top-k precision when:

- The fusion result is noisy (many near-ties in RRF score).
- The downstream consumer only looks at top-5 or smaller.
- The embedding model is a cheap/small one and the user wants a quality boost without re-embedding everything.

Skip rerank when:

- The workspace is small (a few hundred packets) — fusion alone is usually enough.
- The query is sparse/exact — rerankers don't add much over BM25 in that regime.
- Cost or latency matters (rerank roughly doubles per-query API calls).

Set `FMQL_RERANKER_MODEL` to make rerank the default; pass `--no-rerank` to skip it on a specific query.

**Fallback behaviour.** If the reranker call fails, fmql-semantic logs a warning and returns the RRF-sorted results (graceful degradation). Pass `--option rerank_required=true` to turn this into a hard failure instead — useful in automated pipelines where silently-worse results are worse than a clean error.

## Cost and latency awareness

First index of a vault embeds every packet. Rough napkin math:

- `openai/text-embedding-3-small`: ~$0.02 per 1M input tokens. A typical notes vault of ~2000 packets averaging ~500 tokens each is ~1M tokens → ~$0.02. Trivial.
- `openai/text-embedding-3-large`: ~6.5× the cost. Still usually cents.
- Re-runs are incremental (only touched packets re-embed), so ongoing cost is negligible once the initial build is done.

For a very large vault (tens of thousands of packets with long bodies), confirm with the user before the first index run. `fmql index --filter '…'` is the right escape hatch — index only the subset the user actually wants retrievable.

Query latency is dominated by the embedding API call (one per query unless `--sparse-only`). Expect ~200–500 ms for OpenAI; local Ollama can be faster or slower depending on hardware. BM25 and sqlite-vec lookups are sub-millisecond.

## Gotchas

- **Frontmatter field *values* are not embedded.** Indexing writes "`<first configured field's value>\n\n<body>`" to both stores. Structured field values are already queryable via qlang, so embedding them would be redundant and noisy. If the user wants semantic search over titles only, point `--field` at just the title field and rely on short bodies — or pre-process.
- **Long packets get truncated.** Text exceeding `FMQL_EMBEDDING_MAX_TOKENS` (default 8000) is chopped from the end with one warning per build. For very long notes, consider splitting them before indexing.
- **Model mismatch = rebuild.** Switching embedding models requires `--force` on `fmql index` and rebuilds from scratch. Agree on a model upfront.
- **Index is a single SQLite file** (`<workspace>/.fmql/semantic.db`). Portable, easy to delete, but don't add it to git (it's big and user-specific — add `.fmql/` to `.gitignore`).
- **`--dense-only` still needs the embedding API** for the query vector. `--sparse-only` makes *zero* API calls — useful when credentials are unavailable.
- **`fmql list-backends` shows nothing?** The plugin installs via entry points — if you `pip install`ed into a different venv than the one running `fmql`, the backend won't register.

## Example prompts → commands

**"Index my notes vault and show me everything about quarterly planning."**

```bash
fmql index ./notes --backend semantic
fmql search "quarterly planning" --backend semantic --workspace ./notes -k 10 --format json
```

**"Find my recent review notes that mention 'migration strategy'."**

```bash
fmql query ./notes 'type = "note" AND tags CONTAINS "review" AND created_at > today-30d' \
  --search "migration strategy" --index semantic
```

**"Rebuild the index with a better embedding model."**

```bash
export FMQL_EMBEDDING_MODEL=openai/text-embedding-3-large
fmql index ./notes --backend semantic --force
```

**"Pure keyword retrieval for an API name."**

```bash
fmql search "OAuth2RefreshToken" --backend semantic --workspace ./notes --sparse-only -k 20
```

---

For anything not search-related — filtering by frontmatter fields, editing YAML properties, traversing relationships, workspace introspection — use the core [fmql](../../../fmql/skills/fmql/SKILL.md) skill.
