---
id: 0020
title: "`NOT IN`, `null` literal, and `IS NOT NULL` in Cypher WHERE"
status: done
priority: 2
created: 2026-04-30
updated: 2026-05-01
tags: [cypher, grammar, ux]
depends_on: [0021]
phase: cypher
---

## Goal

Today, expressing "this field is not in a small set, including the absent/null case" requires three combined predicates and a parenthesized `NOT`:

```
NOT (t.property_x IN ["a", "b", "c"]) AND t.property_x IS NOT EMPTY
```

That's verbose for a common shape, and `null` cannot appear inside an `IN` list at all because the value grammar only accepts string / number / bool / date-sentinel. Add three small grammar features to Cypher so the natural form works:

```
t.property_x NOT IN [null, "a", "b", "c"]
```

The features are:

1. **`null` value literal** — usable anywhere a `value` is accepted (RHS of `=`/`!=`, members of an `IN` list).
2. **`NOT IN [...]`** — fused predicate, no parentheses required.
3. **`IS NOT NULL`** — symmetric counterpart to the existing `IS NULL`.

Apply only to the Cypher grammar (`packages/fmql/src/fmql/cypher/grammar.lark`). After [0021](0021-deprecate-qlang-rename-cypher-to-query.md) Cypher is the sole query language; the qlang module is gone.

## Acceptance criteria

- [ ] `value` rule in `cypher/grammar.lark` accepts `NULL_KW` and compiles to Python `None`. Existing `IS NULL` / `IS EMPTY` rules continue to work unchanged.
- [ ] `qualified_ident NOT_KW IN_KW "[" [value ("," value)*] "]"` parses as a `not_in` predicate. The compiled op name is `not_in` (the kwargs API already exposes `not_in` per the README operator table — pick this name to keep the surfaces consistent).
- [ ] `qualified_ident IS_KW NOT_KW NULL_KW` parses as the negation of `IS NULL`. Implementation choice (new `is_not_null` op vs. compile to `NotNode(PredNode(is_null))`) is up to the implementer; whichever produces the same observed semantics for absent-vs-explicitly-null fields as `NOT (x IS NULL)` is fine.
- [ ] Semantics for `t.field = null`, `t.field != null`, and `t.field IN [null, …]` are explicitly defined in tests and a short README note. Recommended baseline: `null` matches packets where the field is missing **or** explicitly set to YAML `null` / `~` (i.e. same equivalence class as `IS NULL`); `t.field != null` is the inverse. Document the choice rather than leaving it implicit.
- [ ] No regression in existing predicates — `IS NULL`, `IS EMPTY`, `IS NOT EMPTY`, plain `IN`, and `NOT (…)` wrapping all keep working.
- [ ] Tests cover:
  - `t.field NOT IN ["a", "b"]`
  - `t.field NOT IN [null, "a"]` (null mixed with non-null values)
  - `t.field IS NOT NULL`
  - `t.field = null` and `t.field != null`
  - `t.field IN [null]` (degenerate single-null list)
  - Parser-level: `NOT IN` whitespace tolerance (`NOT IN`, `NOT  IN`, mixed case).
- [ ] README updates:
  - The Cypher `WHERE` operator section gains `NOT IN [...]`, `IS NOT NULL`, and notes `null` as a value alongside strings/numbers/booleans/dates.
- [ ] `make format && make lint && make test` clean.

## Notes

### Grammar sketch (`packages/fmql/src/fmql/cypher/grammar.lark`)

```lark
predicate: qualified_ident cmp_op value                              -> p_binop
         | qualified_ident IN_KW "[" [value ("," value)*] "]"        -> p_in
         | qualified_ident NOT_KW IN_KW "[" [value ("," value)*] "]" -> p_not_in
         | qualified_ident IS_KW NOT_KW EMPTY_KW                     -> p_not_empty
         | qualified_ident IS_KW EMPTY_KW                            -> p_empty
         | qualified_ident IS_KW NOT_KW NULL_KW                      -> p_not_null
         | qualified_ident IS_KW NULL_KW                             -> p_null

value: ESCAPED_STRING   -> v_string
     | SIGNED_NUMBER    -> v_number
     | BOOL_KW          -> v_bool
     | NULL_KW          -> v_null
     | DATE_OFFSET      -> v_date_offset
```

### Compile-side changes (`cypher/compile.py`)

- Add `v_null` → returns `None`.
- Add `p_not_in` → `PredNode(Predicate(field=…, op="not_in", value=values))`.
- Add `p_not_null` → either a new `is_not_null` op on the filter side, or wrap as `NotNode(PredNode(... is_null ...))`. Confirm that `Predicate.eval` (or whatever drives `not_in` from the kwargs path) handles `None` members of the list with the documented semantics — if it doesn't, this task includes that fix.

### Watch-outs

- **LALR conflicts.** Adding `qualified_ident NOT_KW IN_KW [...]` next to the existing `not_op: NOT_KW not_expr` could produce a shift/reduce conflict depending on how lark resolves it. If it does, the typical fix is to fold `NOT IN` lookahead into `predicate` carefully (the predicate alternative starts with `qualified_ident`, not `NOT_KW`, so the conflict is at the `NOT` token after a qualified ident — which only the predicate rule consumes). Worst case, raise priority on the predicate alt.
- **Comparison vs. equivalence to null.** SQL says `field = null` is unknown. We're not SQL — picking "behaves like `IS NULL`" is friendlier for the markdown/frontmatter world where missing-vs-explicit-null is rarely a meaningful distinction. Just document it.
