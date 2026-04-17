# fmql-semantic — Implementation Spec

**Package:** `fmql-semantic`
**Target version:** 0.1.0 (first release)
**Depends on:** `fmql>=0.2` (plugin protocol), `litellm`, `sqlite-vec`
**Status:** Design
**Author:** Michał Michalski
**Last updated:** 2026-04-17

## Goal

Ship semantic search for fmql as a separate pip-installable package that registers itself via the `fmql.search_index` entry point. Uses LiteLLM as the embedding provider abstraction and sqlite-vec as the local vector store. Delivered as the first reference implementation of a third-party fmql plugin.

## Non-goals

- Bundling specific embedding models. Users configure providers via LiteLLM.
- Hybrid retrieval (semantic + keyword). Users can compose with fmql's existing filter DSL by piping.
- Reranking with cross-encoders or LLM rerankers. Out of scope for v0.1.
- Remote vector stores (Pinecone, Qdrant Cloud, etc.). Local-only. If there's demand, ship as separate plugins (`fmql-qdrant`, etc.).
- Embedding frontmatter field values specifically. Frontmatter is already queryable via fmql's structured layer — embedding it is semantic overlap. Body text is the interesting target.

## Design principles

1. **LiteLLM is the only embedding abstraction.** Any provider LiteLLM supports (OpenAI, Voyage, Cohere, Anthropic, Ollama, Azure, Bedrock, etc.) works. No per-provider adapters in this package.
2. **sqlite-vec is the only store.** One file on disk, no daemon, no network, travels with the workspace. Good enough for workspaces up to ~100k packets. Users with bigger needs are outside this plugin's scope.
3. **Configuration via environment, not flags.** Embedding provider config lives in the user's environment (standard LiteLLM convention). fmql-semantic reads it, never writes it, never proxies API keys through CLI flags.
4. **Incremental by default.** Re-indexing an unchanged workspace must be near-instant. Content-hash-based skip, hash stored in the index.
5. **Fail loud, fail early.** Missing config or provider errors produce clear, actionable messages — not LiteLLM stack traces.
6. **One model per index.** An index is pinned to the embedding model that built it. Switching models requires a fresh build. No attempt to mix dimensionalities.

## Architecture

```
    workspace (directory of frontmatter .md)
             │
             ▼
    ┌──────────────────┐
    │ fmql core        │  Packet iteration, filters, hash computation
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ fmql-semantic    │  Batching, incrementality, sqlite-vec I/O
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ LiteLLM          │  Provider routing, retries, standard interface
    └────────┬─────────┘
             │
             ▼
    embedding provider (OpenAI / Voyage / Ollama / ...)
```

fmql-semantic does not talk to providers directly. All embedding calls go through `litellm.embedding()`.

## Configuration

Read from environment at runtime. No config file.

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `FMQL_EMBEDDING_MODEL` | yes | — | LiteLLM model string, e.g. `openai/text-embedding-3-small`, `voyage/voyage-3`, `ollama/nomic-embed-text`. |
| `FMQL_EMBEDDING_DIMENSIONS` | no | provider default | Override output dimensions if the provider supports it (e.g. OpenAI v3 models support truncation). |
| `FMQL_EMBEDDING_BATCH_SIZE` | no | `100` | Packets per embedding API call. |
| `FMQL_EMBEDDING_MAX_TOKENS` | no | `8000` | Truncate packet content to this many tokens before embedding. |
| `FMQL_EMBEDDING_CONCURRENCY` | no | `4` | Max concurrent embedding requests during a build. |

Plus any standard LiteLLM variables for the chosen provider (`OPENAI_API_KEY`, `VOYAGE_API_KEY`, `OLLAMA_API_BASE`, etc.). fmql-semantic does not read or validate these — LiteLLM handles it.

Backend-specific options passable via `fmql index --option KEY=VALUE` override environment values for a single run:

```bash
fmql index ./board --backend semantic \
  --option model=voyage/voyage-3 \
  --option batch_size=50
```

