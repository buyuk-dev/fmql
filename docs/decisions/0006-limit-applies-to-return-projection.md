---
id: 0006
title: Cypher `LIMIT` applies to `RETURN` projection, not bindings; `SET`/`REMOVE` are unaffected
status: accepted
date: 2026-05-01
context_task: 0010
---

## Context

Task [0010](../tasks/0010-cypher-limit-clause.md) adds `LIMIT N` to fmql's Cypher subset. Two questions had to be answered before the executor could be wired up:

1. **Where in the pipeline does `LIMIT` cut?** The executor's stages are: pattern enumerate → `WHERE` filter → build `EditPlan` (for `SET`/`REMOVE`) → `ORDER BY` sort → `_project` (deduplicates rows) → `CypherResult`. `LIMIT` could plausibly slot in at three places: before `_project` on the `bindings` list, after `_project` on `result.rows`, or before `_build_edit_plan` so that writes only hit the truncated set.

2. **What happens when `LIMIT` is combined with `SET` / `REMOVE`?** Neo4j-flavored Cypher answers this with `WITH ... LIMIT N WITH ... SET ...`, but fmql's subset has no `WITH` (it's in `_UNSUPPORTED_KEYWORDS` in `compile.py`). So a query like `MATCH (t) SET t.tag = 1 RETURN t LIMIT 1` has no syntactic way to scope the write to the limited row set.

A fixture from `_project` makes this concrete: rows are deduplicated after projection (`executor.py:_dedupe_sort`). For a multi-binding pattern like `MATCH (a)-[:f]->(b) RETURN a` with 100 raw `(a, b)` bindings but 5 unique `a` values, slicing bindings to `[:3]` returns at most 3 unique `a`s — possibly fewer, depending on which 3 bindings happen to be first. Slicing post-projection always returns 3 unique rows when 3+ exist.

## Decision

`LIMIT N` slices `CypherResult.rows` **after** `_project()`. The `EditPlan` for `SET`/`REMOVE` is built from the full filtered binding set; `LIMIT` does not affect writes.

Concretely, `compile_cypher_ast` (`packages/fmql/src/fmql/cypher/executor.py`) calls a private `_apply_limit(result, ast.limit)` helper that wraps the slice plus a small invariant-fix: when `LIMIT 0` empties a scalar `count(...)` result, both `is_scalar` and `scalar` are cleared so the CLI's row formatter doesn't keep printing a count for an empty row stream. `LIMIT 0` short-circuits projection entirely via `_empty_result()` — there's no point walking bindings to throw them all away.

The `--limit N` CLI flag is folded into the AST before execution. In the direct-emit path, `cmd_query.py` does `replace(ast, limit=min(ast.limit, flag) if both else whichever)` and lets the executor be the single source of truth. In the `--follow`/`--search` path, the AST's in-query `LIMIT` still applies to the seeds inside `compile_cypher_ast`; the flag then caps the post-traverse packet stream via `itertools.islice`, which lets graph traversal short-circuit instead of materializing the full result.

## Rationale

- **Dedup makes pre-projection slicing unintuitive.** A user writing `RETURN a LIMIT 3` expects three rows back. Slicing bindings first can return fewer than 3 unique rows after dedup, which feels like a bug. Post-projection slicing matches the user-facing `RETURN` shape.
- **No `WITH`, so there is no clean way to scope writes by `LIMIT`.** Pre-`EditPlan` slicing would make `SET` behavior depend on the binding iteration order (which packets get the tag?). The order is deterministic — `_enumerate` walks `sorted(workspace.packets)` — but "the tag lands on whichever five packets sort first" is not a useful contract to commit to. Until `WITH` lands (out of subset, no driver), the cleanest answer is: writes apply to all matches, `LIMIT` only caps what `RETURN` shows.
- **One owner of the limit.** Folding the CLI flag into `ast.limit` before execution leaves a single enforcement point (`_apply_limit` inside the executor) and removes a cross-module dependency on a helper just for the scalar edge case.
- **Validator parity with `ORDER BY`.** Both clauses require a `RETURN` to act on a row stream. The validator rejects `LIMIT` without `RETURN` (`LIMIT requires a RETURN clause`) and `LIMIT` with a negative value (defensive — the grammar's `INT: /\d+/` already disallows negative literals, but a hand-built AST could smuggle one in). The CLI flag is bounded by Typer's `min=0`, so `--limit -1` errors before the function runs.

## Consequences

- **`MATCH (t) SET t.tag = 1 RETURN t LIMIT 1` tags every matching `t` and shows one in the result.** This is surprising at first read; documented in the README. Users who want "tag exactly N" should narrow the `WHERE` clause instead — that's what `WHERE` is for.
- **`LIMIT` and `--limit` collapse before execution, not after.** The CLI computes the merged cap and rewrites `ast.limit`; the executor sees a single value. This avoids re-running the limit logic on an already-limited result.
- **`LIMIT 0` on a scalar `count(...)` becomes a non-scalar empty result.** This is the only place `_apply_limit` rewrites more than the `rows` field, and it's necessary because `cmd_query.py`'s `rows` formatter emits `result.scalar` whenever `is_scalar` is True, regardless of whether `rows` is empty.
- **Pre-projection optimization is left on the table.** For very large result sets where `LIMIT` is small, slicing earlier in the pipeline would skip projection work for non-returned bindings. The optimization can be added later behind the same `_apply_limit` interface; we don't need to commit to it now. (`LIMIT 0` already short-circuits projection entirely via `_empty_result`.)

## Alternatives considered

- **Slice `bindings` before `_project`.** Cheaper, but breaks dedup intuition (returns fewer than `N` rows). Rejected.
- **Slice `bindings` before `_build_edit_plan` (so `SET` only hits the limited set).** Required to commit to a binding iteration order as a public contract; without `WITH` this would essentially smuggle `WITH n LIMIT N` semantics into a place users can't control. Rejected.
- **Reject `SET`/`REMOVE` with `LIMIT`.** Simplest, conservative. Considered, but `MATCH (t) SET t.x = 1 RETURN t LIMIT 5` is a perfectly reasonable shape (write to all, preview five) and rejecting it would force the user to run two separate queries. Rejected.
- **Bundle `SKIP N` into the same change.** Tempting (the natural pair) but `SKIP` has its own validation question (`SKIP` without `ORDER BY` is non-deterministic) and CLI question (do we want a `--skip N` flag?). Deferred to a follow-up to keep this PR small. The existing `(r"\bSKIP\b", "SKIP")` entry in `_UNSUPPORTED_KEYWORDS` and a `SKIP 5` line in `test_unsupported_constructs_raise` lock the contract.
