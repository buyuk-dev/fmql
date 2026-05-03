---
id: 0027
title: Backtick-quoted identifiers for hyphenated frontmatter keys (`t.\`org-type\``)
status: todo
priority: 2
created: 2026-05-03
updated: 2026-05-03
issue: https://github.com/buyuk-dev/fmql/issues/15
tags: [cypher, grammar, compatibility, frontmatter, ux, bug]
depends_on: []
phase: cypher
---

## Goal

YAML 1.2 allows hyphens in plain scalar keys, and they're widespread in the wild — Hugo, Jekyll, Obsidian, and countless hand-rolled schemas all use forms like `org-type`, `last-modified`, `cover-image`. fmql currently cannot query any of them: `IDENT` in the Cypher grammar is `[A-Za-z_][A-Za-z0-9_]*` (`packages/fmql/src/fmql/cypher/grammar.lark:132`), and the standard Cypher escape — backticks — is not accepted either. Per [issue #15](https://github.com/buyuk-dev/fmql/issues/15), the workaround is to rename every hyphenated frontmatter key in the corpus to `snake_case`, which is unacceptable for users who don't control the schema (existing repos, third-party templates, exported data).

Add Cypher-standard backtick escaping so `MATCH (t) WHERE t.` `` `org-type` `` ` = "school" RETURN t` works. This keeps the grammar unambiguous (no collision with the binary `+` from [0026](0026-cypher-binary-plus-list-concat.md) or any future `-`) and aligns fmql with how Neo4j users already escape complex identifiers.

## Acceptance criteria

- [ ] Grammar adds a backtick-quoted identifier token in `packages/fmql/src/fmql/cypher/grammar.lark`, accepted in **field-name position only** — i.e. wherever a frontmatter key appears, not pattern variables, labels, function names, list-comp bindings, or relationship types.
- [ ] Concretely, the field-name slot in both `qualified_ident` (line 83) and `return_item`'s `r_field` rule (line 60) accepts either bare `IDENT` or backtick-quoted form. Suggested approach: introduce a `field_name` non-terminal that resolves to either, and reuse it in both places.
- [ ] The backtick-quoted form accepts any non-empty sequence of non-backtick characters: `` `org-type` ``, `` `last modified` ``, `` `日本語` ``, `` `field.with.dots` ``, etc. No support for embedded literal backticks (i.e. no `` `` `` escape) — explicitly out of scope for v1; document and reject with a clear parse error.
- [ ] Empty backticks (`` `` ``) and unterminated backtick (`` ` ``) produce a clear parse error, not silent acceptance.
- [ ] Bare `IDENT` continues to work unchanged — backticks are optional escape, never required. `t.status` and `` t.`status` `` parse to the same predicate.
- [ ] Compile-side: backtick-quoted tokens are unwrapped to their inner string before being stored as the field name on `Predicate`, `SetItem`, `RemoveItem`, `ReturnField`, and `OrderKey`. Downstream code already works with plain field-name strings, so this is a one-spot strip in `compile.py:qualified_ident` (and the analogous `r_field` builder).
- [ ] Works in every clause that takes a field name:
  - `WHERE t.` `` `org-type` `` ` = "school"`
  - `WHERE t.` `` `org-type` `` ` IN ["school", "company"]`, `IS NULL`, `IS NOT EMPTY`, `CONTAINS`, etc.
  - `SET t.` `` `org-type` `` ` = "vendor"`
  - `SET t.` `` `tags` `` ` += "x"` (parses identically to `SET t.tags += "x"`)
  - `REMOVE t.` `` `org-type` ``
  - `RETURN t.` `` `org-type` ``
  - `ORDER BY t.` `` `org-type` `` ` DESC`
  - As an operand in a binary `+` expression: `SET t.` `` `display-name` `` ` = t.` `` `first-name` `` ` + " " + t.` `` `last-name` ``.
- [ ] Tests cover (in `packages/fmql/tests/test_cypher_*.py`, split across whichever test modules already exercise each clause):
  - Filter on hyphenated key in `WHERE` — exact match, `IN`, `IS NULL`, `CONTAINS`.
  - `SET` and `REMOVE` on hyphenated key, with diff verification (the field is actually written / removed in the YAML body).
  - `RETURN t.` `` `org-type` `` projects the value correctly under the column header `t.org-type` (or whatever naming convention `r_field` already uses for hyphen-free fields — match it).
  - `ORDER BY` on hyphenated key.
  - Mixed: a query that uses both backtick-escaped (`` `org-type` ``) and bare (`status`) field names in the same `WHERE`.
  - Identity: `t.status` and `` t.`status` `` produce the same parsed AST.
  - Parser errors: empty backticks, unterminated backtick, backticks in disallowed position (e.g. as a pattern variable: `` MATCH (`t`) ... `` should be a parse error with a message hinting "labels and pattern variables don't support backticks").
- [ ] README updates:
  - The "Cypher subset" section gains a one-line note: "Frontmatter keys with hyphens, dots, or other non-identifier characters can be backtick-escaped, e.g. `` t.`org-type` ``. This matches Neo4j's escape syntax."
  - The `WHERE` operator table gets a small example row using the backtick form (shows users it exists without forcing them to find it in prose).
  - If a "Cypher subset — divergences from Neo4j" section already exists, this is *not* a divergence — fmql now matches Neo4j's escape behavior. Don't add a row; only add to the matching-Cypher narrative.
- [ ] `make format && make lint && make test` clean.

## Notes

### Why backtick escape, not native hyphens in `IDENT`

The bug report's first preferred resolution is "natively support hyphens in identifiers." Reject this:

1. **Operator collision.** Binary `+` just shipped in [0026](0026-cypher-binary-plus-list-concat.md), and `+ "_suffix"` style concatenation is exactly the kind of expression a hyphenated identifier would shadow. `t.org-type` would have to disambiguate between "the `org-type` field" and "`t.org` minus `type`" purely by lookahead. Even though `-` isn't a defined operator today, locking out future binary `-` (subtraction) for an unforced-error reason isn't worth it.
2. **Cypher precedent.** Neo4j itself does not allow hyphens in unquoted identifiers; the canonical fix is backticks. Aligning with Neo4j here is the path of least surprise for users coming from Cypher.
3. **YAML keys are arbitrary.** Hyphens are common but not the only non-`IDENT` characters that appear in frontmatter — dots (`a.b.c`), spaces (`last modified`), and Unicode (`日本語`) all show up. Native-hyphen support would solve one corner of a broader problem; backticks solve all of them.

### Grammar sketch

```lark
qualified_ident: IDENT ("." field_name)?

return_item: COUNT_KW "(" IDENT ")"            -> r_count
           | IDENT "." field_name              -> r_field
           | IDENT                             -> r_var
           | ESCAPED_STRING                    -> r_string
           | SIGNED_NUMBER                     -> r_number

?field_name: IDENT
           | BACKTICK_IDENT

BACKTICK_IDENT: /`[^`]+`/
```

