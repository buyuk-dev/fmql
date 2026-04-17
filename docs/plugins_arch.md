# fmql Plugin Architecture — Implementation Spec

**Target version:** fmql v0.2.0
**Status:** Design
**Author:** Michał Michalski
**Last updated:** 2026-04-17

## Goal

Formalise the `SearchIndex` protocol that the v0.1.0 README already advertises, add an `fmql index` CLI command, and wire up Python entry-point discovery so third-party packages can register additional backends without any change to fmql core.

The deliverable is a plugin mechanism — not a particular backend. This spec covers one reference backend (TF-IDF) shipped with fmql. Semantic search ships separately as `fmql-semantic` (see its own spec).

## Non-goals

- Embedding models, vector stores, LLM providers. Out of scope for fmql core.
- Replacing or deprecating the existing text-scan fallback. It stays as the default.
- Index management across distributed workspaces, network-backed indexes, or indexing daemons.
- Query-time reranking, hybrid search, or any retrieval logic beyond "backend returns ranked ids."

## Design principles

1. **One protocol, many backends.** A single `SearchIndex` protocol defines the contract. Built-in and third-party backends are indistinguishable at the call site.
2. **Entry points, not config files.** Discovery happens via Python packaging metadata. Installing a plugin package is the only registration step.
3. **Zero heavy dependencies in core.** Core ships text-scan (no deps) and TF-IDF (scikit-learn, optional extra). Nothing else.
4. **Indexes are files on disk.** Consistent with fmql's "files are the source of truth" stance. An index is a single file (or a small directory) at a user-specified path. No hidden state in `~/.fmql/`.
5. **Backends can fail gracefully.** Missing dependencies, missing config, or incompatible index versions produce actionable errors, not stack traces.

## The `SearchIndex` protocol

Defined in `fmql/search/protocol.py`:

```python
from typing import Protocol, Iterable, runtime_checkable
from pathlib import Path

@runtime_checkable
class SearchIndex(Protocol):
    """
    Contract for pluggable search backends.

    Implementations are discovered via the 'fmql.search_index' entry point
    group. Each backend is instantiated with zero arguments; configuration
    (if any) comes from environment variables or from options passed to
    build() and query().
    """

    name: str
    """Short identifier used in --backend flag. Must match entry-point name."""

    def build(
        self,
        packets: Iterable["Packet"],
        out_path: Path,
        *,
        options: dict | None = None,
    ) -> "IndexStats":
        """
        Build or refresh an index at out_path from the given packets.

        Implementations SHOULD support incremental updates: if out_path
        already exists and is compatible, skip packets whose content
        hash is unchanged.

        Returns IndexStats describing what was done.
        """

    def query(
        self,
        text: str,
        index_path: Path,
        *,
        k: int = 10,
        options: dict | None = None,
    ) -> list["SearchHit"]:
        """
        Query the index at index_path. Returns up to k hits, ranked by
        backend-defined relevance.
        """

    def describe(self, index_path: Path) -> "IndexInfo":
        """
        Introspect an existing index: backend name, version, packet count,
        build timestamp, backend-specific metadata (e.g. model name for
        embedding-based backends).
        """
```

Supporting types in `fmql/search/types.py`:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class SearchHit:
    packet_id: str       # stable id (path or uuid) into the workspace
    score: float         # backend-defined; higher is better
    snippet: str | None  # optional; backend may produce context snippet

@dataclass(frozen=True)
class IndexStats:
    packets_indexed: int
    packets_skipped: int    # unchanged since last build
    packets_removed: int    # in index but no longer in workspace
    elapsed_seconds: float

@dataclass(frozen=True)
class IndexInfo:
    backend: str
    backend_version: str
    fmql_version: str
    built_at: str           # ISO timestamp
    packet_count: int
    metadata: dict          # backend-specific: model name, dim, etc.
```

### Protocol semantics

- **`build()` is idempotent.** Calling twice with the same packets is a no-op beyond the skip counter.
- **`query()` is read-only.** Never writes to `index_path`.
- **`describe()` must work without the backend's optional deps being configured.** It reads index metadata only; it should not require, e.g., a valid API key for an embedding-based backend.
- **`packet_id` is stable across runs.** Backends store the id the user's workspace uses — typically the path relative to workspace root, or the `uuid` frontmatter field if the workspace uses uuid-based references.

## Entry points

fmql core declares the plugin group in `pyproject.toml`:

```toml
[project.entry-points."fmql.search_index"]
text_scan = "fmql.search.backends.text_scan:TextScanIndex"
tfidf = "fmql.search.backends.tfidf:TfidfIndex"
```

Third-party packages register themselves into the same group:

```toml
# fmql-semantic/pyproject.toml
[project.entry-points."fmql.search_index"]
semantic = "fmql_semantic:SemanticIndex"
```

Discovery code in `fmql/search/registry.py`:

```python
from importlib.metadata import entry_points
from functools import cache

