---
id: 0021
title: Deprecate qlang; rename `fmql cypher` to `fmql query`; build sugar inside Cypher
status: todo
priority: 1
created: 2026-04-30
updated: 2026-04-30
tags: [qlang, cypher, cli, language, breaking-change]
depends_on: []
phase: cypher
---

## Goal

Make Cypher the single query language. Delete qlang as a language entirely. The `fmql query` *command* survives — it just becomes the new name for what is currently `fmql cypher`. No sugar layer in this task: stick strictly to the existing Cypher subset. Ergonomic extensions can be considered later if a strong reason emerges, but they are explicitly out of scope here.

### Why

The original split (qlang as the foundation, Cypher as a 5% escape hatch — see `docs/design.md:25`) is no longer accurate. Bulk edits, virtual properties, list comprehensions, function calls, `+=`, and unary `NOT` have all accreted onto Cypher; qlang has stayed at "filter + ORDER BY" and is now a strict subset of Cypher's `WHERE` clause. We're maintaining two parsers, two grammars, and two compile paths to express ideas one of them can already express. Task [0020](0020-qlang-not-in-null-literal.md) makes this concrete: the same three small features have to be added to both grammar files, and both files have to be kept in sync forever.

There are no external users beyond the maintainer, so this is the right moment to consolidate before the cost compounds.

### Non-goals

- Changing the **Python API**. `Query(ws).where(status="active", priority__gt=2)` builds `Predicate` nodes directly without going through qlang's grammar; it stays as-is. The kwargs operator registry (`__eq`, `__gt`, `__contains`, `__not_in`, …) is unaffected.
- Shipping a deprecation period or back-compat shim for qlang. Single-user project — just delete it.

## Acceptance criteria

### Language / parser

- [ ] Delete `packages/fmql/src/fmql/qlang/` entirely (`grammar.lark`, `compile.py`, `__init__.py`).
- [ ] Remove every `from fmql.qlang import …` site. The canonical query parser is the Cypher one (`packages/fmql/src/fmql/cypher/`).
- [ ] No new "qlang" surface anywhere in the codebase or docs (no fallback, no "did you mean", no auto-translate).

### CLI

- [ ] Delete the current qlang-backed `fmql query` (`cli/cmd_query.py`).
- [ ] Rename `fmql cypher` → `fmql query`. The new `cli/cmd_query.py` is the renamed `cmd_cypher.py`. Help text, command registration in `cli/main.py`, and any docstrings update accordingly.
- [ ] `fmql update` keeps its name and continues to require `SET`/`REMOVE` and reject `RETURN`/`ORDER BY`. Its parser stays the (now sole) Cypher parser.
- [ ] `fmql subgraph` currently parses seeds via `compile_query` (qlang) — see `cli/cmd_subgraph.py:13`. Re-route it through the Cypher parser. The seed argument becomes a full Cypher query (`'MATCH (t) WHERE t.status = "active" RETURN t'`). Verbose, but consistent with `fmql query` and avoids a second parsing mode.
- [ ] `--diagnose`, `--format {paths,json,rows}` (for `query`), `--format {raw,cytoscape,mermaid?}` (for `subgraph`), `--dry-run`, `--yes`, `--resolver`, `--follow`/`--depth`/`--direction` all continue to work. No behavior change beyond the parser swap.

### Docs

- [ ] `README.md`: drop the entire "Filter DSL (qlang)" section. The "Query syntax" section becomes Cypher-only. The `query` command row in the CLI reference table updates to show a Cypher example. The traversal section updates seed examples.
- [ ] `docs/design.md`: update the `Graph patterns via Cypher-compatible subset` bullet to reflect that Cypher is now *the* query language, not an escape hatch.
- [ ] `CLAUDE.md`: no changes (it doesn't pin qlang).
- [ ] Close [0006](0006-sql-not-qlang-cheatsheet.md) — the "SQL vs qlang" framing is moot once qlang is gone. If the cheatsheet still has value as "SQL vs Cypher" for users coming from databases, repurpose it; otherwise mark it `done` with a note that 0021 supersedes it.
- [ ] Re-scope [0020](0020-qlang-not-in-null-literal.md) to Cypher only (drops half the work). Update its frontmatter and acceptance criteria, or close + clone if cleaner.

### Tests

- [ ] Delete qlang-specific test modules.
- [ ] Tests that exercised the CLI via qlang strings get rewritten against the Cypher parser. Coverage for the operators that lived only in qlang tests (`IN`, `IS NULL`, `IS EMPTY`, ordering) must survive on the Cypher side — audit before deleting.
- [ ] Add tests for the new `fmql query` command (renamed from `fmql cypher`) end-to-end.
- [ ] `make format && make lint && make test` clean.

## Notes

### Migration cost (single user)

- Any of the maintainer's local scripts that call `fmql query 'status = "active"'` need to be rewritten to the full Cypher form: `fmql query 'MATCH (t) WHERE t.status = "active" RETURN t'`. Same for `fmql subgraph` seed arguments. Worth grepping personal dotfiles / project Makefiles before merging.
- The Python API does not change. `Query(ws).where(...)` is unaffected.

### On future sugar

Sugar (filter-only shorthand, implicit primary variable, etc.) is **explicitly out of scope** for this task. Bias toward staying with strict Cypher and only revisiting if real friction shows up in daily use. If sugar is ever added, it must extend the Cypher grammar in place — never a second parser.

### Accepted trade-off

`fmql query` and `fmql subgraph` get more verbose for the common filter case (`'MATCH (t) WHERE t.status = "active" RETURN t'` vs the old `'status = "active"'`). That is the cost of consolidating to one language and is accepted.
