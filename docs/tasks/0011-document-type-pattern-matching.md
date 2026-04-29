---
id: 0011
title: Pattern-match document type from frontmatter structure
status: todo
priority: P3
created: 2026-04-19
updated: 2026-04-29
tags: [wishlist, schema, frontmatter, describe]
depends_on: []
---

## Goal

Today, packet "type" is implicit in convention (a `type:` field, a folder, a tag). For a knowledge-graph engine that operates over heterogeneous frontmatter, it would be more useful to *infer* type from structure: a packet whose frontmatter has `{title, status, priority, depends_on}` is a task, a packet with `{decision, context, consequences}` is an ADR, and so on.

## Acceptance criteria

- [ ] Define a "shape" matcher: a small DSL or config (likely declared in `WORKSPACE.md`) that maps required-field signatures to type names. E.g. `task: required=[id, title, status]; optional=[priority, phase, depends_on]`.
- [ ] `fmql describe` reports inferred type per packet, including a confidence/coverage figure when multiple shapes match.
- [ ] Inferred type is queryable: `MATCH (t:task)` resolves to packets matching the `task` shape; `WHERE type(t) = 'task'` works as a projection.
- [ ] Conflicts (a packet matches multiple shapes) surface a warning under `--diagnose` and pick the most-specific shape (largest required-field set) by default.
- [ ] `make format && make lint && make test` clean.

## Notes

Originally on the wishlist in `TODO.md`. Worth pairing with the SQL/qlang docs work ([0006](0006-sql-not-qlang-cheatsheet.md)) — type pattern matching is the kind of feature that needs concrete examples to land in users' heads.