@cache
def discover_backends() -> dict[str, type[SearchIndex]]:
    """
    Discover all registered SearchIndex backends.

    Results are cached for the process lifetime. Call reload_backends()
    to clear the cache in long-running processes.
    """
    eps = entry_points(group="fmql.search_index")
    backends: dict[str, type[SearchIndex]] = {}
    for ep in eps:
        try:
            cls = ep.load()
        except Exception as e:
            # A broken plugin must not break the whole CLI.
            _log_plugin_error(ep.name, e)
            continue
        backends[ep.name] = cls
    return backends

def get_backend(name: str) -> SearchIndex:
    backends = discover_backends()
    if name not in backends:
        available = ", ".join(sorted(backends)) or "(none)"
        raise BackendNotFoundError(
            f"Unknown search backend: {name!r}. "
            f"Available backends: {available}. "
            f"Install additional backends with `pip install fmql-<name>`."
        )
    return backends[name]()

def reload_backends() -> None:
    discover_backends.cache_clear()
```

A plugin whose import fails must not crash `fmql --help` or `fmql query`. Log the error to stderr once (not per invocation) and continue.

## CLI surface

### `fmql index`

```
fmql index [OPTIONS] WORKSPACE

Build or refresh a search index over a workspace.

Options:
  --backend NAME           Backend to use. Default: tfidf.
  --out PATH               Index output path. Default: <workspace>/.fmql/index.
  --filter QUERY           Restrict indexing to packets matching this filter.
  --field FIELD            Frontmatter field(s) to include in index content.
                           Repeatable. Default: implicit (title + body).
  --force                  Rebuild from scratch, ignoring any existing index.
  --option KEY=VALUE       Backend-specific option. Repeatable.
  --format {text,json}     Output format for stats. Default: text.
```

Examples:

```bash
# Simple: index everything with the default backend
fmql index ./board

# Only index active tasks
fmql index ./board --filter 'status = "active"'

# Explicit backend and output path
fmql index ./board --backend tfidf --out ./board/.search.idx

# Backend-specific option (passed through to build())
fmql index ./board --backend semantic --option model=openai/text-embedding-3-small
```

### `fmql search`

```
fmql search [OPTIONS] INDEX_PATH QUERY

Search an existing index.

Options:
  -k INT                   Max results. Default: 10.
  --format {paths,json,rows}  Output format. Default: paths.
  --option KEY=VALUE       Backend-specific option. Repeatable.
```

Output (default `paths`) prints one packet id per line, ranked. Designed to pipe into other fmql commands:

```bash
# Find semantically similar, then filter structurally
fmql search ./board/.fmql/index "authentication bugs" -k 50 \
  | fmql query --stdin 'status != "done" AND priority > 2' \
               --workspace ./board
```

(The `--stdin` flag for `query` already exists as of v0.1.0 for the bulk-edit pipe pattern. Reused here.)

### `fmql index describe`

```
fmql index describe INDEX_PATH [--format {text,json}]
```

Prints backend name, version, packet count, build time, and backend-specific metadata. Works even if the backend's optional runtime deps aren't installed — it reads index metadata only.

### `fmql index list-backends`

```
fmql index list-backends [--format {text,json}]
```

Lists discovered backends, their source package, and whether they're currently usable (imports cleanly, required deps present). Useful for debugging plugin installation.

## Reference backends shipped with core

### `text_scan` (existing, wrapped)

The current text-scan fallback from v0.1.0, adapted to the new protocol. No persistent index — `build()` is a no-op, `query()` walks the workspace every time. Kept for zero-dep installs and as a correctness oracle for tests.

### `tfidf` (new)

A scikit-learn `TfidfVectorizer` over the concatenation of configured fields. Stored as a pickled sparse matrix + id list on disk. Good enough for small-to-medium workspaces; serves as a reference implementation showing the incremental-update pattern.

Dependencies: `scikit-learn`, `numpy`. Installed as `fmql[tfidf]` extra, not a required dep of the base package.

Index layout:

```
<out_path>/
  meta.json          # IndexInfo, content hashes per packet
  vectorizer.pkl     # fitted TfidfVectorizer
  matrix.npz         # sparse TF-IDF matrix
  ids.json           # ordered list of packet ids
