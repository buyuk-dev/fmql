# fmql-semantic

Hybrid semantic search backend plugin for [`fmql`](https://pypi.org/project/fmql/).

- **Dense** retrieval via LiteLLM embeddings + [`sqlite-vec`](https://github.com/asg017/sqlite-vec).
- **Sparse** retrieval via SQLite FTS5 (BM25).
- **Fusion** via reciprocal rank fusion (RRF).
- **Optional reranking** via LiteLLM rerank providers (Cohere, Voyage, etc.).
- Single-file SQLite index. No server.

## Install

```sh
pip install fmql-semantic
```

`fmql-semantic` requires a Python build with `sqlite3` loadable-extension support
(macOS/Linux/Windows builds from python.org, `pyenv`, `uv`, and official Docker
images all qualify; the macOS system Python at `/usr/bin/python3` does not). If
the extension loader is unavailable, the backend fails fast with a clear error.

## Configure

`fmql-semantic` reads configuration from three channels, in increasing
precedence:

1. Process environment.
2. A dotenv file pointed to by `--option env=path/to/.env`.
3. `--option KEY=VALUE` flags on the command line.

### Environment variables

| Variable | Purpose |
|---|---|
| `FMQL_EMBEDDING_MODEL` | LiteLLM embedding model string (required). |
| `FMQL_EMBEDDING_API_BASE` | Override provider API base URL. |
| `FMQL_EMBEDDING_API_KEY` | Override provider API key. |
| `FMQL_EMBEDDING_BATCH_SIZE` | Packets per embedding call (default 100). |
| `FMQL_EMBEDDING_CONCURRENCY` | Max concurrent embedding requests (default 4). |
| `FMQL_EMBEDDING_MAX_TOKENS` | Per-packet token budget before truncation (default 8000). |
| `FMQL_RERANKER_MODEL` | LiteLLM rerank model. Enables reranking when set. |
| `FMQL_RERANKER_TOP_N` | Candidates sent to reranker (default 50). |

Standard LiteLLM provider env vars (`OPENAI_API_KEY`, `VOYAGE_API_KEY`,
`OLLAMA_API_BASE`, …) are read by LiteLLM directly.

### `--option` keys

Build: `model`, `api_base`, `api_key`, `batch_size`, `concurrency`,
`max_tokens`, `fields`, `force`, `env`.

Query: `model`, `api_base`, `api_key`, `reranker_model`, `reranker_top_n`,
`rerank_required`, `no_rerank`, `dense_only`, `sparse_only`, `fetch_k`, `env`.

## Use

```sh
export FMQL_EMBEDDING_MODEL=openai/text-embedding-3-small
export OPENAI_API_KEY=...

# Build once:
fmql index ./my-notes --backend semantic

# Query:
fmql search "quarterly planning" --backend semantic --workspace ./my-notes -k 10

# Dense-only / sparse-only / disable rerank for this query:
fmql search q --backend semantic --workspace ./my-notes --option dense_only=true
fmql search q --backend semantic --workspace ./my-notes --option sparse_only=true
fmql search q --backend semantic --workspace ./my-notes --option no_rerank=true
```

The default index location is `<workspace>/.fmql/semantic.db`. Override with
`--out` (for `fmql index`) or `--index` (for `fmql search`).

## Indexing

For each packet, the backend indexes:

```
<first present frontmatter field from --option fields=title,summary,name>

<body>
```

Frontmatter field *values* are otherwise not indexed — they're already queryable
via fmql's structured layer.

Builds are incremental: packets whose content hash hasn't changed since the
last build are skipped. Packets removed from the workspace are removed from the
index. The index is committed per batch via SQLite WAL, so a crashed build
leaves a queryable index that the next run picks up.

### Model pinning

An index is pinned to the embedding model that built it. Rebuilding with a
different model refuses unless you pass `--force` (which drops the existing
tables). Dimension mismatches are caught the same way.

## Provider notes

- **OpenAI** (`openai/text-embedding-3-small`, `openai/text-embedding-3-large`) —
  batch caps at 2048; default 100 is fine.
- **Voyage** (`voyage/voyage-3`) — batch caps at 128. Set `--option
  batch_size=128` (or lower) for large indexes.
- **Cohere rerank** (`cohere/rerank-v3.5`) — works as a reranker model out of
  the box once `COHERE_API_KEY` is set.
- **Ollama** (`ollama/nomic-embed-text`) — set `OLLAMA_API_BASE` or
  `--option api_base=http://localhost:11434`.

## Licensing

MIT. See [LICENSE](LICENSE).
