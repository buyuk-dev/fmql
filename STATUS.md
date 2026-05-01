---
session_id: 82e6357f-d433-4494-a791-059005525f1e
task_id: 21
branch: feature/deprecate-qlang-rename-cypher-to-query
phase: done
started: '2026-05-01T19:54:04Z'
---
# Status

Task **0021 — Deprecate qlang; rename `fmql cypher` to `fmql query`** finalized.

Branch: `feature/deprecate-qlang-rename-cypher-to-query`. Plan: `~/.claude/plans/get-started-on-task-purring-trinket.md`.

## Outcome

- qlang is gone. `packages/fmql/src/fmql/qlang/` deleted.
- `fmql cypher` is gone as a standalone command. `fmql query` now speaks the Cypher subset and is a strict superset of the old qlang query: it absorbs `--follow / --depth / --direction / --include-origin / --search / --index / --index-location / --format paths`.
- `fmql subgraph` and `fmql index --filter` route their seed argument through the Cypher parser (via `Query.cypher()`).
- README, design.md, both SKILL.md files, and the CHANGELOG all reflect Cypher as the single query language. Task 0006 closed as superseded by 0021. Task 0020 re-scoped to Cypher-only. Task 0010's qlang-parity bullet removed. Task 0011's qlang doc-pairing reference cleaned up.
- Two ADRs added under `docs/decisions/`:
  - `0001-merge-not-rename-fmql-query.md` — why the new `fmql query` is a merge of the old query + cypher commands, not a literal rename.
  - `0002-cypher-seeds-via-query-cypher.md` — why seed parsing reuses `Query.cypher()` instead of a new helper module.
- Code review pass (the `/simplify` skill): lifted `effective_fmt` computation to the top of `query_cmd`; eliminated double-parse on the Query path by passing the AST through to `compile_cypher_ast` directly and seeding `Query` via `IdSetStage`; promoted `_parse_depth` to a shared `cli/_run.parse_depth`; created `tests/cli/conftest.py` with a shared `write_blocked_ws` fixture; renamed `_ordering_ws` → `ordering_ws`.

## Verification

- `make format` — clean (4 files reformatted on first run).
- `make lint` — clean after one E501 fix in `cmd_query.py`'s `--format` help text.
- `make test` — `fmql` 480 passed, `fmql-semantic` 56 passed.
- Smoke-tested by hand on a synthetic workspace: `fmql query` with `paths` / `rows` / `json` formats, `--follow`, `RETURN count(...)`, multi-var `RETURN`, `fmql subgraph`, `fmql update --dry-run`, and confirmed `fmql cypher` exits 2 with "No such command 'cypher'".

## Notes

- Behaviour change worth flagging: Cypher's `IS NULL` matches absent fields (treats absent as null). qlang's `IS NULL` was strict (only explicit nulls). The ported test was renamed from `test_is_null_false_for_absent` to `test_exec_where_is_null_matches_absent_in_cypher` to document the divergence rather than assert the qlang behaviour. Task 0020 may want to address this.
- Task 0020's file slug still reads `qlang-not-in-null-literal.md` — kept as-is to preserve backlinks from tasks 0021 and 0022.
