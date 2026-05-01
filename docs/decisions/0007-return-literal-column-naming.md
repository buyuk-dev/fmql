---
id: 0007
title: Cypher `RETURN` literals carry their source-form text as the column name
status: accepted
date: 2026-05-01
context_task: 0016
---

## Context

Task [0016](../tasks/0016-cypher-return-literals.md) extends Cypher `RETURN` so it accepts string and number literals (`RETURN a.title, "|", b.title`, `RETURN a.title, 1`). Every literal becomes one column on every output row. The task spec gestures at the column-name shape — "a sensible column name (e.g. the literal itself, or `col_N`)" — but leaves the choice open. Three options came up:

1. **Source form**: column name is the original token text (`"|"` for `"|"`, `1` for `1`, `-3.14` for `-3.14`).
2. **Unwrapped value**: column name is the parsed value cast to string (`|` for `"|"`, `1` for `1`).
3. **Positional `col_N`**: column name is `col_1`, `col_2`, ... regardless of literal value.

Source form requires storing one extra `text: str` field per `ReturnString` / `ReturnNumber` (the transformer has the original token in hand and would otherwise discard it). The unwrapped and positional schemes need no extra storage but also lose information.

The CLI's `rows`, `json`, and `yaml` formatters all consume `result.columns` directly as column / key names, so whichever shape we pick surfaces in every format.

## Decision

`ReturnString` and `ReturnNumber` carry both the parsed `value` and the original `text` (source form). `_column_name` returns `r.text` for both; `_project_item` returns `r.value`.

So:

- `RETURN "|"` → column name `"|"`, cell value `|` (string).
- `RETURN 1` → column name `1`, cell value `1` (int).
- `RETURN -3.14` → column name `-3.14`, cell value `-3.14` (float).
- `RETURN "x", "x"` → two columns named `"x"` (mirrors the existing `RETURN a.title, a.title` behavior, which already permits duplicate column names).

## Rationale

- **Strings stay visually distinct from field names.** The header `a.title | "|" | b.title` reads as "field, literal, field" at a glance. With the unwrapped option, `a.title | | | b.title` is harder to parse and the literal `|` collides visually with the row separator in `rows` output.
- **Round-trippable.** A user looking at the column name can see exactly what they wrote — `"|"` for a string, `1` for an integer, `-3.14` for a float. The `int` vs `float` distinction is preserved (`1.0` would be a float column named `1.0`, `1` an int column named `1`). Unwrapped strings would lose the type information; positional `col_N` would lose both type and value.
- **One-line implementation; no extra branching at format time.** `_column_name` already dispatches on the `Return*` type; adding a branch that returns `r.text` is two lines. Positional naming would require numbering at projection time and threading the index through `_column_name` (which currently takes a single `ReturnItem`, not a position).
- **Consistent with existing `RETURN a.title, a.title` permissiveness.** Duplicate column names are already legal in this language. Forcing literals to be uniquely named via `col_N` would be a one-off rule that doesn't apply to property accesses, and the formatters tolerate duplicates already.

## Consequences

- **`AST.ReturnString` / `ReturnNumber` carry redundant data.** Both `value` and `text` describe the same literal. The redundancy is intentional: `text` is the column name, `value` is the cell value, and recomputing one from the other (re-quoting a string, formatting a float) is fragile and loses the user's exact source form. Only the parser ever populates these; downstream code never reconstructs them.
- **Float formatting follows Python's `str(float)` if anyone hand-builds an AST.** The parser's `text` is whatever the user typed (`3.14`, `3.14e0`, `0.5`, `.5`), and `_column_name` returns it verbatim. A hand-built `ReturnNumber(value=3.14, text="3.14")` is the only normal shape; if a caller sets `text` to something else, the column name follows. Not worth defending against — internal API.
- **Duplicate literals → duplicate column names.** `RETURN "x", "x"` produces two columns named `"x"`. The existing `RETURN a.title, a.title` already exhibits this and the formatters cope; no new behavior to document beyond the README note.
- **`json` / `yaml` keys can be unusual.** `{"\"|\"": "|"}` is valid JSON; some downstream consumers may not love it. Users who want clean keys should rename the column at consume time. `AS alias` in `RETURN` is the long-term answer (see Out of scope).

## Alternatives considered

- **Unwrapped value as column name.** Rejected: collides visually with row separators in `rows` output; loses int-vs-float type info; ambiguous for strings that contain `|` or other formatter-significant characters.
- **Positional `col_N` naming.** Rejected: requires threading the column index into `_column_name`, breaks symmetry with the existing `ReturnVar` / `ReturnField` / `ReturnCount` cases which all derive their name from the item alone, and provides no information beyond the position. If we ever want positional naming, it should apply uniformly (including to property accesses), not just to literals.
- **Single `ReturnLiteral(value: Any)` dataclass.** Considered, given the precedent of `LiteralExpr` in `value_expr`. Rejected for symmetry: every other `Return*` variant is a distinct dataclass with a fixed shape, and two dataclasses make the executor's `isinstance` branches read more naturally than a single class with type-dispatch on `value`. The cost is one extra class and three extra lines.
- **`AS alias` for explicit column naming (`RETURN "|" AS sep`).** Out of scope. Cypher-spec `AS` is the right long-term solution but adds a grammar question (where does `AS` slot into other `Return*` forms?) and a CLI question (does the formatter prefer the alias or the source form when both are present?). Deferred.
