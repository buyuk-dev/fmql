---
id: 0026
title: Add binary `+` to Cypher value expressions for Neo4j-portable list concatenation
status: done
priority: 2
created: 2026-05-03
started: 2026-05-03
completed: 2026-05-03
tags: [cypher, grammar, compatibility]
depends_on: [0022]
phase: cypher
---

## Goal

Today, fmql's only way to append to a list is `SET t.tags += "x"`. That spelling is the headline divergence flagged in [ADR 0008](../decisions/0008-cypher-divergences-from-neo4j.md): Neo4j's `+=` is map-merge at node level and is undefined at property level, so the portable Neo4j idiom for list-append is `SET n.tags = n.tags + "x"` (or `+ ["x"]` to extend). fmql doesn't accept that form at all — the grammar's `value_expr` has no binary `+` operator (see `packages/fmql/src/fmql/cypher/grammar.lark:15-19`), so the Neo4j-portable rewrite of an fmql `+=` query is a parse error.

This task adds binary `+` on `value_expr` so the portable form works. It does **not** revisit ADR 0008's lock-in of `+=` semantics — both spellings coexist, and the README guides users toward `+` when portability matters and `+=` when initialize-when-absent ergonomics matter.

## Acceptance criteria

- [ ] Grammar adds binary `+` to `value_expr` in `packages/fmql/src/fmql/cypher/grammar.lark`. Left-associative; precedence below `NOT` (so `NOT a + b` parses as `(NOT a) + b`, matching Cypher).
- [ ] AST gains a `BinaryOp` node (or extends the existing `UnaryOp` shape into a shared `Op` family — implementer's call) with `op = "add"`.
- [ ] `compile.py` builds the AST node for `+`. Validation in `_check_value_expr_vars` recurses through both operands.
- [ ] `expr.py` evaluates `+` with these rules, in priority order:
  - `list + list` → concatenation (extend; **not** nesting). `[1, 2] + [3]` → `[1, 2, 3]`.
  - `list + scalar` → append-element. `[1, 2] + 3` → `[1, 2, 3]`.
  - `scalar + list` → prepend-element. `0 + [1, 2]` → `[0, 1, 2]`.
  - `string + string` → string concatenation. `"a" + "b"` → `"ab"`.
  - `number + number` → numeric addition. `1 + 2` → `3`. Mixed int/float follows Python's coercion.
  - Any other type combination (e.g. `string + number`, `bool + anything`) → per-packet error, reported the same way `+=` against a non-list field is reported (see `test_cypher_set.py:169`).
  - `None` on either side → result is `None` (silent; consistent with how `field()` propagates missing values today).
- [ ] `+` works anywhere `value_expr` works: RHS of `SET t.field = …`, inside `list_lit`, inside `func_call` arguments, inside `list_comp` source/projection. (RETURN expressions stay literal-only — see "Out of scope".)
- [ ] `SET t.tags = t.tags + "x"` against an absent field is a per-packet error, **not** a silent initialize. Initialize-when-absent stays the unique ergonomic of `+=`. Document this asymmetry explicitly.
- [ ] Tests cover (in `packages/fmql/tests/test_cypher_set.py` or a new `test_cypher_binop.py`):
  - `list + list` extends (not nests) — directly contrasts with the `+=` nesting test on line 152.
  - `list + scalar` appends-element.
  - `scalar + list` prepends-element.
  - `string + string`.
  - `number + number` (int+int, int+float).
  - Mixed-type error (e.g. `"a" + 1`) reports per-packet error; other packets succeed.
  - `None` propagation: `t.missing + "x"` evaluates to `None` and the field is set to `None` (or whatever the documented behavior is — pin it in the test).
  - `t.list + [1] + [2]` left-associative chaining.
  - Inside `list_lit`: `SET t.tags = [t.first + "_suffix", "literal"]`.
  - Inside `func_call`: `SET t.x = field(resolve(t.id + "_v2", "id"), "title")` (or similar — proves operands carry through nested calls).
- [ ] README updates:
  - The `SET` operator table grows a row for `SET t.field = expr1 + expr2` with the type-rule summary.
  - The "Cypher subset — divergences from Neo4j" section grows a clarifying note under the `+=` row: "For Neo4j-portable list concat, use `SET t.tags = t.tags + "x"` instead. fmql's `+` follows Neo4j semantics; `+=` keeps fmql's initialize-when-absent ergonomic and the nesting-on-list-RHS behavior pinned by ADR 0008."
  - A new short "Portability tips" subsection (or footnote on the divergences section) listing the rewrite for users who want their queries to also run on Neo4j.
- [ ] `make format && make lint && make test` clean.

## Notes

### Grammar sketch (`packages/fmql/src/fmql/cypher/grammar.lark`)

Today's `value_expr`:

```lark
?value_expr: value_atom
           | func_call
           | NOT_KW value_expr               -> ve_not
           | list_lit
           | list_comp
```

Proposed (introduces `add_expr` between `value_expr` and the unary/atom layer):

```lark
?value_expr: add_expr

?add_expr: add_expr PLUS unary_expr          -> ve_add
         | unary_expr

?unary_expr: NOT_KW unary_expr               -> ve_not
           | value_atom
           | func_call
           | list_lit
           | list_comp

PLUS: "+"
```

Left-recursive `add_expr` is fine in lark's LALR mode — it's the canonical way to express left-associativity. `PLUS_EQ` already exists (line 118) and is a separate token, so there's no lexer ambiguity between `+` and `+=`.

### Why add `+` rather than change `+=`

ADR 0008 explicitly locked `+=` semantics as stable surface and called out that changing them later would itself be a breaking change. Three reasons not to revisit that decision in this task:

1. **Initialize-when-absent is genuinely useful for frontmatter** in a way it isn't for Neo4j. Neo4j nodes always exist before `SET`, so the analogue never came up; in fmql, the field may not be there yet, and `+=` Just Works.
2. **The portability problem is solved additively.** Adding `+` lets users who care about Neo4j-portability rewrite mechanically; users who don't, keep their existing queries.
3. **Two operators with two different shapes is honest about what they do.** `+=` is fmql sugar (initialize-or-append-as-element). `+` is the Neo4j-aligned primitive. The README divergences section becomes a recipe ("use `+` for portability, `+=` for ergonomics") instead of an apology.

If a future task does want to revisit `+=` (e.g. align nesting-on-list-RHS to extend), this task makes that move easier: `+` is already present as the Neo4j-semantics anchor, so `+=` could be defined as `t.f = t.f + expr` with the initialize-when-absent shim layered on top.

### Type coercion rules

The proposed rules above match Neo4j's `+` semantics for the type combinations Neo4j defines, and reject the rest with a clear per-packet error rather than silent surprises:

- Neo4j defines `list + list` (extend), `list + scalar` (append), `scalar + list` (prepend), `string + string` (concat), and arithmetic `number + number`. We match all five.
- Neo4j allows `string + number` with implicit string coercion (`"a" + 1` → `"a1"`). **Reject** in fmql — it's a frequent foot-gun in JS/Python and frontmatter has no compelling use case. Force users to be explicit.
- `None` propagation matches how `field()` already behaves (see expr.py:eval_value_expr for the func_call broadcast path) — keeps mental model consistent.

### Where `+` is allowed

- `SET t.field = …` RHS — primary use case.
- `list_lit` elements — `SET t.x = [t.a + t.b, t.c]`.
- `func_call` arguments — `SET t.x = field(resolve(t.id + "_v2", "id"), "title")`.
- `list_comp` source and projection — `SET t.x = [v IN t.list + ["extra"] | v + "_done"]`.

`WHERE` predicates and `RETURN` items keep their existing leaf-only shape — see Out of scope.

### Watch-outs

- **LALR conflict between `+` and `PLUS_EQ`.** Both tokens start with `+`, but `PLUS_EQ` is a maximal-munch literal (`"+="`) and `PLUS` is `"+"`; lark's lexer prefers the longer match, so `set_op` continues to consume `+=` and `add_expr` continues to consume `+`. Verify with a parse test that `SET t.f += t.g + "x"` parses as `SET t.f += (t.g + "x")`, not anything else.
- **Precedence vs. `NOT`.** `NOT` is unary; placing `add_expr` above `unary_expr` gives `NOT a + b` → `(NOT a) + b`, which matches Cypher. Pin in a parser test.
- **`None` semantics in the validator.** `_check_value_expr_vars` (compile.py) recurses for the existing operand-bearing nodes; make sure the new `BinaryOp` is added to that recursion or the validator will silently skip type/var checks on operands.
- **Per-packet error reporting.** The existing `+=` non-list error path produces an error tuple with a packet id; reuse that same path for `+` type-mismatch errors so the user-facing format is consistent.
- **String-vs-number coercion temptation.** Don't add it. It's the kind of "convenience" that papers over real bugs in user queries (`SET t.title = t.year + " summary"` silently making "2024 summary" or " summary" depending on field presence). Better to error and force `str(t.year)` when we add it, or a `concat(...)` function.

### Out of scope

- **Other binary operators.** Only `+`. `-`, `*`, `/`, `%` are not in scope — no current fmql query needs them, and adding the full arithmetic set widens the grammar surface for no demand pull. Revisit when a concrete use case appears.
- **Changing `+=` semantics.** ADR 0008 lock-in stands. This task is purely additive.
- **Expressions in `RETURN`.** RETURN items are still literal-only (`r_field`, `r_var`, `r_string`, `r_number`, `r_count`); arithmetic in RETURN projections is its own task. The grammar change keeps `return_item` untouched.
- **Expressions in `WHERE`.** `predicate` continues to take `qualified_ident cmp_op value` shapes only. Computed comparisons (`WHERE t.a + 1 > t.b`) are out of scope; raise a separate task if needed.
- **String concatenation operator other than `+`.** No `||` (SQL-style) or `concat()` function. `+` covers it.
- **Map-merge `+=`.** Still not implemented; ADR 0008 covers the rationale.