```

Incremental update rule: recompute only if the set of packets or any content hash changed. Partial updates are not worth the complexity for TF-IDF — full refit is fast enough at this scale.

## Index format expectations for all backends

Every backend MUST:

1. Write an `IndexInfo` record at a well-known location inside the index (backends are free to choose the filename, but it must be readable without importing the backend's heavy deps). Suggested convention: `meta.json` at the index root.
2. Store content hashes per packet so incremental builds work.
3. Version its on-disk format and refuse to load incompatible versions with a clear error message pointing the user at `--force` to rebuild.
4. Handle the case where the workspace has moved or been renamed. Packet ids are relative; absolute paths must not be baked into the index.

## Error handling

Three named exception types in `fmql/search/errors.py`:

- `BackendNotFoundError` — requested backend is not installed.
- `BackendUnavailableError` — backend is installed but its optional deps are not (e.g. `fmql-semantic` installed without `LITELLM_MODEL` configured). Error message MUST tell the user the exact missing piece and how to fix it.
- `IndexVersionError` — on-disk index was built with an incompatible version. Error message MUST include the suggestion `fmql index WORKSPACE --force`.

The CLI catches these and prints a one-line friendly message to stderr. Stack traces only with `FMQL_DEBUG=1`.

## Testing strategy

- **Protocol conformance tests.** A parametrised test suite in `fmql/search/conformance.py` that runs against any backend. Third-party plugins can import and run it against themselves. Tests: build-then-query round-trip, incremental update skips unchanged packets, describe works without backend deps, version mismatch is caught.
- **`text_scan` is the oracle.** For a small fixed test corpus, `text_scan` query results are used as a sanity baseline for `tfidf` (not exact match — TF-IDF will reorder — but "top 3 of text_scan should appear in top 10 of tfidf").
- **Plugin discovery test.** A synthetic plugin registered via a test-only entry point, verifying discovery, loading, and the broken-plugin-doesn't-crash-cli path.
- **Coverage target:** ≥84% (matches existing project threshold).

## Migration from v0.1.0

The v0.1.0 README mentions a "text-scan fallback" and a "minimal `SearchIndex` protocol." The protocol in this spec formalises that promise. Migration for existing users is zero-effort: no CLI flag from v0.1.0 changes, and the default behaviour when no index is built is unchanged (text-scan is still the fallback).

The `fmql index` and `fmql search` commands are additive. They don't replace anything.

## Implementation checklist

Ordered by dependency:

1. `fmql/search/types.py` — dataclasses for `SearchHit`, `IndexStats`, `IndexInfo`.
2. `fmql/search/protocol.py` — the `SearchIndex` Protocol.
3. `fmql/search/errors.py` — exception types.
4. `fmql/search/registry.py` — entry-point discovery with caching and error isolation.
5. `fmql/search/backends/text_scan.py` — wrap existing fallback in the protocol.
6. `fmql/search/backends/tfidf.py` — new TF-IDF backend.
7. `fmql/cli/index.py` — `index`, `search`, `index describe`, `index list-backends` commands.
8. `fmql/search/conformance.py` — reusable conformance test suite.
9. `tests/search/` — conformance + discovery + CLI tests.
10. Docs: README section on "Writing a search backend" with a 30-line walkthrough.
11. `pyproject.toml` — register entry points, add `[project.optional-dependencies] tfidf = [...]`.
12. `CHANGELOG.md` — v0.2.0 entry.

Estimated effort: half a day of focused work for a functional v0.2.0, plus half a day for docs and conformance suite.

## Open questions

- Should `fmql query` accept a `--search QUERY` flag that implicitly runs a search and uses the hit set as its initial seed? The v0.1.0 README hints at this. Not required for v0.2.0 but worth a decision before locking the CLI surface.
- Should index paths default to `<workspace>/.fmql/index` (hidden, inside workspace) or `<workspace>.fmql-index` (sibling)? Inside-workspace is more discoverable; sibling avoids polluting the workspace itself. Leaning inside-workspace with an auto-added `.gitignore` entry.
- Should backends be allowed to declare capabilities (e.g. "supports incremental," "supports snippets") so the CLI can adjust output accordingly? Probably yes, but deferred to v0.3 unless a concrete need appears.