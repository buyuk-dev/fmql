---
id: 0002
title: fmql set / append support for list and dict values
status: done
priority: P1
created: 2026-04-19
updated: 2026-04-28
tags: [cli, edits, frontmatter]
depends_on: []
---

## Goal

YAML frontmatter is list- and dict-native, but `fmql set` was scalar-only. That forced a `remove` + N×`append` loop wrapped in a Python script for what is conceptually one update — every non-trivial change ended up as an external script that re-implemented fmql's own parsing/IO.

## Acceptance criteria

- [x] `--json` / `:=` operator on `fmql set` and `fmql append` parses the right-hand value as JSON (borrowing httpie's convention): `fmql set … 'depends_on:=["a","b"]'`.
- [x] `coerce_value` refuses to silently stringify list- or dict-shaped input — `depends_on=["foo","bar"]` must error rather than become the string `'["foo","bar"]'`.
- [x] `make format && make lint && make test` clean.

## Notes

Resolved in commit ccb2cee (2026-04-28). Called out in the original feedback as one of the three highest-weight backlog items alongside the resolver fix and the bulk-migration story.
