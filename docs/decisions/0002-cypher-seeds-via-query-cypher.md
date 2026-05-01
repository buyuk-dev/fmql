---
id: 0002
title: Use `Query.cypher()` for seed parsing in subgraph and index commands
status: accepted
date: 2026-05-01
context_task: 0021
---

## Context

Task 0021 requires `fmql subgraph` to stop using `fmql.qlang.compile_query` for its seed argument and route through the Cypher parser instead. `fmql index --filter` has the same dependency.

Two options for how to share the parse-and-collect-ids logic:

1. Introduce a new helper module (e.g. `fmql.cli._seeds.cypher_seeds(query, ws) -> list[PacketId]`) and call it from both commands.
2. Reuse the existing `Query.cypher()` builder method, which already does the same thing.

## Decision

**Use `Query.cypher()` directly from both commands.** No new helper module.

`Query.cypher(text)` (defined at `packages/fmql/src/fmql/query.py:147`) already:

- Parses the input as Cypher.
- Validates that `RETURN` is a single `ReturnVar` (raises `CypherUnsupported` otherwise).
- Validates that `RETURN` is present (raises `CypherUnsupported` if it's a SET-only query).
- Executes the AST and produces a `Query` staged with the matched packet ids via `IdSetStage`.

Calling `Query(ws).cypher(query).ids()` from `cmd_subgraph.py` and `cmd_index.py` gives us exactly the seed list we need, with consistent error messages, and zero new code.

## Consequences

- `cmd_subgraph.py` and `cmd_index.py` shrink instead of growing.
- `Query.cypher()` becomes load-bearing for two more call sites; it was already used by the new merged `query_cmd` and by tests. If its validation rules change (e.g. relaxing the single-`ReturnVar` requirement), all four call sites benefit or break together — that's fine, the validation is the right contract for "select a set of packets."
- No `cli/_seeds.py` to maintain. If a third call site appears with different validation needs (e.g. accepting `RETURN a.field` and pulling pids out via lookup), revisit then — but YAGNI for now.

## Alternatives considered

- **`cli/_seeds.py` helper**: Was in the original plan. Rejected once I noticed `Query.cypher()` already does the work — adding a wrapper that delegates to it would be pure ceremony.
- **Inline parsing in each command**: 5-7 lines of `parse_cypher` + `compile_cypher_ast` + `validate single ReturnVar` + `extract ids` per command. Rejected because the validation logic would diverge over time.
