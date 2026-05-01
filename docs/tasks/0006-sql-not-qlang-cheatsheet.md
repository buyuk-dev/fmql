---
id: 0006
title: Address the SQL-vs-qlang mental-model mismatch in docs
status: done
priority: 2
created: 2026-04-19
updated: 2026-04-29
tags: [docs, qlang, ux]
depends_on: []
---

## Goal

The project's own `docs/README.md` (before the cleanup) had SQL-flavored examples — `SELECT … FROM … WHERE …` — that aren't valid qlang. That was authored by a human who knew fmql but reached for SQL anyway. If SQL is what people type first, drift will show up in other users' repos too.

## Acceptance criteria

- [ ] Decide between two approaches: (a) ship a thin SQL → qlang/cypher translation layer that recognizes the most common `SELECT/WHERE` shapes and emits a "did you mean …" suggestion; (b) add a very visible "this is NOT SQL — here's the cheatsheet" callout to `docs/README.md` and the top of `--help` for `fmql query`.
- [ ] Whichever path is taken, include a side-by-side cheatsheet (SQL ↔ qlang ↔ cypher subset) covering filtering, projection, joins/follows, aggregation, and ORDER BY / LIMIT.
- [ ] If a translation layer ships, it errors loudly on anything outside the translatable subset rather than silently emitting wrong qlang.
- [ ] `make format && make lint && make test` clean.

## Notes

Originally surfaced as feedback item #6. The core observation: even the project's own author reached for SQL when writing examples, so this is a strong drift signal worth taking seriously rather than dismissing as user error.