## What gets embedded

For each packet, the embedded text is:

```
<title field>

<body>
```

Where `<title field>` is the first present frontmatter field from a configurable list (default: `title`, `summary`, `name`). Frontmatter itself is not embedded — it's already structurally queryable.

Overridable via `--option` or via a `text_fields` option passed to `build()`:

```bash
fmql index ./board --backend semantic --option text_fields=title,summary,body
```

If the resulting text exceeds `FMQL_EMBEDDING_MAX_TOKENS`, it is truncated from the end with a warning logged once per build.

## Index format

A single SQLite file at the user-specified output path (default: `<workspace>/.fmql/semantic.db`).

Schema:

```sql
-- Metadata table: one row, describes the index.
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Populated keys:
--   backend            = 'semantic'
--   backend_version    = e.g. '0.1.0'
--   fmql_version       = e.g. '0.2.0'
--   built_at           = ISO timestamp of most recent build
--   model              = e.g. 'openai/text-embedding-3-small'
--   dimensions         = e.g. '1536'
--   text_fields        = JSON array, e.g. '["title","body"]'
--   format_version     = '1'

-- Packet registry: stable ids + content hashes for incrementality.
CREATE TABLE IF NOT EXISTS packets (
    id            TEXT PRIMARY KEY,     -- workspace-relative id
    content_hash  TEXT NOT NULL,        -- sha256 of embedded text
    token_count   INTEGER NOT NULL,
    indexed_at    TEXT NOT NULL         -- ISO timestamp
);

-- Vectors: sqlite-vec virtual table. Rowid joins to packets via order-of-insertion
-- — we maintain a separate mapping since sqlite-vec rowids are opaque.
CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING vec0(
    embedding float[<dimensions>]
);

-- Rowid <-> packet id mapping. sqlite-vec rowids are stable within a DB.
CREATE TABLE IF NOT EXISTS packet_vectors (
    packet_id  TEXT PRIMARY KEY REFERENCES packets(id) ON DELETE CASCADE,
    rowid      INTEGER NOT NULL UNIQUE
);
```

**Format version.** `format_version = '1'` today. Bumped on any schema change. Loading an index with a different format version raises `IndexVersionError` and instructs the user to rebuild with `--force`.

**Model pinning.** The `model` and `dimensions` meta values are set at first build. Subsequent builds that detect a mismatch refuse to proceed unless `--force` is set. Users switching models must rebuild.

## Build algorithm

```python
def build(packets, out_path, options=None):
    cfg = resolve_config(options)
    db = open_or_create(out_path, cfg)
    check_model_compatibility(db, cfg)  # raises if model changed

    existing_hashes = load_existing_hashes(db)
    to_embed = []
    seen_ids = set()

    for packet in packets:
        text = render_embedding_text(packet, cfg.text_fields)
        h = sha256(text)
        seen_ids.add(packet.id)
        if existing_hashes.get(packet.id) != h:
            to_embed.append((packet.id, text, h))

    # Remove packets that disappeared from the workspace.
    removed = set(existing_hashes) - seen_ids
    delete_packets(db, removed)

    # Embed in batches, with bounded concurrency.
    stats = embed_and_store(db, to_embed, cfg)

    update_meta(db, built_at=now_iso())
    return IndexStats(
        packets_indexed=stats.indexed,
        packets_skipped=len(seen_ids) - len(to_embed),
        packets_removed=len(removed),
        elapsed_seconds=stats.elapsed,
    )
```

**Batching.** Batches of `FMQL_EMBEDDING_BATCH_SIZE` packets per LiteLLM call. Providers reject requests over their input limit — on a 4xx "too many tokens" response, halve the batch and retry. On persistent failure at batch size 1, skip the packet and log.

**Concurrency.** Up to `FMQL_EMBEDDING_CONCURRENCY` batches in flight via `asyncio.Semaphore`. LiteLLM has async support (`litellm.aembedding`). Use it.

