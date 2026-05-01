---
id: 0023
title: Expose the frontmatter parser API at the top level of the `fmql` package
status: todo
priority: 2
created: 2026-05-01
updated: 2026-05-01
tags: [api, parser, frontmatter, public-surface]
depends_on: []
phase: cli
---

## Goal

Re-export the basic frontmatter parser primitives from `fmql.parser` at the top level of the `fmql` package so that users who only want a frontmatter-aware markdown parser can `from fmql import parse, parse_file, serialize` without buying into `Workspace`, `Query`, or the rest of the engine.

### Why

fmql is positioned as a "frontmatter knowledge graph engine," but the most reusable primitive in the package — the YAML-frontmatter + markdown-body parser in `packages/fmql/src/fmql/parser.py` — is not part of the public API. Today the only way to reach it is `from fmql.parser import parse_file`, which signals "private / internal" and means anyone who wants a `python-frontmatter` replacement either won't find it or won't trust it.

The parser is already battle-tested by the rest of the engine (every `Workspace` load goes through it), already round-trips losslessly (preserves BOM, EOL, fence style, EOF newline, YAML quoting via ruamel), and is the part of fmql with the broadest standalone audience. Promoting it to the top level is a near-zero-cost win that meaningfully widens the package's reach.

## Acceptance criteria

- [ ] `packages/fmql/src/fmql/__init__.py` re-exports the public parser surface and adds those names to `__all__`. Concretely, the surface is:
  - `parse(text, *, pid, abspath) -> Packet` — parse a string.
  - `parse_file(path, *, pid) -> Packet` — parse a file on disk.
  - `serialize(packet, *, frontmatter=None, body=None, force_frontmatter=None) -> str` — round-trip a packet back to text. Currently named `serialize_packet` in the module; expose under a shorter top-level alias (`serialize`) while keeping `serialize_packet` available from `fmql.parser` for code that already imports it.
- [ ] `Packet.serialize()` (the instance method on `packet.py`) keeps working unchanged.
- [ ] The `pid` parameter on `parse` / `parse_file` is currently required. Audit whether it makes sense as a required argument for someone using fmql purely as a parser (no workspace, no resolvers). Likely outcome: make `pid` optional with a sensible default (e.g. derive from `abspath`, or accept `None` and synthesize one), so the standalone use case is `from fmql import parse_file; doc = parse_file(Path("note.md"))`. If we keep `pid` required, document why in the docstring.
- [ ] README gets a short "Use fmql as a frontmatter parser" subsection near the top of the Python API section showing the three-line example: open a file, mutate `frontmatter`, write it back. This is the elevator pitch for half the audience.
- [ ] Docstrings on `parse`, `parse_file`, and `serialize` are filled in (currently empty) — they're now public API.
- [ ] `make format && make lint && make test` clean.

## Notes

### Naming

`serialize` at the top level is shorter and reads better than `serialize_packet`. The `_packet` suffix made sense when the function lived next to other internal helpers; at the package level it's redundant. Worth coordinating with [0024](0024-rename-packet-type.md) — if `Packet` becomes `Document`, `serialize_packet` would become `serialize_document` anyway, and the top-level alias `serialize` sidesteps the churn.

### Out of scope

- Adding a separate `fmql-parser` distribution. The parser stays in the `fmql` package; this task only adjusts what's importable from the top level.
- Changing the `Packet` dataclass shape. That's [0024](0024-rename-packet-type.md).
- A streaming / incremental parser API. Today's parser reads the whole file; that's fine for the markdown-frontmatter use case.

### Related

- [0017](0017-frontmatter-document-serialization.md) ships a `fmql serialize` / `fmql deserialize` *CLI* surface for the same primitive. This task ships the *Python* surface. Land them together if convenient — they're the CLI and library halves of the same idea.
