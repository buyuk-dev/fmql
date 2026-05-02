---
phase: done
---
# Status

Task **0022 — Resolve Cypher-compatibility divergences (`+=` semantics, function-name collisions)** finalized.

Branch: `feature/cypher-compatibility-divergences`. Plan: `~/.claude/plans/get-started-on-task-whimsical-kite.md`.

## Outcome

- **Function registry** (`packages/fmql/src/fmql/cypher/expr.py`): dropped `_make_shortcut`, `_path`, and the `id` / `uuid` / `slug` / `path` entries from `REGISTRY`. The registry is now `{"resolve": _resolve, "field": _field}` — the two unambiguously fmql-specific primitives the four shortcuts decomposed into. Added a `_REMOVED_SHORTCUTS` map of name → explicit-composition hint and an `unknown_function_error(name)` factory; both the eval-time path (`eval_value_expr`) and the SET-validation path (`_check_value_expr_vars` in `executor.py`) call the same factory so the migration hint surfaces consistently from `query` and `update`.
- **`+=` keeps list-append**: no code change. The grammar already restricts `+=` to `qualified_ident set_op value_expr`, and `edits.py`'s append op already initializes a missing field to `[expr]`. The decision is purely "lock the existing semantics in," driven by tests and docs.
- **Tests**: replaced the two `test_slug_shortcut_*` cases in `test_cypher_expr.py` with a single parametrized `test_removed_shortcut_raises_with_hint` covering all four removed names and asserting the hint is in the error message. Added three explicit `+=` semantics tests in `test_cypher_set.py` — `test_append_initializes_when_field_absent`, `test_append_with_list_valued_rhs_nests`, `test_append_to_non_list_field_errors` — pinning the divergence the README now documents. Rewrote the `slug(t.deps)` example in `test_cypher.py:test_parse_set_function_call` to use `resolve(t.deps)`.
- **Docs** (`packages/fmql/README.md`): dropped the four shortcut rows from the built-in functions table; added a "**Differs from Neo4j**" inline note to the `+=` row in the SET operator table; added a new "**Cypher subset — divergences from Neo4j**" subsection right after Built-in functions, listing each divergence (`+=`, `id()`, `path()`, `uuid()` / `slug()`) with Neo4j-vs-fmql columns and a link to ADR 0008. Updated the Features bullet (drops `slug, id, uuid, path` from the function list) and the Common-commands `update` example.
- **ADR** (`docs/decisions/0008-cypher-divergences-from-neo4j.md`): single ADR covering both decisions. Sections: Context, Decision (`+=` and function-names sub-decisions), Rationale (why keep `+=` as list-append; why drop *all four* shortcuts not just the colliders; why one ADR), Consequences, Alternatives considered (`+=` rename, `+=` LHS-shape disambiguation, keep-and-document, namespace under `fmql.`, drop only direct colliders, two ADRs).
- **Workflow housekeeping**: archived prior STATUS body to `docs/changelog/0005.md` (already created); flipped task 0022 to `done`; updated `docs/roadmap.md`; new `docs/changelog/0006.md` records this finalization.

## Verification

- `make format` — clean.
- `make lint` — clean.
- `make test` — `fmql` 540 passed (was 536; +4 net: -2 slug-shortcut cases, +4 parametrized removed-shortcut cases, -1 slug-shortcut SET case, +3 `+=` semantics cases), `fmql-semantic` 56 passed.

## Notes

- **`unknown_function_error` factory** is the only new module-level function in `expr.py`. It exists so the eval-time and validation-time error paths share a single message format. Without it, `executor.py:_check_value_expr_vars` and `expr.py:eval_value_expr` would each format their own "unknown function" string and drift over time — the consolidating refactor was a small bonus on top of the actual task work.
- **`SET t.tags += t.extras` nests, not extends.** When the RHS is itself a list, the executor calls `current.append(value)` (per `edits.py:105`), so the list lands as a single nested element. The README and the new `test_append_with_list_valued_rhs_nests` test pin this. Diverges from Python's `list += list` muscle memory; documented loudly in the new divergences subsection.
- **Breaking change**: `id(v)` / `uuid(v)` / `slug(v)` / `path(v)` now raise `CypherError("function <name>() was removed; use <hint> instead")`. Migration is mechanical via the hint. The maintainer's local scripts and notes were grepped during this task per the plan; no out-of-tree fix-ups in this PR.