LALR-safe: `BACKTICK_IDENT` starts with `` ` ``, which isn't a leading character of any other token. Lark's lexer matches it greedily; the runtime regex `/`[^`]+`/` rejects empty content and unterminated forms at lex time.

### Compile-side strip

`compile.py:qualified_ident` (line 393) does `idents = [str(c) for c in children if _is_ident(c)]`. Add a sibling helper that recognizes `BACKTICK_IDENT` and strips the surrounding backticks:

```python
def _ident_value(tok):
    s = str(tok)
    if s.startswith("`") and s.endswith("`"):
        return s[1:-1]
    return s
```

Apply at every site that previously did `str(child)` on a field-name token. Search for those sites with: `qualified_ident`, `r_field`, `set_item`, `remove_clause`, `order_ref_qual` — they all funnel into `Predicate.field`, `SetItem.field`, `RemoveItem.field`, `ReturnField.field`, `OrderKey.field` respectively.

### Watch-outs

- **Validator recursion.** `_check_value_expr_vars` walks `qualified_ident` nodes; the change replaces `IDENT` with `field_name` in the field slot but the resolved string value is the same. Add a parser regression test that `SET t.` `` `org-type` `` ` = t.` `` `org-type` `` ` + "_v2"` round-trips through the validator without a "missing var" complaint.
- **Diff and error messages.** Per-packet error messages currently print `field "<name>"` with the bare name. After unwrap, hyphenated names will show up as `field "org-type"` — verify message is still readable (it is, but pin in a test).
- **Pattern variable collision.** `MATCH (` `` `t` `` `)` should *not* parse — pattern variables stay snake_case. Confirm with a parse-error test, and make the error point to the right place ("backticks are only valid for field names after a dot").
- **Frontmatter parser side.** No change. The frontmatter YAML parser already happily accepts hyphenated keys; this task is purely about the query language being able to *reference* them.

### Out of scope

- **Embedded literal backticks** (`` `field``with``backtick` ``). Cypher's escape is `` `` ``; fmql v1 rejects this with a clear parse error. Add a follow-up task only if a user actually has such a key.
- **Backticks on labels, pattern variables, function names, or relationship types.** All four stay `IDENT`-only. Document the restriction; the parse error tests pin it.
- **Python kwargs API support for hyphenated keys.** `q.where(org_type="school")` cannot match `org-type` because Python identifiers reject hyphens. The `**{"org-type": "school"}` workaround already works (the kwargs API just looks up the key in the YAML map). Document this in the kwargs section as a known gotcha; a richer solution (e.g. `Filter("org-type", "eq", "school")`) is a separate task if demand appears.
- **Validation that the backtick-escaped name corresponds to an actually-present frontmatter key.** Schemaless engine; missing keys behave the same as for bare-IDENT field names (predicate evaluates to false / unknown depending on the operator). No special validation.
- **Quoting variants.** No support for `"double-quoted"` or `[bracket-quoted]` identifiers. Backticks are the Cypher standard and that's what we match.