**Retries.** LiteLLM handles provider-level retries. fmql-semantic adds one layer of retry (default: 3 attempts, exponential backoff) for transient network failures surfaced as exceptions.

**Progress reporting.** A `tqdm` progress bar during builds when stdout is a TTY, suppressed otherwise. Granularity: per batch.

**Transactionality.** Each successfully-embedded batch is written to the sqlite file in a single transaction. Partial builds leave a valid, queryable index covering whatever was embedded before the interruption. Re-running `fmql index` picks up where it left off via the content-hash skip.

## Query algorithm

```python
def query(text, index_path, k=10, options=None):
    cfg = resolve_config(options)
    db = open_readonly(index_path)
    meta = load_meta(db)

    # Query-time model must match index-time model.
    if cfg.model != meta['model']:
        warn(f"Query model {cfg.model!r} differs from index model "
             f"{meta['model']!r}. Using index model for query.")
        cfg = cfg.with_model(meta['model'])

    query_vec = litellm.embedding(model=cfg.model, input=[text]).data[0].embedding

    rows = db.execute("""
        SELECT pv.packet_id, vec_distance_cosine(v.embedding, ?) AS distance
        FROM vectors v
        JOIN packet_vectors pv ON pv.rowid = v.rowid
        ORDER BY distance
        LIMIT ?
    """, (serialize(query_vec), k)).fetchall()

    return [SearchHit(packet_id=pid, score=1.0 - dist, snippet=None) for pid, dist in rows]
```

Score is `1 - cosine_distance`, normalised to `[0, 1]` where higher is better. This matches the `SearchIndex` protocol convention.

Snippets are not produced in v0.1. Callers that want context can read the packet body themselves from the returned id.

## Error handling

Beyond the standard errors from `fmql.search.errors`:

**Missing configuration.** If `FMQL_EMBEDDING_MODEL` is not set and no `--option model=...` is passed:

```
error: fmql-semantic requires an embedding model to be configured.

Set FMQL_EMBEDDING_MODEL to a LiteLLM-supported model identifier, e.g.:

    export FMQL_EMBEDDING_MODEL=openai/text-embedding-3-small
    export FMQL_EMBEDDING_MODEL=ollama/nomic-embed-text
    export FMQL_EMBEDDING_MODEL=voyage/voyage-3

Or pass --option model=<id> on the command line.

See https://docs.litellm.ai/docs/embedding/supported_embedding for the
full list of supported models.
```

**Provider errors.** LiteLLM raises provider-specific exceptions (rate limits, auth failures, etc.). Caught once and re-raised as `BackendUnavailableError` with a short message including the original provider error type. Full trace only with `FMQL_DEBUG=1`.

**Model mismatch.** If an existing index was built with a different model than the one currently configured, `build()` without `--force` raises:

```
error: This index was built with model 'openai/text-embedding-3-small'
(1536 dimensions). You're trying to build with 'voyage/voyage-3'
(1024 dimensions). These are incompatible.

To rebuild from scratch with the new model:
    fmql index WORKSPACE --backend semantic --force
```

## Testing strategy

**Unit tests:**
- `render_embedding_text` produces expected text for various frontmatter shapes.
- Content hashing is stable across runs.
- Schema creation + migration between format versions.
- Model-mismatch detection.

**Integration tests with a fake provider:**
- Register a local LiteLLM custom provider that returns deterministic fake embeddings (e.g. hash-based). Use it for all integration tests. No real API calls in CI.
- End-to-end: build, query, incremental build (verify skip count), rebuild after deletion (verify removal), concurrent build cancellation leaves a valid index.

**Conformance tests:**
- Import `fmql.search.conformance` and run the protocol conformance suite. Must pass.

**Live provider smoke test:**
- A separate `tests/live/` directory with tests gated behind `FMQL_LIVE_TESTS=1`. Runs against a real provider (configurable). Not part of CI by default; used as a pre-release smoke check.

**Coverage target:** ≥85% (matches fmql core).

## Performance expectations

Rough numbers to validate against during development. These are goals, not guarantees.

