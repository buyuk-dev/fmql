---
id: 0015
title: Pseudo-fields `a._id` / `a._path` in Cypher `WHERE`
status: todo
priority: 2
created: 2026-04-19
updated: '2026-04-30'
tags: [cypher, query, frontmatter]
depends_on: []
github_issue: https://github.com/buyuk-dev/fmql/issues/8
phase: cypher
---

## Goal

There is currently no first-class way to pin a start node to a specific document in a Cypher-style query without adding bookkeeping fields (e.g. an explicit `id:` key) to the frontmatter of every file. That means queries like "start from *this exact file* and traverse out" require either frontmatter discipline the user may not want, or awkward workarounds.

Support read-only pseudo-fields in the `WHERE` clause (and anywhere property access is valid):

- `a._id` — a stable identifier for the document (e.g. slug / canonical id derived from path).
- `a._path` — the document's workspace-relative file path.

## Acceptance criteria

- [ ] `_id` and `_path` are resolvable in `WHERE` without requiring any frontmatter changes.
- [ ] These pseudo-fields behave like normal string properties for equality and comparison, but are not settable or writable through any bulk-edit path.
- [ ] Attempting to `SET` / write to a pseudo-field produces a clear error.
- [ ] A test covers filtering by `_path` against a real file.
- [ ] Documented in the Cypher section of the README.

## Notes

### Example

```cypher
MATCH (a)-[:links_to]->(b)
WHERE a._path = "notes/inbox/today.md"
RETURN b.title
```

[0003](0003-bulk-migrations-cypher-update.md) already added virtual properties `t.path`, `t.filename`, `t.slug` for SET/MATCH; this issue is about making the same surface (or a `_`-prefixed equivalent) available read-only in WHERE without requiring frontmatter changes. Worth reconciling the naming — `_path` (this issue) vs `path` (already shipped) — before implementing.

Cloned from GitHub issue [#8](https://github.com/buyuk-dev/fmql/issues/8).
