---
id: 0010
title: Cypher LIMIT N clause and `--limit` flag on fmql query
status: todo
priority: 3
created: 2026-04-29
updated: 2026-04-29
tags: [cypher, qlang, cli, query]
depends_on: []
phase: cypher
---

## Goal

Cap the number of returned results, as in SQL `LIMIT N` / Cypher `LIMIT N`. Today the keyword is explicitly rejected at [packages/fmql/src/fmql/cypher/compile.py:59](../../packages/fmql/src/fmql/cypher/compile.py#L59); users have to fall back to `| head -n N` shell piping, which doesn't compose with downstream fmql commands.

## Acceptance criteria

- [ ] Remove `LIMIT` from the `_UNSUPPORTED_KEYWORDS` list in [compile.py](../../packages/fmql/src/fmql/cypher/compile.py).
- [ ] Add `LIMIT <int>` to the Cypher grammar ([cypher/grammar.lark](../../packages/fmql/src/fmql/cypher/grammar.lark)), AST ([cypher/ast.py](../../packages/fmql/src/fmql/cypher/ast.py)), and executor — must compose with `WHERE` and `ORDER BY` (apply ordering first, then truncate).
- [ ] Add the same construct to qlang's grammar and compiler so both surfaces have parity.
- [ ] Add a `--limit N` flag to `fmql query` that applies after any in-query `LIMIT` (taking the more restrictive of the two if both are present).
- [ ] `LIMIT 0` returns an empty result deterministically; negative values error.
- [ ] Decision required: do we also support `SKIP N` for pagination? It's the natural pair, but currently also rejected as unsupported. Capture the answer in the task or split SKIP into a follow-up.
- [ ] `make format && make lint && make test` clean.

## Notes

Asked about during the 2026-04-29 session. Pairs naturally with [0007](0007-describe-on-resolver-mismatch.md) only insofar as both are CLI ergonomics; otherwise standalone.
