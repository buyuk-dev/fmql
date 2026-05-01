---
id: 0010
title: Cypher LIMIT N clause and `--limit` flag on fmql query
status: done
priority: 3
created: 2026-04-29
updated: 2026-05-01
tags: [cypher, cli, query]
depends_on: []
phase: cypher
---

## Goal

Cap the number of returned results, as in SQL `LIMIT N` / Cypher `LIMIT N`. Today the keyword is explicitly rejected at [packages/fmql/src/fmql/cypher/compile.py:59](../../packages/fmql/src/fmql/cypher/compile.py#L59); users have to fall back to `| head -n N` shell piping, which doesn't compose with downstream fmql commands.

## Acceptance criteria

- [x] Remove `LIMIT` from the `_UNSUPPORTED_KEYWORDS` list in [compile.py](../../packages/fmql/src/fmql/cypher/compile.py).
- [x] Add `LIMIT <int>` to the Cypher grammar ([cypher/grammar.lark](../../packages/fmql/src/fmql/cypher/grammar.lark)), AST ([cypher/ast.py](../../packages/fmql/src/fmql/cypher/ast.py)), and executor — must compose with `WHERE` and `ORDER BY` (apply ordering first, then truncate).
- [x] Add a `--limit N` flag to `fmql query` that applies after any in-query `LIMIT` (taking the more restrictive of the two if both are present).
- [x] `LIMIT 0` returns an empty result deterministically; negative values error.
- [x] Decision: `SKIP N` is **deferred to a follow-up task** (see Notes below). LIMIT lands here on its own.
- [x] `make format && make lint && make test` clean.

## Notes

Asked about during the 2026-04-29 session. Pairs naturally with [0007](0007-describe-on-resolver-mismatch.md) only insofar as both are CLI ergonomics; otherwise standalone.

### SKIP deferred (2026-05-01)

`SKIP` is left in `_UNSUPPORTED_KEYWORDS` and gets its own follow-up task. Reasoning:

- Pagination needs `ORDER BY` to be deterministic — that's a separate validation rule (LIMIT alone is fine without ORDER BY).
- `--skip N` on the CLI is its own ergonomics question (do we want a flag? does it compose with `--follow`/`--search` the same way `--limit` does?).
- Keeping the LIMIT PR small makes review and revert easier.

A dedicated follow-up will pick the answer up; the existing `(r"\bSKIP\b", "SKIP")` entry in `_UNSUPPORTED_KEYWORDS` and the `SKIP 5` line in `test_unsupported_constructs_raise` lock the contract until then.
