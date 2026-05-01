# Roadmap

A snapshot of in-flight and queued work. The source of truth is `docs/tasks/` — this file is regenerated from it. Run `fmql query 'MATCH (t) RETURN t.id, t.title, t.status, t.priority, t.phase ORDER BY t.priority, t.id' -w docs/tasks --format rows` to refresh.

Last updated: 2026-05-01.

## Phase: cypher (the query language)

| ID | Status | P | Title |
|---|---|---|---|
| [0003](tasks/0003-bulk-migrations-cypher-update.md) | done | 1 | Bulk-migration command — symmetric edit path for Cypher |
| [0021](tasks/0021-deprecate-qlang-rename-cypher-to-query.md) | done | 1 | Deprecate qlang; rename `fmql cypher` to `fmql query` |
| [0006](tasks/0006-sql-not-qlang-cheatsheet.md) | done | 3 | (Superseded by 0021) SQL-vs-qlang mental-model mismatch |
| [0015](tasks/0015-cypher-pseudo-fields-id-path.md) | done | 2 | Pseudo-fields `a._id` / `a._path` in Cypher `WHERE` |
| [0020](tasks/0020-qlang-not-in-null-literal.md) | done | 2 | `NOT IN`, `null` literal, `IS NOT NULL` in Cypher WHERE |
| [0010](tasks/0010-cypher-limit-clause.md) | todo | 3 | Cypher `LIMIT N` clause and `--limit` flag |
| [0016](tasks/0016-cypher-return-literals.md) | todo | 3 | Allow string / number literals as `RETURN` items |
| [0022](tasks/0022-cypher-compatibility-divergences.md) | todo | 3 | Resolve Cypher-compatibility divergences |

## Phase: cli

| ID | Status | P | Title |
|---|---|---|---|
| [0002](tasks/0002-fmql-set-list-and-dict-values.md) | done | 1 | `fmql set` / append support for list and dict values |
| [0017](tasks/0017-frontmatter-document-serialization.md) | todo | 1 | Frontmatter documents — JSON / YAML (de)serialization |
| [0005](tasks/0005-output-format-labels-disambiguation.md) | todo | 2 | Disambiguate `--format json` (NDJSON vs JSON-array) |
| [0018](tasks/0018-subgraph-mermaid-format.md) | todo | 2 | Mermaid output format for `fmql subgraph` |
| [0023](tasks/0023-expose-parser-api-at-top-level.md) | todo | 2 | Expose the frontmatter parser API at the top level |
| [0024](tasks/0024-rename-packet-type.md) | todo | 2 | Rename `Packet` → `Document` (and `PacketId` → `DocumentId`) |
| [0014](tasks/0014-visible-row-separator.md) | todo | 3 | Visible row separator in `rows` output format |

## Phase: workspace

| ID | Status | P | Title |
|---|---|---|---|
| [0004](tasks/0004-workspace-target-ergonomics.md) | done | 1 | Unify workspace / target handling across CLI commands |
| [0008](tasks/0008-workspace-relative-paths-everywhere.md) | todo | 1 | Make every CLI path workspace-relative — args, stdin, outputs |
| [0012](tasks/0012-filesystem-level-operations.md) | todo | 2 | Filesystem-level ops (ls, mv, cp, rm, stat) over the workspace |
| [0013](tasks/0013-link-doctor-on-filesystem-changes.md) | todo | 3 | Auto-doctor edge references when files move or are deleted |

## Phase: resolvers

| ID | Status | P | Title |
|---|---|---|---|
| [0001](tasks/0001-id-resolver-for-edge-fields.md) | done | 1 | ID resolver for edge fields, with type-aware mismatch warnings |
| [0007](tasks/0007-describe-on-resolver-mismatch.md) | todo | 1 | Surface `fmql describe` output on resolver mismatch |
| [0011](tasks/0011-document-type-pattern-matching.md) | todo | 3 | Pattern-match document type from frontmatter structure |

## Phase: plugins / docs

| ID | Status | P | Title |
|---|---|---|---|
| [0009](tasks/0009-fmql-semantic-apsw-backend.md) | todo | 1 | fmql-semantic — switch to apsw |
| [0019](tasks/0019-project-website-github-pages.md) | todo | 1 | Project website hosted on GitHub Pages |