| Workspace size | Cold build time (OpenAI) | Warm rebuild (no changes) | Query latency |
|---|---|---|---|
| 100 packets | < 5s | < 50ms | < 200ms |
| 1,000 packets | < 30s | < 500ms | < 300ms |
| 10,000 packets | < 5min | < 3s | < 500ms |
| 100,000 packets | "it works" | < 30s | < 2s |

The 100k number is a soft ceiling. sqlite-vec can handle it but query latency degrades linearly without an ANN index. If users push past this, they're on the boundary of what this plugin targets.

## Packaging

```toml
# pyproject.toml
[project]
name = "fmql-semantic"
version = "0.1.0"
description = "Semantic search backend for fmql, using LiteLLM + sqlite-vec"
requires-python = ">=3.11"
dependencies = [
    "fmql>=0.2",
    "litellm>=1.40",
    "sqlite-vec>=0.1",
    "numpy>=1.26",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "pytest-cov", "ruff", "black"]

[project.entry-points."fmql.search_index"]
semantic = "fmql_semantic:SemanticIndex"
```

**Version pinning.** `fmql>=0.2` because that's when the plugin protocol landed. `litellm>=1.40` for stable `aembedding`. `sqlite-vec>=0.1` — note this is still pre-1.0, so pin upper bound once a 1.0 ships.

**Supported Python versions.** 3.11+, matching fmql core.

**Wheels.** Pure Python package; no platform-specific wheels needed. sqlite-vec ships its own wheels.

## Documentation deliverables

1. **README.md** — what it is, one-paragraph install, 5-line usage example, link to full docs.
2. **docs/configuration.md** — every env var, every `--option`, provider setup walkthroughs for 3-4 common providers (OpenAI, Voyage, Ollama, Azure).
3. **docs/cookbook.md** — common patterns: combining semantic + structural filters, per-project indexes, incremental workflows.
4. **docs/troubleshooting.md** — common errors and fixes. Model mismatch, rate limits, missing keys, index corruption.
5. **Blog post** — "Adding semantic search to fmql as a plugin." Covers both the why (why separate package) and the how (LiteLLM as abstraction, sqlite-vec as store, plugin protocol in practice). Serves as the second launch moment.

## Implementation checklist

Phase 1 — core mechanics (1 day):

1. Package skeleton, `pyproject.toml`, entry point.
2. Config resolution from env + options.
3. SQLite schema + migration scaffolding.
4. `render_embedding_text` and content hashing.
5. Synchronous build path with LiteLLM (no batching yet).
6. Query path.

Phase 2 — production readiness (1 day):

7. Batching with adaptive batch-size on 4xx.
8. Async/concurrent builds.
9. Incrementality: hash-based skip, packet deletion.
10. Progress reporting.
11. Full error handling + friendly messages.

Phase 3 — tests and docs (1 day):

12. Fake-provider test harness.
13. Unit + integration tests.
14. Conformance suite integration.
15. README, configuration docs, cookbook, troubleshooting.
16. Live smoke test harness.

Phase 4 — release (half day):

17. Tag v0.1.0, publish to PyPI.
18. Announcement blog post.
19. Add to fmql core README's "known plugins" list.

Total: ~3.5 days of focused work.

## Open questions

- Should fmql-semantic support per-field embeddings (separate vectors for title, body, notes)? Useful for weighted hybrid queries. Deferred — single concatenated text for v0.1, revisit if users ask.
- Should the index support multiple models side-by-side (different vector tables per model)? Cleaner than the current "one model per index" rule but significant complexity. Deferred to v0.2.
- Should there be a `fmql-semantic migrate-model` command that reads an old index, re-embeds with a new model, and writes a new index? Probably yes eventually. Not v0.1.
- sqlite-vec's ANN support is evolving. v0.1 uses linear scan (fine up to ~100k). Add ANN indexing when sqlite-vec's story there is stable.
- Should builds write to a temp file and atomically rename on success, to avoid leaving a corrupt index on crash? Yes — add to Phase 2.