# fmql Plugin Architecture — Implementation Spec

Formalise the `SearchIndex` protocol, add `fmql index` and `fmql search` CLI commands, and wire up entry-point discovery so third-party packages can register backends without any change to fmql core.

The deliverable is the plugin mechanism, not any particular backend. Core ships one backend: `grep`, which performs a text scan and builds no index. Real backends (`fmql-fts`, `fmql-semantic`, etc.) ship as separate packages.

## Design principles

1. **One protocol, many backends.** Built-in and third-party backends are indistinguishable at the call site.
2. **Entry points, not config files.** Discovery happens via Python packaging metadata. `pip install` is the only registration step.
3. **Zero non-stdlib dependencies added to core** for this feature.
4. **Indexes are plugin-defined.** Each backend decides what an index is, where it lives, and how it's addressed. The user passes an opaque location string; the backend interprets it.
5. **Fail gracefully.** Missing deps, missing config, or incompatible index versions produce actionable errors, not stack traces.

## The protocol

Two protocols, because some backends have indexes and some don't. Forcing `build()` on scan-based backends is a lie.

`fmql/search/protocol.py`:

```python
from typing import Protocol, Iterable, runtime_checkable

@runtime_checkable
class ScanSearch(Protocol):
    """Backend that scans the workspace at query time. No build step."""

    name: str

    def query(
        self,
        text: str,
        workspace: "Workspace",
        *,
        k: int = 10,
        options: dict | None = None,
    ) -> list["SearchHit"]: ...

    def info(self) -> "BackendInfo": ...


@runtime_checkable
class IndexedSearch(Protocol):
    """Backend that builds a persistent index."""

    name: str

    def parse_location(self, location: str) -> object:
        """
        Validate and normalise an index location string (path, URI, etc.).
        Returns a backend-specific handle. Raises ValueError on malformed input.
        """

    def default_location(self, workspace: "Workspace") -> str | None:
        """
        Suggested default location for this workspace, or None if the
        backend has no sensible default and requires --out explicitly.
        """

    def build(
        self,
        packets: Iterable["Packet"],
        location: str,
        *,
        options: dict | None = None,
    ) -> "IndexStats": ...

    def query(
        self,
        text: str,
        location: str,
        *,
        k: int = 10,
        options: dict | None = None,
    ) -> list["SearchHit"]: ...

    def info(self, location: str | None = None) -> "BackendInfo":
        """
        Return backend metadata. If location is given, include index-specific
        info (packet count, build time, etc.) by reading from the index.
        Must not raise on missing/unreadable indexes — return what it can.
        """
```

Supporting types in `fmql/search/types.py`:

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class SearchHit:
    packet_id: str
    score: float
    snippet: str | None = None

@dataclass(frozen=True)
class IndexStats:
    packets_indexed: int
    packets_skipped: int
    packets_removed: int
    elapsed_seconds: float

@dataclass(frozen=True)
class BackendInfo:
    name: str
    version: str
    kind: str                      # "scan" | "indexed"
    metadata: dict = field(default_factory=dict)
```

### Semantics

- `build()` is idempotent. Rebuilding an unchanged workspace is effectively a no-op.
- `query()` is read-only.
- `packet_id` is stable across runs — whatever stable identifier the workspace uses (relative path or `uuid` field).
- Format versioning is each backend's internal concern. A backend detects incompatible on-disk formats and raises `IndexVersionError` with a rebuild instruction. No protocol-level metadata format is mandated.
- Credentials for remote backends come from environment variables, never from CLI arguments or location strings.

### Recommendation for workspace-writing backends

Write to `<workspace>/.fmql/<backend-name>.*` so one `.gitignore` entry covers everything. Not enforced, just the path of least friction.

## Entry points

Core's `pyproject.toml`:

```toml
[project.entry-points."fmql.search_index"]
grep = "fmql.search.backends.grep:GrepBackend"
```

Third-party packages:

```toml
[project.entry-points."fmql.search_index"]
semantic = "fmql_semantic:SemanticBackend"
```

Discovery in `fmql/search/registry.py`:

```python
from importlib.metadata import entry_points
from functools import cache

@cache
def discover_backends() -> dict[str, type]:
    backends = {}
    for ep in entry_points(group="fmql.search_index"):
        try:
            backends[ep.name] = ep.load()
        except Exception as e:
            _log_plugin_error(ep.name, e)
    return backends

