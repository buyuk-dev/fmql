---
id: 0024
title: Rename `Packet` → `Document` (and `PacketId` → `DocumentId`)
status: todo
priority: 2
created: 2026-05-01
updated: 2026-05-01
tags: [api, naming, breaking-change, refactor]
depends_on: []
phase: cli
---

## Goal

Rename the core `Packet` dataclass to `Document` (and `PacketId` to `DocumentId`) across the codebase. The thing fmql operates on is a markdown file with a YAML frontmatter header — that is a *document*, not a *packet*. The current name is opaque to anyone reading the API for the first time and actively misleading (it suggests something network-y, transport-y, or message-bus-y, none of which fmql is).

### Why

"Packet" is a leftover from an earlier framing and has never carried its weight. Every time the term shows up in the public API (`from fmql import Packet`, `PacketId`, `serialize_packet`, `_packet_field_value`, `as_plain` on a packet…) it forces the reader to translate "packet → frontmatter document" in their head. For a project positioned as a *frontmatter knowledge graph engine*, the canonical noun should be one users already know. `Document` is what the README, design.md, and every external write-up already use informally; the code should follow.

This is a high-confusion-per-occurrence cost paid on every read of the codebase, every docstring, and every error message. It's a single-user project — the right moment to fix it is now, before [0023](0023-expose-parser-api-at-top-level.md) bakes `Packet` into the public top-level API and makes the rename more painful.

### Non-goals

- Restructuring the dataclass. `Document` keeps the exact same fields as `Packet` (`id`, `abspath`, `frontmatter`, `body`, `raw_prefix`, `fence_style`, `eol`, `newline_at_eof`, `has_frontmatter`).
- Splitting into `Document` (logical) vs `RawDocument` (with byte-level metadata). Tempting, but out of scope — the current shape works and the split has no concrete driver yet.
- A deprecation period. Per the project's posture (single user, no external consumers — same reasoning as [0021](0021-deprecate-qlang-rename-cypher-to-query.md)), no `Packet = Document` alias, no `DeprecationWarning`. Just rename clean.

## Acceptance criteria

### Code

- [ ] Rename `packages/fmql/src/fmql/packet.py` → `document.py`. The dataclass becomes `Document`. The instance method stays `serialize()`.
- [ ] Rename `PacketId` → `DocumentId` in `packages/fmql/src/fmql/types.py` and at every callsite. Audit:
  - `aggregation.py`, `query.py`, `traversal.py`, `resolvers.py`, `edits.py`, `subgraph.py`, `describe.py`, `diagnostics.py`, `filters.py`, `workspace.py`, `config.py`, `cypher/expr.py`, `cypher/executor.py`, `search/types.py`, `search/protocol.py`, `search/conformance.py`, `search/backends/grep.py`, `cli/cmd_query.py`, `cli/cmd_subgraph.py`, `cli/cmd_index.py`, `cli/main.py`.
- [ ] Helper / parameter names follow the rename: `packet`/`packets` → `document`/`documents` (or `doc`/`docs`); `pid` → `did` *or* simply `doc_id` — pick one and apply consistently. `_packet_field_value` → `_document_field_value`. Likewise rename internal helpers like `_count_field(packets, …)` arguments.
- [ ] `serialize_packet` in `parser.py` → `serialize_document`. Update its only in-tree caller (`Packet.serialize` → `Document.serialize`).
- [ ] `__init__.py` exports `Document` and `DocumentId` instead of `Packet` / `PacketId`. Alphabetic ordering in `__all__` preserved.
- [ ] Tests: rename modules and identifiers (`test_packet*`, fixtures named `packet`, etc.). All tests still pass.
- [ ] Error messages and docstrings updated. Grep for case-insensitive "packet" across the package and audit each hit — keep only the references that are genuinely about something else (network packets, etc.; there shouldn't be any).

### Docs

- [ ] `README.md`: any mention of `Packet` / `PacketId` updates.
- [ ] `docs/design.md`: line 27 references `PacketId` in the search protocol bullet — update to `DocumentId`.
- [ ] `docs/plugins.md`, `docs/fmql-semantic.md`, `docs/monorepo.md`: grep and update.
- [ ] CHANGELOG entry under `packages/fmql/CHANGELOG.md` calls out the rename as a breaking change.

### `fmql-semantic` package

- [ ] The sister package `packages/fmql-semantic/` re-exports or imports from `fmql`. Audit and update any `Packet` / `PacketId` references there. (Cheap to do in the same PR; expensive to leave half-done across packages.)

### Verify

- [ ] `rg -w 'Packet|PacketId|packet_id|pid' packages/` returns only intentional hits (e.g. shell `pid`, network terminology in third-party stubs — there shouldn't be any in our code).
- [ ] `make format && make lint && make test` clean.

## Notes

### Naming choice

`Document` is the obvious pick: it's what the artifact actually is, it's the term every external write-up already uses, and it composes naturally (`DocumentId`, `serialize_document`, "this query returns 3 documents"). Considered alternatives:

- `Note` — too narrow; implies personal-knowledge-management framing only.
- `Entry` — too generic; could mean a log entry, a dict entry, anything.
- `File` — confusing alongside `pathlib.Path` / file objects.
- `MarkdownFile` / `FmFile` — too long and re-introduces the same "is the prefix carrying weight?" problem `Packet` has today.

Stick with `Document`.

### Coordinate with 0023

[0023](0023-expose-parser-api-at-top-level.md) wants to add `parse` / `parse_file` / `serialize` to the top level and will return a `Packet`/`Document`. Land 0024 first if both are picked up close together — otherwise 0023 ships a public API around `Packet` and the rename gets more annoying. If they land in the opposite order, [0023](0023-expose-parser-api-at-top-level.md) just needs to update its export names.

### `pid` keyword argument

Several functions take `pid=` as a keyword (e.g. `parse(text, *, pid, abspath)`). Rename to `doc_id=` for clarity. This *is* a public-API break for anyone calling the parser directly, but with single-user scope and 0023 still in flight, there is no better moment.
