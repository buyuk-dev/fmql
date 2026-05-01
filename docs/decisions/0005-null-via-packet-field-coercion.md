---
id: 0005
title: Cypher `null` semantics ride on `packet_field`'s missing-to-None coercion
status: accepted
date: 2026-05-01
context_task: 0020
---

## Context

Task [0020](../tasks/0020-qlang-not-in-null-literal.md) adds three Cypher `WHERE` features: `null` value literal, `NOT IN [...]`, and `IS NOT NULL`. The task documents the semantics it wants:

> `null` matches packets where the field is missing **or** explicitly set to YAML `null`/`~` (i.e. same equivalence class as `IS NULL`); `t.field != null` is the inverse.

There were two ways to deliver that: (1) modify the filter ops in `packages/fmql/src/fmql/filters.py` (`_eq`, `_ne`, `_in`, `_is_null`, `not_in`) so they treat the `_MISSING` sentinel as equivalent to `None` when the comparison value is `None`, or (2) rely on the existing coercion that the Cypher execution path already performs.

`cypher/expr.py:48-64`'s `packet_field()` returns `None` for both absent fields and explicit YAML-null fields. The kwargs API path (`Query(ws).where(...)`) goes through `filters._get`, which preserves the `_MISSING` sentinel. So at the Cypher predicate-eval boundary, missing and explicit-null are already merged into `None` — without any change to the filter ops.

The same coercion is what made the existing `IS NULL` predicate match absent fields too (test `test_exec_where_is_null_matches_absent_in_cypher`).

## Decision

Lean on the existing `packet_field` coercion for the new null-related semantics. **Do not modify `filters.py`.** Specifically:

- `t.f = null` → `_eq(None, None)` → True for missing-or-explicit-null packets, False otherwise. Falls out of `_eq`'s plain-equality path.
- `t.f != null` → `_ne(None, None)` → False for missing-or-explicit-null packets, True for present-non-null. The inverse, by definition.
- `t.f IN [null, ...]` → `_in(None, [...])` → True when `None` is a list member. Standard list-containment.
- `t.f NOT IN [...]` → existing `not_in` op (`filters.py:240`). Already in the operator registry; only the Cypher grammar lacked an entry point.
- `t.f IS NOT NULL` → compiled to `NotNode(PredNode(is_null=True))`. Same observed behavior as a hypothetical `is_not_null` op, given the coercion.

The compile-side change is the smallest possible: three new transformer methods (`p_not_in`, `p_not_null`, `v_null`) and three grammar alternatives. No new filter op, no behavior change to the kwargs API.

## Rationale

- **Smaller blast radius.** Touching `filters.py` would re-shape the kwargs path's behavior too (e.g. `Query(ws).where(field__eq=None)` would start matching absent fields). Task 0020 is scoped to Cypher; broadening it via filter changes would break the kwargs contract documented in the README operator table (`is_null` → "field value is explicitly `null`").
- **Consistent with existing `IS NULL`.** The current `IS NULL` already gets its missing-matches-null semantics via the same `packet_field` coercion. Plumbing the new `null` literal through the same path keeps the language internally consistent — anything that says `null` (predicate or literal) means the same thing.
- **No new op to maintain.** `is_not_null` would have been a one-liner in `_OPS`, but `NotNode(PredNode(is_null))` reuses an existing op verbatim and is observably identical.

## Consequences

- **Cypher and the kwargs API diverge for `null` / `_MISSING` cases.** This was already the case for `IS NULL` (task 0021's changelog flagged the divergence) and continues to be the case for the new operators. The README's kwargs operator table is unchanged: `is_null` and `not_in` still describe the kwargs semantics ("explicitly `null`"; "is present and not in the list"). The Cypher `WHERE` operator section now documents the Cypher-side null equivalence class (missing-or-explicit-null).
- **`t.f NOT IN ["a", "b"]` (no `null` in the list) matches absent fields under Cypher.** Because absent → `None`, and `None` is not in `["a", "b"]`, the predicate is True. To exclude absent packets, write `t.f NOT IN [null, "a", "b"]` — which is the natural shape the task was designed around.
- **`SET t.f = null` is unaffected** — `null` was already addressable via `IS NULL` in `WHERE`, but the `value` rule did not allow it on the right-hand side of `=`. With this task it does, and `value_atom` → `value` (grammar.lark:21) means `null` is now a valid `SET` RHS too. Behavior on the executor side: writing `None` into frontmatter via ruamel emits `field:` (empty value, parsed back as null on next load). Out of scope to harden further unless a task specifically calls for it.

## Alternatives considered

- **Special-case `None` in the filter ops.** Rejected: changes kwargs API behavior, and the divergence already exists for `IS NULL`. Adding more divergence in a different direction would make the two paths harder to reason about, not easier.
- **A dedicated `is_not_null` op.** Rejected as redundant: `NotNode(PredNode(is_null))` already produces the desired behavior, and adding a third null-related op (`is_null`, `is_not_null`, plus an implicit "null-equality" arm in `_eq`) would clutter `_OPS` for no observable benefit.
- **Reject `null` in `IN` lists.** Would force users back to the verbose `NOT (x IN [...]) AND x IS NOT EMPTY` shape that the task is explicitly trying to retire. Rejected.
