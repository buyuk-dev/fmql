# fmql-semantic — Spec

Hybrid retrieval plugin for fmql: dense (embeddings) + sparse (BM25), fused with RRF, with optional cross-encoder reranking. Separate pip-installable package. Registers via `fmql.search_index` entry point.

## Dependencies

- `fmql>=0.2` (plugin protocol)
- `litellm` (embeddings and reranking)
- `sqlite-vec` (dense vector storage; BM25 via SQLite's built-in FTS5)

## Configuration

All options configurable via environment variables, dotenv file (`--env PATH`), or CLI flags. Precedence: flags > dotenv > process env > defaults.

### Env vars

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `FMQL_EMBEDDING_MODEL` | yes | — | LiteLLM embedding model string. |
| `FMQL_EMBEDDING_API_BASE` | no | provider default | Override API base URL. |
| `FMQL_EMBEDDING_API_KEY` | no | provider default | Override API key. |
| `FMQL_EMBEDDING_BATCH_SIZE` | no | 100 | Packets per embedding call. |
| `FMQL_EMBEDDING_CONCURRENCY` | no | 4 | Max concurrent embedding requests. |
| `FMQL_EMBEDDING_MAX_TOKENS` | no | 8000 | Per-packet truncation before embedding. |
| `FMQL_RERANKER_MODEL` | no | unset | LiteLLM rerank model. Setting this enables reranking by default. |
| `FMQL_RERANKER_TOP_N` | no | 50 | Candidates sent to reranker. |

Standard LiteLLM provider env vars (`OPENAI_API_KEY`, `VOYAGE_API_KEY`, `OLLAMA_API_BASE`, etc.) are read by LiteLLM directly.

## CLI surface

### `fmql index WORKSPACE` (semantic backend)

```
--backend semantic
--out LOCATION            Default: <workspace>/.fmql/semantic.db
--force                   Rebuild from scratch.
--filter QUERY            Restrict indexing to packets matching this filter.
--fields FIELD[,FIELD...] Fields to index. Default: title/summary/name + body.

--model MODEL
--api-base URL
--api-key KEY
--batch-size INT
--concurrency INT
--max-tokens INT

--env PATH                Load env vars from dotenv file.
--format {text,json}      Stats output format.
--option KEY=VALUE        Escape hatch for uncommon options.
```

### `fmql search QUERY`

```
--backend semantic
--workspace PATH
--index LOCATION
-k INT                    Max results. Default: 10.

--rerank                  Enable reranking. Default if reranker model is configured.
--no-rerank               Disable reranking for this query.
--dense-only              Skip BM25 and fusion.
--sparse-only             Skip embeddings and fusion.

--model MODEL
--reranker-model MODEL
--api-base URL
--api-key KEY

--env PATH
--format {paths,json,rows}
--option KEY=VALUE
```

## Indexing

For each packet, index the same text into both dense and sparse stores:

```
<first present frontmatter field from --fields list>

<body>
```

Frontmatter field values themselves are not indexed — they're already queryable via fmql's structured layer.

Text exceeding `max_tokens` is truncated from the end with a single warning per build.

### Build requirements

- Incremental: skip packets whose content hash is unchanged since last build.
- Packets removed from the workspace are removed from the index.
- Partial builds (crash mid-run) leave a valid, queryable index; re-running picks up where it left off.
- Progress bar on TTY, suppressed otherwise.
- Final write is atomic (write to temp file, rename on success).

### Model pinning

An index is pinned to the embedding model that built it. Building against an existing index with a different model refuses unless `--force` is passed. Error message names both models and the rebuild command.

## Querying

Default mode: hybrid.

1. **Dense retrieval**: embed the query, cosine search in `sqlite-vec`, return top `fetch_k`.
2. **Sparse retrieval**: tokenise the query, BM25 search in FTS5, return top `fetch_k`.
3. **RRF fusion**: combine the two ranked lists, `k_rrf = 60`.
4. **Rerank (optional)**: if reranker is configured, send top `rerank_top_n` fused candidates through LiteLLM rerank, re-sort by rerank score.
5. Truncate to `k`, return.

Defaults: `fetch_k = max(k * 4, 50)` per retriever, `rerank_top_n = 50`.

### Mode overrides

- `--dense-only`: skip sparse retrieval and fusion.
- `--sparse-only`: skip dense retrieval, fusion, and any embedding API call.
- `--no-rerank`: skip reranking even if globally configured.

### Score semantics

Returned `SearchHit.score` is whichever ranker produced the final order: reranker score if rerank ran, RRF score otherwise, cosine similarity if dense-only, BM25 score if sparse-only. Scale differs across modes; use for ranking, not thresholding.

### Reranker fallback

If reranking is enabled but the provider call fails, log a warning and return RRF-sorted results. `--option rerank_required=true` changes this to hard fail.

## Index format

Single SQLite file. Contains:

- `meta` table: backend version, fmql version, built_at, embedding model, embedding dimensions, indexed fields, format_version.
- `packets` table: packet id, content hash, indexed_at.
- `vectors`: sqlite-vec virtual table, `float[<dimensions>]`.
- `packet_vectors`: packet_id ↔ rowid mapping.
- `packets_fts`: FTS5 virtual table, tokenizer `unicode61 remove_diacritics 2`, same rowids as `vectors`.

`format_version = 1` at first release. Mismatched format version raises `IndexVersionError` with rebuild instructions.

## Error handling

- Missing `FMQL_EMBEDDING_MODEL` and no `--model`: clear error listing example model strings and the LiteLLM docs URL.
- Provider errors: re-raised as `BackendUnavailableError` with provider error type in the message. Full trace only with `FMQL_DEBUG=1`.
- Model mismatch on existing index: error names both models, suggests `--force`.
- Missing `--env` file: hard error.

## Testing

- Fake embedding provider and fake reranker registered as LiteLLM custom providers for all integration tests. No real API calls in CI.
- Conformance suite from `fmql.search.conformance` passes.
- RRF correctness: fixed inputs produce hand-computed outputs.
- Mode correctness: `--dense-only`, `--sparse-only`, hybrid, hybrid+rerank each produce expected behaviour.
- Fallback correctness: reranker failure soft-falls-back to RRF; `rerank_required=true` hard-fails.
- Live smoke tests gated behind `FMQL_LIVE_TESTS=1`, not in CI.
- Coverage target: ≥90%.

## Packaging

- Name: `fmql-semantic`.
- Python: 3.11+.
- Pure Python; no platform-specific wheels.
- Entry point: `fmql.search_index` → `semantic = "fmql_semantic:SemanticBackend"`.


## Deliverables

- Package source + tests.
- README (shipped to PyPI).
- Configuration docs covering every env var and flag.
- Provider setup walkthroughs: OpenAI, Voyage, Ollama, Azure.
- Troubleshooting guide: model mismatch, rate limits, missing keys, corrupted index.
- Announcement blog post.