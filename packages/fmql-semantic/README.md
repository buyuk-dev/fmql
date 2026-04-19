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

`fmql-semantic` requires a Python build with `sqlite3` loadable-extension support.
Most Python installs qualify: Linux distro Python, Windows Python, `uv`'s bundled
Python, Homebrew's `python`, the python.org macOS installer, conda, and official
Docker images. If the extension loader is unavailable, the backend fails fast
with a clear error.

### With pipx

`fmql-semantic` is a plugin library (no CLI of its own), so `pipx install
fmql-semantic` does not work. Inject it into `fmql`'s pipx env instead:

```sh
pipx inject fmql fmql-semantic
```

On macOS specifically, pin pipx to Homebrew's Python to sidestep the sqlite
loadable-extension problem described below:

```sh
brew install python@3.12
pipx install --python /opt/homebrew/bin/python3.12 fmql
pipx inject fmql fmql-semantic
```

Or set `PIPX_DEFAULT_PYTHON=/opt/homebrew/bin/python3.12` in `~/.zshrc` so all
future `pipx install` calls use Homebrew Python automatically.

### macOS + pyenv: extra setup required

Default `pyenv install` on macOS links Python against Apple's system sqlite
(`/usr/lib/libsqlite3.dylib`), which is compiled without loadable-extension
support for sandboxing reasons. Same is true of the macOS system Python at
`/usr/bin/python3`. In both cases `connection.enable_load_extension(True)`
raises `NotSupportedError` and fmql-semantic fails fast.

To use fmql-semantic on pyenv-installed Python on macOS, point pyenv at
Homebrew's sqlite (which has loadable extensions enabled) and reinstall:

```sh
brew install sqlite

export LDFLAGS="-L$(brew --prefix sqlite)/lib"
export CPPFLAGS="-I$(brew --prefix sqlite)/include"
export PKG_CONFIG_PATH="$(brew --prefix sqlite)/lib/pkgconfig"

pyenv uninstall <version>
pyenv install <version>

python -c "import sqlite3; sqlite3.connect(':memory:').enable_load_extension(True); print('OK')"
```

The `LDFLAGS`/`CPPFLAGS` exports must be set while `pyenv install` runs; they
tell Python's build to prefer Homebrew's sqlite over Apple's. Once the `OK`
check passes, recreate your venv and reinstall `fmql-semantic`. This is a
one-time setup per pyenv Python version.

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
`OLLAMA_API_BASE`, …) are read by LiteLLM directly from the process
environment. A dotenv file passed via `--option env=path/to/.env` also
publishes its non-`FMQL_*` keys into `os.environ` (without overriding
values already exported by the shell), so the same file can carry both
`FMQL_*` settings and provider credentials.

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
