---
session_id: 2e1fdda8-ef2f-4e75-8c88-7fe66194a9da
task_id: 26
branch: feature/cypher-binary-plus-list-concat
phase: done
started: '2026-05-03T21:05:40Z'
---
Task **0026 — Add binary `+` to Cypher value expressions for Neo4j-portable list concatenation** finalized.

Branch: `feature/cypher-binary-plus-list-concat`. Plan: `~/.claude/plans/get-started-on-task-joyful-koala.md`.

## Outcome

- **`packages/fmql/src/fmql/cypher/grammar.lark`**: layered the value-expr grammar — `?value_expr: add_expr`, with `?add_expr: add_expr PLUS unary_expr` (left-associative) sitting above `?unary_expr` (which carries `NOT_KW`, `value_atom`, `func_call`, `list_lit`, `list_comp`). New `PLUS: "+"` token next to the existing `PLUS_EQ`; lark's longest-match lexer rule keeps `+=` consumed by `set_op` and `+` consumed by `add_expr` with no ambiguity.
- **`packages/fmql/src/fmql/cypher/ast.py`**: new `BinaryOp(op, left, right)` frozen dataclass; extended the `ValueExpr` union to include it. Mirrors the pre-existing `UnaryOp` shape.
- **`packages/fmql/src/fmql/cypher/compile.py`**: `ve_add` transformer builds the `BinaryOp(op="add", ...)` node from the three children lark hands it; extended `_to_value_expr`'s isinstance tuple to accept `BinaryOp`.
- **`packages/fmql/src/fmql/cypher/executor.py`**: validator (`_check_value_expr_vars`) recurses through both operands. The per-binding eval at `_build_edit_plan` is wrapped in a narrow `try / except BinaryOpError`; on catch, the message is recorded in a new `errors_by_pid: dict[PacketId, str]` (first-error-wins) and the binding's set/append bookkeeping is skipped. The op-assembly loop emits a `kind="error"` `EditOp` first for any errored pid and `continue`s, so no other ops are queued for that file.
- **`packages/fmql/src/fmql/cypher/expr.py`**: new `BinaryOpError(CypherError)` subclass; `BinaryOp` arm in `eval_value_expr`; new `_eval_add(left, right)` helper applying the type-rule priority order — None propagation → list+list extend → list+scalar append → scalar+list prepend → str+str → num+num → `BinaryOpError`. `bool` is excluded from the numeric branch so `True + 1` errors instead of silently becoming `2`. List-concat branches use `[*left, *right]` spread for single-allocation results.
- **`packages/fmql/src/fmql/edits.py`**: extended the `OpKind` Literal with `"error"`; added a `kind == "error"` arm at the top of `_apply_op` that returns `op.args["message"]` verbatim. Routes through the existing `_apply_op` → `FileChange.error` → `ApplyReport.errors` plumbing untouched.
- **ADR** (`docs/decisions/0011-binary-plus-error-routing.md`): captures the per-packet error mechanism — why a narrow `BinaryOpError` subclass instead of catching plain `CypherError` (would change behavior of unrelated eval-time errors), why `kind="error"` instead of a side-channel on `EditPlan` (reuses existing apply pipeline), why error-op-first emission (matches `_apply_ops_to_map`'s short-circuit semantics), and four alternatives considered.
- **README** (`packages/fmql/README.md`): new row in the `SET` operators table for `SET t.field = expr1 + expr2` summarizing the type rules and the absent-field error; clarification appended to the `+=` divergences row pointing at `+` for portability; new "Portability tips" subsection listing the rewrites for users who want their queries to also run on Neo4j.
- **Tests** (14 new in `packages/fmql/tests/test_cypher_set.py`): list+list extends; list+scalar appends; scalar+list prepends; string+string; numbers (parametrized — int+int, int+float, float+float); per-packet mixed-type error with another packet succeeding; None propagation (sets the field to YAML `null`); left-associative chaining; `+` inside `list_lit`; `+` inside `func_call` (resolver-driven id-versioning roundtrip); parser pin for `+=` consuming the longer match (the bare `+` binds tighter than `+=` in `SET t.f += t.g + "x"`); parser pin for `NOT` binding tighter than `+`.
- **Workflow housekeeping**: archived prior STATUS body (task 0017) to `docs/changelog/0009.md`; flipped task 0026 to `done`; added task 0026 row to `docs/roadmap.md` under the cypher phase.

## Verification

- `make format` — reformatted one file (`executor.py`); rerun clean.
- `make lint` — clean first run (ruff + black --check).
- `make test` — `fmql` 605 passed (was 591; +14 from the new binop tests including parametrized cases), `fmql-semantic` 56 passed.

## Notes

- **`+=` lock-in stays.** ADR 0008's locked-in semantics for `+=` (initialize-on-absent at the property level, nest-on-list-RHS) are unchanged. `+` is the additive Neo4j-portable primitive; `+=` keeps its fmql-sugar ergonomics. The README divergences section now reads as a recipe ("use `+` for portability, `+=` for ergonomics") rather than an apology, which is what ADR 0008 anticipated.
- **`BinaryOpError` is internal stable surface, not public API.** It's imported by `executor.py` from `expr.py` for the per-binding catch. Tests assert on `ApplyReport.errors[N][1]` (the message string), not the exception class. ADR 0011 walks through why a narrow subclass instead of a generic `CypherError` catch — the latter would change behavior of `_negate` non-bool, `field()` arity errors, and unknown-function dispatch from compile-time abort to per-packet, which is the wrong shape for those cases.
- **Error-op-first ordering is load-bearing.** The op-assembly loop emits the error op and `continue`s, so non-error ops aren't even queued for an errored pid. `EditPlan.summary()` correctly reports "1 changed, 1 skipped (error), 0 no-op" rather than "0 changed, 1 skipped (error), 1 no-op-because-short-circuited." Symmetric with how `+=` non-list errors interact with subsequent ops on the same file via `_apply_ops_to_map`'s first-error-return.
- **Earley grammar handles left-recursion fine.** The `?add_expr: add_expr PLUS unary_expr` rule is left-recursive; lark's Earley parser handles this in polynomial time without ambiguity (the only `+`-producing rule recurses on the left, and `unary_expr` doesn't reach back to `add_expr`). LALR was mentioned in the task's grammar sketch but turned out to be a non-issue because the existing parser is Earley.
- **`_is_number` duplicates `filters._is_number`.** Same logic, both private to their modules. Resolved by inlining behavior — the alternative (cross-module private import or hoisting to a shared `_typing.py` module) is scope creep for a one-task win. If a third call site appears, that's the trigger for extraction.
- **The `kind="error"` op generalizes.** Any future eval-time per-packet error class can plug into the same routing by adding to the catch tuple in `_build_edit_plan` and reusing the existing `_apply_op` `"error"` arm. No changes needed at any apply-side site.
