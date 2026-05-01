---
id: 0001
title: New `fmql query` is a merge of old query+cypher commands, not a strict rename
status: accepted
date: 2026-05-01
context_task: 0021
---

## Context

Task [0021](../tasks/0021-deprecate-qlang-rename-cypher-to-query.md) tells us to delete qlang and rename `fmql cypher` → `fmql query`. The task body says:

> The new `cli/cmd_query.py` is the renamed `cmd_cypher.py`.

But the same acceptance criteria also say:

> `--diagnose`, `--format {paths,json,rows}` (for `query`), … `--follow`/`--depth`/`--direction` all continue to work. No behavior change beyond the parser swap.

Those two statements are in tension. A literal rename of `cmd_cypher.py` doesn't carry `--follow`, `--depth`, `--direction`, `--include-origin`, `--search`, `--index`, `--index-location`, or `--format paths` — those flags only existed on the old qlang-backed `fmql query`. The cypher command had `--format rows|json` only.

## Decision

Treat the change as a **merge** of `cmd_cypher.py` and old `cmd_query.py`, not a strict rename:

- The Cypher parser (`fmql.cypher.parse_cypher` + `compile_cypher_ast`) is the basis.
- All of old qlang `query_cmd`'s traversal/search flags (`--follow`, `--depth`, `--direction`, `--include-origin`, `--search`, `--index`, `--index-location`) are preserved.
- The `--format` enum gains `paths` alongside cypher's existing `rows` and `json`.
- The default format is **inferred** from the AST: `paths` when `RETURN` is a single packet variable (e.g. `RETURN t`), `rows` otherwise. This matches the README's documented defaults (`paths` for `query`, `rows` for `cypher`) without the user having to pass `--format` for the common cases.
- `--follow` / `--search` engage a "Query path": run the Cypher query, take the resulting packet ids, then chain `Query.follow()` / `Query.search()`. Requires `RETURN` to be a single packet variable; rejects `SET`/`REMOVE` (which belong on the Cypher path or in `fmql update`).
- `--format paths` requires `RETURN` to be a single packet variable in all paths; explicit error otherwise.

## Consequences

- The `query_cmd` function is longer than a verbatim rename of `cypher_cmd` (~150 lines vs ~50). This is the cost of preserving the broader CLI surface.
- Edge cases need explicit handling: `--format paths` with a multi-var or count `RETURN` errors instead of silently falling back; `--follow` with a query that has no `RETURN` is rejected.
- The README and skill docs become more useful as a single reference for the new `query` command — readers no longer need to mentally cross-reference two commands.

## Alternatives considered

- **Strict rename** (drop the qlang flags). Cleaner code, but violates the task's "all continue to work" criterion and forces users with shell scripts that do `fmql query 'X' --follow F` to rewrite into a Cypher MATCH followed by a separate command — significantly more surgery for the user despite the task framing this as "no behavior change beyond the parser swap."
- **Two commands.** Keep `fmql cypher` AND `fmql query` (the latter as the qlang-flagged superset). Rejected because it preserves the two-language perception this task is trying to dismantle.

The merge was approved as the recommended option in the plan reviewed at `~/.claude/plans/get-started-on-task-purring-trinket.md`.
