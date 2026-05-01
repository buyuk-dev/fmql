---
session_id: ba719742-9236-4f88-937f-7a775126413c
task_id: 20
branch: feature/qlang-not-in-null-literal
phase: done
started: '2026-05-01T20:54:43Z'
---
# Status

Task **0020 — `NOT IN`, `null` literal, and `IS NOT NULL` in Cypher `WHERE`** finalized.

Branch: `feature/qlang-not-in-null-literal`. Plan: `~/.claude/plans/get-started-on-task-ethereal-mitten.md`.

## Outcome

- Three new alternatives in `packages/fmql/src/fmql/cypher/grammar.lark`: `qualified_ident NOT_KW IN_KW [...]` → `p_not_in`, `qualified_ident IS_KW NOT_KW NULL_KW` → `p_not_null`, and `NULL_KW` as a `value` alternative → `v_null`. No new tokens; reuses the existing `NULL_KW` / `NOT_KW` / `IN_KW` / `IS_KW` lexemes.
- Three matching transformer methods in `packages/fmql/src/fmql/cypher/compile.py`. `p_not_null` returns `NotNode(PredNode(Predicate(... is_null ...)))` — reuses the existing `is_null` filter op rather than introducing a new `is_not_null` op. `v_null` returns Python `None`.
- **No `filters.py` changes.** `cypher/expr.py:packet_field` already coerces missing fields to `None` before predicates evaluate, so the documented "null = absent or explicit YAML null" semantics fall out of the existing `_eq` / `_ne` / `_in` / `_is_null` / `not_in` ops unchanged. Rationale recorded in ADR `0005-null-via-packet-field-coercion.md`.
- 14 new tests in `packages/fmql/tests/test_cypher.py` covering `IS NOT NULL`, `IS NULL`/`IS NOT NULL` partition, `= null`, `!= null`, `= null`/`!= null` partition, `NOT IN`, `NOT IN [null, …]`, `IN [null]`, `IN [null, …]`, parser whitespace/case tolerance for `NOT IN` and `IS NOT NULL`, case-insensitive `null` literal, and a no-regression check that `NOT (x IN [...])` and `x NOT IN [...]` produce identical results.
- New shared fixture `null_partition_ws` in `packages/fmql/tests/conftest.py` — three packets (absent / explicit-null / present) — used by the three `= null` / `!= null` tests.
- README `WHERE` operator section updated: added `NOT IN [v1, v2]` and `IS NOT NULL` to the operator list, added `null` to the values list, added a paragraph documenting the null equivalence class, and added two CLI examples.
- Code-review pass (`/simplify`): consolidated the three identical `make_workspace({absent, explicit, present})` blocks into the new shared fixture. Other findings (helper-extract for `p_in`/`p_not_in`, in-list-test fixture consolidation, dedicated `is_not_null` op) were considered and rejected as premature abstraction or sub-microsecond overhead.
- Workflow housekeeping: archived prior STATUS body to `docs/changelog/0002.md`; flipped task 0020 to `done`; updated `docs/roadmap.md`.

## Verification

- `make format` — clean (1 file reformatted on first run: `tests/test_cypher.py`).
- `make lint` — clean.
- `make test` — `fmql` 508 passed, `fmql-semantic` 56 passed.

## Notes

- The Cypher parser is Earley (`compile.py:91`), not LALR, so the shift/reduce conflict the task spec warned about doesn't arise. No grammar precedence tweaks were needed.
- The kwargs API path remains unchanged — `Query(ws).where(field__not_in=…)` and `field__is_null=True` keep their existing semantics. The Cypher↔kwargs divergence around missing-vs-null (Cypher merges them via `packet_field`; kwargs preserves `_MISSING` via `filters._get`) was already present for `IS NULL` and is now consistent for the new operators too.
- `null` is now a valid `SET` RHS value too, since `value_atom` → `value` (grammar.lark:21). Behaviour: writing `None` into frontmatter via ruamel emits `field:` (empty value, parsed back as null on next load). Out of scope to harden further unless a future task explicitly addresses it.