def get_backend(name: str):
    backends = discover_backends()
    if name not in backends:
        available = ", ".join(sorted(backends)) or "(none)"
        raise BackendNotFoundError(
            f"Unknown backend: {name!r}. Available: {available}."
        )
    return backends[name]()
```

A plugin whose import fails must not crash the CLI. Log once to stderr, continue.

## CLI

### `fmql index`

```
fmql index [OPTIONS] WORKSPACE

Options:
  --backend NAME        Backend. Must be an indexed backend.
  --out LOCATION        Index location (backend-defined). Uses backend's
                        default_location() if omitted.
  --filter QUERY        Restrict indexing to packets matching this filter.
  --field FIELD         Fields to embed. Repeatable. Backend-defined default.
  --force               Rebuild from scratch.
  --option KEY=VALUE    Backend-specific option. Repeatable.
  --format {text,json}  Stats output format.
```

Errors if `--backend` names a `ScanSearch` backend (nothing to build).

### `fmql search`

```
fmql search [OPTIONS] QUERY

Options:
  --backend NAME        Backend. Default: grep.
  --workspace PATH      Workspace (for scan backends or to derive default index location).
  --index LOCATION      Explicit index location (for indexed backends).
  -k INT                Max results. Default: 10.
  --format {paths,json,rows}  Default: paths.
  --option KEY=VALUE    Backend-specific option.
```

Output defaults to one packet id per line for piping:

```bash
fmql search "authentication bugs" --backend semantic --workspace ./board -k 50 \
  | fmql query --stdin 'status != "done" AND priority > 2' --workspace ./board
```

### `fmql index list-backends`

```
fmql index list-backends [--format {text,json}]
```

Enumerates discovered backends, source package, and whether they load cleanly.

## Built-in: `grep`

This is the current text-scan implementation renamed to grep and adapted to the new protocol. Scan-based. Implements `ScanSearch`. No index, no `build()`, no location.

- Default: case-insensitive substring match on packet body + title.
- `--option regex=true` enables regex mode.
- `--option case_sensitive=true` for case-sensitive.
- Returns hits in workspace order (no ranking). All scores are `1.0`.

Zero dependencies beyond what fmql already uses.

## Errors

`fmql/search/errors.py`:

- `BackendNotFoundError` — requested backend not installed.
- `BackendUnavailableError` — backend installed but unusable (missing deps, missing config). Message must name the missing piece and the fix.
- `IndexVersionError` — incompatible on-disk format. Message must suggest `--force`.
- `BackendKindError` — tried to `build()` a scan backend, or `search` an indexed backend without a location.

CLI catches these and prints one-line messages to stderr. Full traces only with `FMQL_DEBUG=1`.

## Testing

- **Conformance suite** in `fmql/search/conformance.py`, parametrised over a backend instance. Third-party plugins import and run it against themselves. Tests: round-trip, incremental skip, deletion handling, version mismatch detection.
- **Plugin discovery test** via a synthetic test-only entry point: discovery, load, broken-plugin isolation.
- **Coverage:** ≥90%.

## Migration

Additive. No v0.1.0 behaviour changes. The existing text-scan fallback is renamed internally to `grep` and wrapped in the `ScanSearch` protocol. `fmql index` and `fmql search` are new commands.

## Implementation checklist

1. `fmql/search/types.py` — dataclasses.
2. `fmql/search/protocol.py` — `ScanSearch`, `IndexedSearch`.
3. `fmql/search/errors.py` — exception types.
4. `fmql/search/registry.py` — entry-point discovery.
5. `fmql/search/backends/grep.py` — rename and wrap existing text-scan.
6. `fmql/cli/index.py` — `index`, `search`, `list-backends`.
7. `fmql/search/conformance.py` — reusable test suite.
8. `tests/search/` — conformance, discovery, CLI.
9. README: "Writing a search backend" walkthrough.
10. `pyproject.toml` — entry point registration.
11. `CHANGELOG.md` — v0.2.0.


## Open questions

- `fmql query --search QUERY`: should query-then-filter be a single command, or stay as a pipe? Leaning pipe (simpler, composable). > pipe.
- Capability declarations on backends (`supports_incremental`, `supports_snippets`): deferred until a concrete need appears. > ok.