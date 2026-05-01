---
id: 0003
title: Bulk-migration command — symmetric edit path for Cypher
status: done
priority: 1
created: 2026-04-19
updated: 2026-04-28
tags: [cli, cypher, edits, migrations]
depends_on:
  - 0002-fmql-set-list-and-dict-values
phase: cypher
---

## Goal

`fmql cypher` already gave a pattern-matching read path; the symmetric edit path was missing. Something like `fmql update docs/tasks 'MATCH (t) SET t.depends_on = resolve_slug(t.depends_on)'` would have collapsed bulk migrations to one line. The original shape pushed every non-trivial change into external scripts that recapitulated fmql's parsing/IO.

## Acceptance criteria

- [x] New `fmql update '<MATCH … [WHERE …] [SET …] [REMOVE …]>'` command applies a Cypher-style edit pattern across the workspace.
- [x] Cypher SET grammar grows the missing operators: `+=` (merge map), unary `NOT`, list comprehensions, and a top-level `REMOVE` clause.
- [x] Virtual properties (`t.path`, `t.filename`, `t.slug`) are addressable in MATCH / WHERE / SET / RETURN so packets can be filtered or rewritten by file identity.
- [x] `make format && make lint && make test` clean.

## Notes

Resolved in commit 1d301e6 (2026-04-28). Highest-weight item in the original feedback alongside [0001](0001-id-resolver-for-edge-fields.md) and [0002](0002-fmql-set-list-and-dict-values.md).
