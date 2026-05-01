---
id: 0020
title: "`NOT IN`, `null` literal, and `IS NOT NULL` in qlang and Cypher WHERE"
status: todo
priority: 2
created: 2026-04-30
updated: 2026-04-30
tags: [qlang, cypher, grammar, ux]
depends_on: []
phase: cypher
---

## Goal

Today, expressing "this field is not in a small set, including the absent/null case" requires three combined predicates and a parenthesized `NOT`:

```
NOT (property_x IN ["a", "b", "c"]) AND property_x IS NOT EMPTY
```

That's verbose for a common shape, and `null` cannot appear inside an `IN` list at all because the value grammar only accepts string / number / bool / date-sentinel / ident. Add three small grammar features so the natural form works:

```
property_x NOT IN [null, "a", "b", "c"]
```

The features are:

1. **`null` value literal** — usable anywhere a `value` is accepted (RHS of `=`/`!=`, members of an `IN` list).
2. **`NOT IN [...]`** — fused predicate, no parentheses required.
3. **`IS NOT NULL`** — symmetric counterpart to the existing `IS NULL`.

Apply to both parsers so the qlang DSL and the Cypher subset stay aligned (the README documents Cypher's `WHERE` as "the same operators as the filter DSL"):

- `packages/fmql/src/fmql/qlang/grammar.lark` (filter DSL used by `fmql query` and the `qlang` module)
- `packages/fmql/src/fmql/cypher/grammar.lark` (Cypher subset used by `fmql cypher` / `fmql update`)

## Acceptance criteria

- [ ] `value` rule in both grammars accepts `NULL_KW` and compiles to Python `None`. Existing `IS NULL` / `IS EMPTY` rules continue to work unchanged.
- [ ] `IDENT NOT_KW IN_KW "[" [value ("," value)*] "]"` parses as a `not_in` predicate in both grammars. The compiled op name is `not_in` (the kwargs API already exposes `not_in` per the README operator table — pick this name to keep the surfaces consistent).
- [ ] `IDENT IS_KW NOT_KW NULL_KW` parses as the negation of `IS NULL`. Implementation choice (new `is_not_null` op vs. compile to `NotNode(PredNode(is_null))`) is up to the implementer; whichever produces the same observed semantics for absent-vs-explicitly-null fields as `NOT (x IS NULL)` is fine.
- [ ] Semantics for `field = null`, `field != null`, and `field IN [null, …]` are explicitly defined in tests and a short README note. Recommended baseline: `null` matches packets where the field is missing **or** explicitly set to YAML `null` / `~` (i.e. same equivalence class as `IS NULL`); `field != null` is the inverse. Document the choice rather than leaving it implicit.
- [ ] No regression in existing predicates — `IS NULL`, `IS EMPTY`, `IS NOT EMPTY`, plain `IN`, and `NOT (…)` wrapping all keep working.
- [ ] Tests cover, in both parsers:
  - `field NOT IN ["a", "b"]`
  - `field NOT IN [null, "a"]` (null mixed with non-null values)
  - `field IS NOT NULL`
  - `field = null` and `field != null`
  - `field IN [null]` (degenerate single-null list)
  - Parser-level: `NOT IN` whitespace tolerance (`NOT IN`, `NOT  IN`, mixed case).
- [ ] README updates:
  - The filter-DSL operator table gains `NOT IN [...]`, `IS NOT NULL`, and notes `null` as a value alongside strings/numbers/booleans/dates.
  - The Cypher-subset section gets the same updates (or a single shared note that the operator set applies to both).
- [ ] `make format && make lint && make test` clean.

## Notes

### Grammar sketch (qlang — `packages/fmql/src/fmql/qlang/grammar.lark`)

```lark
predicate: IDENT cmp_op value                                  -> p_binop
         | IDENT IN_KW "[" [value ("," value)*] "]"            -> p_in
         | IDENT NOT_KW IN_KW "[" [value ("," value)*] "]"     -> p_not_in
         | IDENT IS_KW NOT_KW EMPTY_KW                         -> p_not_empty
         | IDENT IS_KW EMPTY_KW                                -> p_empty
         | IDENT IS_KW NOT_KW NULL_KW                          -> p_not_null
         | IDENT IS_KW NULL_KW                                 -> p_null

value: ESCAPED_STRING  -> v_string
     | SIGNED_NUMBER   -> v_number
     | BOOL_KW         -> v_bool
     | NULL_KW         -> v_null
     | DATE_OFFSET     -> v_date_offset
     | IDENT           -> v_ident
```

Mirror the `predicate` and `value` changes in `packages/fmql/src/fmql/cypher/grammar.lark` (which uses `qualified_ident` instead of `IDENT` in predicates).

### Compile-side changes (`qlang/compile.py` and the cypher equivalent)

- Add `v_null` → returns `None`.
- Add `p_not_in` → `PredNode(Predicate(field=…, op="not_in", value=values))`.
- Add `p_not_null` → either a new `is_not_null` op on the filter side, or wrap as `NotNode(PredNode(... is_null ...))`. Confirm that `Predicate.eval` (or whatever drives `not_in` from the kwargs path) handles `None` members of the list with the documented semantics — if it doesn't, this task includes that fix.

### Watch-outs

- **LALR conflicts.** Adding `IDENT NOT_KW IN_KW [...]` next to the existing `not_op: NOT_KW not_expr` could produce a shift/reduce conflict depending on how lark resolves it. If it does, the typical fix is to fold `NOT IN` lookahead into `predicate` carefully (the predicate alternative starts with `IDENT`, not `NOT_KW`, so the conflict is at the `NOT` token after an `IDENT` — which only the predicate rule consumes). Worst case, raise priority on the predicate alt.
- **Comparison vs. equivalence to null.** SQL says `field = null` is unknown. We're not SQL — picking "behaves like `IS NULL`" is friendlier for the markdown/frontmatter world where missing-vs-explicit-null is rarely a meaningful distinction. Just document it.
- **Cypher subset parity.** The two grammars are independent files. Don't add a feature on one side and not the other — the README's promise that Cypher `WHERE` mirrors the filter DSL is load-bearing.
