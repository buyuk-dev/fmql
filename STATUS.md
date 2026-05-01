---
session_id: aa5575b7-b768-4524-b41f-9854942b7214
task_id: 10
branch: feature/cypher-limit-clause
phase: done
started: '2026-05-01T21:22:49Z'
---
# Status

Task **0010 — Cypher `LIMIT N` clause and `--limit` flag on `fmql query`** finalized.

Branch: `feature/cypher-limit-clause`. Plan: `~/.claude/plans/get-started-on-task-generic-gem.md`.

## Outcome

- Grammar (`packages/fmql/src/fmql/cypher/grammar.lark`): new `LIMIT_KW.5` token and `limit_clause: LIMIT_KW INT` rule, slotted into the top-level cypher rule after `order_clause?`. `INT: /\d+/` admits no minus, so negative literals fail at parse time.
- AST (`cypher/ast.py`): added `limit: Optional[int] = None` to `CypherAST`. No new dataclass — LIMIT is a single integer.
- Compiler (`cypher/compile.py`): dropped the `(r"\bLIMIT\b", "LIMIT")` entry from `_UNSUPPORTED_KEYWORDS`; added a `limit_clause` transformer that returns `("__limit__", int(...))`; threaded the value through `_Compiler.cypher()` mirroring the `__order__` pattern.
- Executor (`cypher/executor.py`): `_validate()` now rejects LIMIT without RETURN and negative limits (defensive — reachable only via hand-built ASTs). `compile_cypher_ast` short-circuits `LIMIT 0` via a new `_empty_result()` helper instead of running projection just to throw the rows away. `LIMIT N > 0` slices `result.rows` post-projection through a private `_apply_limit()` that also clears the `is_scalar`/`scalar` fields when an empty slice would otherwise leave a stale count behind.
- CLI (`cli/cmd_query.py`): new `--limit N` option with Typer's `min=0` (replaces an earlier `parse_limit` helper that turned out to duplicate Typer's bound check). On the direct path, `--limit` is folded into `ast.limit` via `dataclasses.replace` before `compile_cypher_ast` runs — the executor sees a single value, no double-application. On the `--follow`/`--search` path, `itertools.islice(q, limit)` caps the post-traverse packet stream so graph traversal can short-circuit instead of materializing the full result.
- Tests: 13 new LIMIT cases in `tests/test_cypher.py` (parse / executor / scalar count / SET-with-LIMIT) and 9 new CLI cases in `tests/cli/test_query_cmd.py` (in-query LIMIT, `--limit` flag, both directions of "more restrictive wins," `LIMIT 0`, negative-flag error, `--follow` integration, scalar count). The `LIMIT 10` line in `test_unsupported_constructs_raise` was replaced with `SKIP 5` to lock the deferred-keyword contract.
- Docs: README's "Query syntax" block now documents `LIMIT N`; the Features bullet and Common-flags list mention it. ADR `docs/decisions/0006-limit-applies-to-return-projection.md` records the post-projection slicing decision and the `SET`/`REMOVE` interaction.
- `/simplify` review pass: collapsed the CLI's two-slice composition into a single AST-level merge (removed `apply_limit` import from CLI, deleted the redundant `parse_limit` helper from `cli/_run.py`, made `_apply_limit` private to `executor.py`); added `LIMIT 0` short-circuit and `_apply_limit` early-return when `limit >= len(rows)`; switched the follow/search path to `itertools.islice` so traversal stops early; dropped two test comments that restated the test name or duplicated the ADR.
- Workflow housekeeping: archived prior STATUS body to `docs/changelog/0003.md`; flipped task 0010 to `done`; updated `docs/roadmap.md`.

## Verification

- `make format` — clean.
- `make lint` — clean.
- `make test` — `fmql` 531 passed, `fmql-semantic` 56 passed.

## Notes

- **SKIP deferred.** Task 0010 explicitly flagged the decision; SKIP stays in `_UNSUPPORTED_KEYWORDS` and gets its own follow-up. Reasoning recorded in the task file's Notes: SKIP needs a separate validation rule (must require ORDER BY for determinism), its own CLI ergonomics question (`--skip N`?), and its own SET/REMOVE behavior call.
- **`MATCH (t) SET t.tag = 1 RETURN t LIMIT 1` tags every matching `t`** — `SET` sees all bindings; `LIMIT` only caps `RETURN` projection. Without `WITH` there's no clean way to scope writes by `LIMIT`. Documented in ADR 0006 and verified by `test_exec_limit_with_set_applies_writes_to_all`.
- **`LIMIT` is a reserved word now.** Frontmatter fields named `limit` (any case) can no longer be referenced in Cypher — same constraint as the other Cypher keywords (RETURN, WHERE, etc.). Affected workspaces would need to rename the field.
- The first lint-clean review attempt suggested using `_is_kw_token(c)` in `limit_clause`'s child filter; that helper actually returns True for *any* Token (not just keywords), which would skip the `INT` data token too. Reverted to `isinstance(c, Token) and c.type == "INT"` after the test failure surfaced the misnomer. Worth knowing for future grammar work.
