# Changelog

## [0.2.1]

### Added

- `ORDER BY` clause in both the Filter DSL (QLang) and the Cypher subset. Supports multiple comma-separated keys with per-key `ASC`/`DESC` and optional `NULLS FIRST` / `NULLS LAST` (default follows SQL: `ASC` → nulls last, `DESC` → nulls first). Cypher ORDER BY keys may reference any bound variable, not just items in `RETURN`.
- `Query.order_by(field, *, desc=False, nulls="auto")` fluent method. Chained calls accumulate keys in declaration order.
- New `fmql.ordering` module exposing `OrderKey` and the shared sort-key helper.

### Changed

- `ORDER`, `BY`, `ASC`, `DESC`, `NULLS`, `FIRST`, `LAST` become reserved words (case-insensitive) in both the QLang and Cypher grammars. Existing queries using these as bare identifiers in keyword positions would have already been syntax errors; string/number/date literals are unaffected.
- Cypher's `ORDER BY` is now supported rather than rejected with `CypherUnsupported`.

## [0.2.0]

### Added

- Search-backend plugin architecture. Third-party packages can register backends via the `fmql.search_index` entry-point group and implement `ScanSearch` or `IndexedSearch` from `fmql.search`. See [docs/plugins_arch.md](docs/plugins_arch.md).
- `fmql index WORKSPACE --backend NAME [--out LOCATION] [--filter QUERY] [--field FIELD] [--force] [--option KEY=VALUE] [--format text|json]` builds an index for indexed backends.
- `fmql list-backends [--format text|json]` enumerates discovered backends.
- `fmql search QUERY --backend NAME [--workspace PATH] [--index LOCATION] [-k N] [--format paths|json|rows] [--option KEY=VALUE]`.
- `fmql query --index-location LOCATION` threads a location into `Query.search()` when `--index` names an indexed backend.
- Built-in `grep` backend (scan-based, no build step) — ships with core. Options: `regex=true`, `case_sensitive=true`.
- `fmql.search.conformance` — reusable assertions for third-party backends.

### Changed (breaking)

- Default search backend renamed from `text` to `grep`. `fmql query --search X` and `Query.search(X)` now default to `--index grep`. The previous `text` name is gone (no alias).
- `SearchIndex` Protocol removed from `fmql.types`. Use `ScanSearch` / `IndexedSearch` from `fmql.search`.
- `Workspace(..., search_indexes=...)` constructor kwarg removed. Backends are resolved through the entry-point registry, not per-workspace injection.
- `fmql.TextScanIndex` removed (replaced by `fmql.search.backends.grep.GrepBackend`).

### Removed

- Placeholder `fmql.contrib.semantic` and `fmql.contrib.sqlite` modules. Real backends now ship as separate packages (`fmql-semantic`, `fmql-fts`, …).

## [0.1.0]

Initial release.
