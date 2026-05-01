---
id: 0016
title: Allow string / number literals as `RETURN` items
status: done
priority: 3
created: 2026-04-19
updated: 2026-05-01
tags: [cypher, query]
depends_on: []
github_issue: https://github.com/buyuk-dev/fmql/issues/9
phase: cypher
---

## Goal

The `RETURN` clause currently only accepts variable references, property accesses, and `count(...)`:

```
return_item: COUNT_KW "(" IDENT ")"  -> r_count
           | IDENT "." IDENT         -> r_field
           | IDENT                   -> r_var
```

This means you cannot inject a literal into a row, which rules out common shaping tricks like separators, constant columns, or inline labels. Allow string and number literals as `RETURN` items so projections can include constants alongside property accesses.

## Acceptance criteria

- [ ] `RETURN a.title, "|", b.title` parses and executes, producing a three-column result with `"|"` literally in the middle column of every row.
- [ ] Numeric literals work the same way: `RETURN a.title, 1`.
- [ ] Literals render inline in every output format (`rows`, `json`, `yaml`, ...) with a sensible column name (e.g. the literal itself, or `col_N`).
- [ ] Tests cover both string and number literals alongside property accesses.

## Notes

### Implementation sketch

The change touches four files:

- [grammar.lark](../../packages/fmql/src/fmql/cypher/grammar.lark) — add `ESCAPED_STRING` and `SIGNED_NUMBER` alternatives to `return_item`.
- [ast.py](../../packages/fmql/src/fmql/cypher/ast.py) — add `ReturnString` / `ReturnNumber` dataclasses and extend the `ReturnItem` union.
- [compile.py](../../packages/fmql/src/fmql/cypher/compile.py) — add `r_string` / `r_number` transformer methods.
- [executor.py](../../packages/fmql/src/fmql/cypher/executor.py) — handle the new cases in `_project_item` and generate a column name in `_column_name`.

Cloned from GitHub issue [#9](https://github.com/buyuk-dev/fmql/issues/9).
