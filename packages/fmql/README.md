# FMQL - Schemaless Markdown + YAML FrontMatter Query Language

A schemaless query engine and editor for directories of frontmatter (markdown + YAML) files.

[![PyPI](https://img.shields.io/pypi/v/fmql.svg)](https://pypi.org/project/fmql/)
[![CI](https://github.com/buyuk-dev/fmql/actions/workflows/ci.yml/badge.svg)](https://github.com/buyuk-dev/fmql/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/fmql.svg)](https://pypi.org/project/fmql/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Point it at any directory of markdown/YAML files. Query with filters, traversal, aggregation, and graph patterns. Edit properties across single files or entire result sets. No configuration, no schema, no setup.

![fmql in motion: cat a frontmatter task file, then run a Cypher-shaped `fmql update` to bulk-tag tech-debt candidates with a diff preview.](https://raw.githubusercontent.com/buyuk-dev/fmql/main/packages/fmql/docs/hero.gif)

## Installation

```bash
pip install fmql
```

### System-wide CLI via pipx

If you want `fmql` on your `PATH` across projects without managing a per-repo venv, use [`pipx`](https://pipx.pypa.io):

```bash
pipx install fmql
```

pipx installs `fmql` into an isolated environment and exposes the CLI on your shell. Search backends and other plugins register via Python entry points, so they must live in fmql's pipx env. Add them with `pipx inject` (not `pipx install` — plugin libraries have no CLI of their own):

```bash
pipx inject fmql fmql-semantic    # example: add the semantic search backend
```

### From source

```bash
git clone https://github.com/buyuk-dev/fmql.git
cd fmql
uv sync                    # or: pip install -e '.[dev]'
```

Requires Python 3.11+.

## Quickstart

CLI:

```bash
fmql query 'MATCH (t) WHERE t.type = "task" AND t.status != "done" RETURN t' -w ./notes
fmql query 'MATCH (t) WHERE t.due_date < today+0d RETURN t' -w ./project --format json
```

Every command takes `--workspace/-w` for the workspace root; if omitted, fmql uses the current working directory.

Python:

```python
from fmql import Workspace, Query

ws = Workspace("./notes")
q = Query(ws).where(type="task", status__ne="done")
for packet in q:
    print(packet.id)
```

## Features

- **Cypher query language** — `MATCH ... [WHERE ...] [SET|REMOVE ...] [RETURN ...] [ORDER BY ...]`, with virtual properties (`t.path`, `t.filename`, `t.slug`), list comprehensions, `+=`, unary `NOT`, and built-in functions (`resolve`, `field`, `slug`, `id`, `uuid`, `path`).
- **Python kwargs API** — Django-style `field__op=value` with a full operator registry. Builds `Predicate` nodes directly; doesn't go through the Cypher grammar.
- **Bulk edits via Cypher** — `fmql update 'MATCH … [WHERE …] [SET …] [REMOVE …]'`. Every edit previews a unified diff and prompts before writing.
- **Format-preserving YAML** — round-trip via `ruamel.yaml`; edits preserve comments, key order, and quoting of untouched fields.
- **Traversal** — `follow()` resolves reference fields (paths, UUIDs, slugs) forward or reverse, bounded or transitive.
- **Aggregation** — `group_by(...).aggregate(Count, Sum, Avg, Min, Max)`.
- **Describe** — workspace introspection: observed fields, types, distinct-value samples.
- **Pluggable search** — third-party backends register via Python entry points (`fmql.search_index`). Ships with a `grep` scan backend; third-party packages can add indexed backends (`fmql-fts`, `fmql-semantic`, …).

## Plugins

Official plugins live alongside core in the [fmql monorepo](https://github.com/buyuk-dev/fmql/tree/main/packages). Third-party plugins are discovered via the `fmql.search_index` entry-point group — see [Writing a search backend](#writing-a-search-backend).

| Package | PyPI | Description |
|---|---|---|
| [`fmql-semantic`](https://github.com/buyuk-dev/fmql/tree/main/packages/fmql-semantic) | [pypi.org/project/fmql-semantic](https://pypi.org/project/fmql-semantic/) | Hybrid semantic search backend: dense embeddings (LiteLLM + `sqlite-vec`), sparse BM25 (SQLite FTS5), RRF fusion, optional reranking. |

## CLI reference

| Command | Purpose | Example |
|---|---|---|
| `query` | Run a Cypher query against a workspace | `fmql query 'MATCH (t) WHERE t.status = "active" RETURN t' -w ./project` |
| `describe` | Workspace introspection | `fmql describe -w ./project` |
| `update` | Pattern-match and edit packets (`MATCH ... [SET\|REMOVE]`) | `fmql update 'MATCH (t) SET t.depends_on = slug(t.depends_on)' -w ./project` |
| `subgraph` | Reachability closure around seed packets as `{nodes, edges}` JSON | `fmql subgraph 'MATCH (t) WHERE t.uuid = "task-1" RETURN t' -w ./project --follow blocked_by` |
| `search` | Run a search backend against a workspace/index | `fmql search 'alice' -w ./project` |
| `index` | Build an index for an indexed backend | `fmql index --backend semantic -w ./project --out ./project/.fmql/semantic` |
| `list-backends` | Enumerate discovered search backends | `fmql list-backends` |

Every command takes `--workspace/-w ROOT` (default: cwd). There are no longer any `set / append / remove / rename / toggle` commands — bulk edits go through `fmql update` with a Cypher pattern (see [Editing via update](#editing-via-update)).

Common flags:

- `--format {paths,json,rows}` — output format on `query`. Default infers from the query: `paths` when `RETURN` is a single packet variable (e.g. `RETURN t`), otherwise `rows`. `paths` requires a single packet variable in `RETURN`.
- `--follow FIELD`, `--depth N|'*'`, `--direction {forward,reverse}`, `--include-origin` — traversal on `query` and `subgraph` (chained after the `MATCH` result; requires `RETURN` to be a single packet variable).
- `--resolver {path,uuid,slug,id}` — default reference resolver for traversal and relationship hops.
- `--format {raw,cytoscape}` — output shape for `subgraph` (default `raw`).
- `--search QUERY`, `--index NAME`, `--index-location LOCATION` — pluggable search stage on `query` (backend default: `grep`).
- `--diagnose` — on `query` and `subgraph`: emit stderr `warning:` lines for reference values the active resolver could not match. Off by default; costs one extra workspace scan per relationship field. Enable globally for a workspace via `fmql.diagnose: true` in `WORKSPACE.md`.
- `--dry-run`, `--yes` — preview or auto-confirm on `query` / `update` when the query has a `SET` or `REMOVE`.

Run `fmql <command> --help` for the full flag list on any command.

## Query syntax

`fmql query` and `fmql update` both speak the same Cypher subset.

```
MATCH (a)-[:field]->(b)                 # single hop
MATCH (a)-[:field*]->(b)                # transitive
MATCH (a)-[:field*1..5]->(b)            # bounded depth
MATCH (a)-[:blocked_by*]->(a)           # cycle detection
WHERE a.status = "active" AND b.priority > 2
SET a.status = "archived", a.label = b.title
REMOVE a.draft_notes
RETURN a
RETURN a, b
RETURN a.title
RETURN count(a)
ORDER BY a.priority DESC [NULLS LAST]   # sort returned rows; keys may reference
                                        # any bound variable, not just RETURN items
```

Node labels parse but are ignored (schemaless). `ORDER BY` supports multiple comma-separated keys (`var` or `var.field`) with per-key `ASC`/`DESC` and optional `NULLS FIRST` / `NULLS LAST`; default nulls policy matches SQL (`ASC` → nulls last).

### `WHERE` operators

Logical: `AND` / `OR` / `NOT` / `( ... )` (case-insensitive).

```
= != <> > >= < <=
CONTAINS         — substring match on strings/lists
MATCHES          — regex match on strings
IN [v1, v2]      — membership test
NOT IN [v1, v2]  — negated membership test
IS EMPTY         — field missing or empty
IS NOT EMPTY
IS NULL
IS NOT NULL
```

Values: quoted strings (`"active"`), numbers (`42`, `3.14`), booleans (`true`, `false`), `null`, ISO dates (`2026-05-01`), and date sentinels with required offset (`today+0d`, `today-7d`, `now+1h`, `today+30d`).

`null` matches packets where the field is absent **or** explicitly set to YAML `null`/`~` — the same equivalence class as `IS NULL`. `t.f != null` and `t.f IS NOT NULL` are the inverse: they match only packets where the field is present and non-null. Inside `IN [...]` lists, `null` works the same way: `t.f IN [null, "x"]` matches packets where the field is absent, explicitly null, or equal to `"x"`.

```bash
fmql query 'MATCH (t) WHERE t.status = "active" AND t.priority > 2 RETURN t' -w ./project
fmql query 'MATCH (t) WHERE t.due_date < today+0d AND t.status != "done" RETURN t' -w ./project
fmql query 'MATCH (t) WHERE t.tags CONTAINS "urgent" OR t.priority >= 3 RETURN t' -w ./project
fmql query 'MATCH (t) WHERE t.status IN ["todo", "in_progress"] RETURN t' -w ./project
fmql query 'MATCH (t) WHERE t.assigned_to NOT IN [null, "alice"] RETURN t' -w ./project
fmql query 'MATCH (t) WHERE t.assigned_to IS NOT NULL RETURN t' -w ./project
fmql query 'MATCH (t) WHERE NOT (t.assigned_to IS EMPTY) RETURN t' -w ./project
fmql query 'MATCH (t) WHERE t.title MATCHES "^\\[WIP\\]" RETURN t' -w ./project
fmql query 'MATCH (a)-[:blocked_by*]->(a) RETURN a' -w ./project
fmql query 'MATCH (a)-[:belongs_to]->(e) WHERE e.type = "epic" RETURN a, e' -w ./project
```

### Python kwargs API

The Python API does not go through the Cypher grammar — it builds `Predicate` nodes directly from `field__op=value` kwargs.

| Operator | Matches when field value… |
|---|---|
| `eq` (default) | equals the expected value (booleans stay distinct from ints) |
| `ne` / `not` | is present and does not equal |
| `gt`, `gte`, `lt`, `lte` | is a comparable type and ordered accordingly |
| `in` | is in the given list/tuple/set |
| `not_in` | is present and not in the list |
| `contains` | is a string containing the substring, or a list containing the value |
| `icontains` | same as `contains`, case-insensitive for strings |
| `startswith`, `endswith` | string prefix / suffix match |
| `matches` | matches the given regex |
| `exists` | field is present (any value, truthy flag) |
| `not_empty` | field is present and not empty / zero-length |
| `is_null` | field value is explicitly `null` |
| `type` | field value's type name equals the expected (`int`, `str`, `list`, `date`, …) |

Type-honest: non-comparable values are silently excluded, not coerced. `priority > 2` matches packets where `priority` is an int > 2; packets where it's a string or missing are just not in the result.

```python
from fmql import Query, Workspace

ws = Workspace("./project")
Query(ws).where(status="active", priority__gt=2)
Query(ws).where(tags__contains="urgent")
Query(ws).where(status__in=["todo", "in_progress"])
Query(ws).where(assigned_to__not_empty=True)
Query(ws).where(title__matches=r"^\[WIP\]")
Query(ws).where(status="open").order_by("priority", desc=True)
Query(ws).order_by("status").order_by("priority", desc=True, nulls="last")
```

### Cypher details

#### Virtual properties

Every packet exposes three virtual properties derived from its workspace-relative path. They behave exactly like frontmatter fields in `WHERE`/`SET`/`RETURN`:

| Field | Value |
|---|---|
| `t.path` | workspace-relative POSIX path (e.g. `tasks/task-42.md`) |
| `t.filename` | basename including extension (e.g. `task-42.md`) |
| `t.slug` | filename without extension (e.g. `task-42`) |

```bash
# Filter by file identity in MATCH/WHERE.
fmql query 'MATCH (t) WHERE t.path = "tasks/task-42.md" RETURN t' -w ./project

# Use a virtual field on the right-hand side of SET.
fmql update 'MATCH (t) WHERE t.title IS EMPTY SET t.title = t.slug' -w ./project
```

Frontmatter keys take precedence — if a packet already has its own `path` field, that value wins.

For an identity that *cannot* be shadowed by frontmatter — useful when pinning a query to a specific document without adding bookkeeping fields — use the underscore-prefixed pseudo-fields:

| Field | Value |
|---|---|
| `t._path` | workspace-relative POSIX path; not shadowable by frontmatter |
| `t._id`   | stable packet identifier (currently aliased to `_path`)       |

```bash
fmql query 'MATCH (a)-[:links_to]->(b) WHERE a._path = "notes/inbox/today.md" RETURN b.title' -w ./notes
```

Pseudo-fields are read-only: `SET t._path = ...` and `REMOVE t._id` are rejected at validation time.

#### `SET` and `REMOVE` (bulk migrations)

`SET` rewrites frontmatter on matched packets, `REMOVE` deletes fields. Right-hand sides accept literals, qualified field references (`var.field`), function calls, list literals, list comprehensions, and unary `NOT`. A query may have `SET` only, `REMOVE` only, both, `RETURN` only, or any combination — when `SET`/`REMOVE` is paired with `RETURN`, the writes apply first, then `RETURN` projects against the post-write state (Neo4j ordering). Multiple bindings writing the same `(packet, field)` with different values is rejected as a conflict; `SET t.f = …` and `REMOVE t.f` on the same field is also rejected.

`SET` operators:

| Operator | Behavior |
|---|---|
| `SET t.field = expr` | Replace the field with `expr`. |
| `SET t.field += expr` | Append `expr` to the existing list (or initialize to `[expr]`). |
| `SET t.field = NOT t.field` | Boolean toggle (broadcasts element-wise over lists). |
| `SET t.field = [x IN t.list WHERE pred (\| projection)?]` | Neo4j-style list comprehension. Use it to filter or project list-valued fields. |

Built-in functions:

| Function | Purpose |
|---|---|
| `resolve(v)` | Resolve `v` via the workspace's default resolver (or per-field binding) → packet id. |
| `resolve(v, "<name>")` | Resolve via a specific resolver: `path`, `uuid`, `slug`, or `id`. |
| `field(pid, "<name>")` | Read frontmatter field `name` from packet `pid` (returns `None` if `pid` is `None` or the field is missing). |
| `slug(v)` / `id(v)` / `uuid(v)` | Shortcut for `field(resolve(v, "<name>"), "<name>")`. |
| `path(v)` | Shortcut for `resolve(v, "path")` — returns the relative packet id. |

When the first positional argument evaluates to a list, the call is broadcast element-wise (subsequent args stay scalar); unresolvable elements become `None` and are preserved in position.

Both `fmql query` (when `SET`/`REMOVE` is present) and `fmql update` accept `--dry-run` (preview the diff without writing) and `--yes` (skip the confirm prompt).

### Editing via update

`fmql update` is the one-stop shop for bulk edits. It requires a `SET` and/or `REMOVE` clause and rejects `RETURN`/`ORDER BY`; use `fmql query` when you want to write *and* project in the same query.

```bash
# Migrate id-shaped references to slugs.
fmql update 'MATCH (t) SET t.depends_on = slug(t.depends_on)' -w ./project

# Compose: id → packet → slug field.
fmql update 'MATCH (t) SET t.depends_on = field(resolve(t.depends_on, "id"), "slug")' -w ./project

# Append to a list-valued field.
fmql update 'MATCH (t) WHERE t.status = "active" SET t.tags += "urgent"' -w ./project

# Remove a field across many packets.
fmql update 'MATCH (t) WHERE t.archived = true REMOVE t.draft_notes' -w ./project

# Toggle a boolean.
fmql update 'MATCH (t) WHERE t.flagged = false SET t.flagged = NOT t.flagged' -w ./project

# Drop a single value from a list.
fmql update 'MATCH (t) SET t.tags = [x IN t.tags WHERE x <> "deprecated"]' -w ./project

# Rename a field (SET + REMOVE; the new key lands at the end of the YAML map).
fmql update 'MATCH (t) WHERE t.assignee IS NOT EMPTY
             SET t.assigned_to = t.assignee REMOVE t.assignee' -w ./project

# Filter by virtual properties in WHERE.
fmql update 'MATCH (t) WHERE t.path = "tasks/task-42.md" SET t.status = "done"' -w ./project

# SET + RETURN: write then project the updated rows (use `fmql query`).
fmql query 'MATCH (t) WHERE t.status = "old" SET t.status = "archived" RETURN t' -w ./project --yes
```

## Traversal & resolvers

`--follow FIELD` turns the result set into the starting seeds for a graph walk along that field. `--depth N` bounds the walk (use `*` for transitive). `--direction reverse` walks incoming edges instead of outgoing.

```bash
# Direct dependencies of one task
fmql query 'MATCH (t) WHERE t.uuid = "task-42" RETURN t' -w ./project --follow blocked_by --depth 1

# Full transitive dependency chain
fmql query 'MATCH (t) WHERE t.uuid = "task-42" RETURN t' -w ./project --follow blocked_by --depth '*'

# What does task-42 unblock? (reverse edge)
fmql query 'MATCH (t) WHERE t.uuid = "task-42" RETURN t' -w ./project --follow blocked_by --direction reverse
```

`--follow` chains a graph walk after the Cypher result, so `RETURN` must be a single packet variable. Express native multi-hop traversal in `MATCH` itself when possible.

References in frontmatter fields are resolved by the selected resolver:

- `path` (default) — relative filesystem paths, e.g. `blocked_by: ../tasks/task-41.md`.
- `uuid` — matches a `uuid` frontmatter field on other packets (string values only).
- `slug` — matches a `slug` frontmatter field on other packets, falling back to file stem.
- `id` — matches an `id` frontmatter field; accepts both int and string values, so `depends_on: [1, 8, 17]` resolves out of the box on roadmap/ADR/ticket corpora where YAML coerces unquoted IDs to ints.

Pass `--resolver uuid` / `--resolver slug` / `--resolver id` to switch the default for one invocation.

Resolver bindings can fall through silently — e.g. binding `uuid` to a field whose values are integers will produce empty edges with no error. Pass `--diagnose` (off by default for performance) to scan the workspace and emit a `warning:` line to stderr for each field with unresolved values, including sample values and a copy-pasteable `WORKSPACE.md` snippet that fixes the binding. Set `fmql.diagnose: true` in `WORKSPACE.md` to enable diagnostics by default for a given workspace.

> Quote IDs with leading zeros (`id: "017"`) — YAML 1.2 parses unquoted `017` as the integer 17, and the `id` resolver does not bridge that gap. Quoted strings only match quoted strings; unquoted ints only match unquoted ints (with a string fallback for cross-coercion).

### Workspace configuration (`WORKSPACE.md`)

Drop a `WORKSPACE.md` file at the workspace root with an `fmql:` block in its frontmatter to bind resolvers per field — eliminating the need for `--resolver` on every command:

```markdown
---
fmql:
  default_resolver: path
  resolvers:
    depends_on: id
    supersedes: slug
    blocked_by: uuid
  diagnose: true       # optional; enables --diagnose by default for this workspace
---

# My Workspace

Free-form notes here. The body is ignored by fmql; only the `fmql:` block in frontmatter is configuration.
```

Precedence: `--resolver FLAG` (per-invocation) > Python `Workspace(resolvers=…, default_resolver=…)` kwargs > `WORKSPACE.md` > built-in `path` default. An unknown resolver name in `WORKSPACE.md` raises an error at workspace load time. `fmql.diagnose` must be a boolean — non-bool values raise an error.

For the whole reachability closure as structured graph data (not a row set), use `fmql subgraph`. It emits `{nodes, edges}` JSON by default (`--format raw`), or a Cytoscape.js-ready shape with `--format cytoscape`:

```bash
# Default: {nodes, edges} for jq / custom pipelines
fmql subgraph 'MATCH (t) WHERE t.status = "active" RETURN t' -w ./project --follow blocked_by

# Cytoscape.js: {elements: {nodes, edges}} with data wrappers + synthesized edge IDs,
# ready for cy.add(…) or cytoscape({elements: …})
fmql subgraph 'MATCH (t) WHERE t.status = "active" RETURN t' -w ./project --follow blocked_by --format cytoscape > graph.json
```

## Aggregation & describe

Group-and-aggregate returns one row per group:

```python
from fmql import Query, Workspace
from fmql import Count, Sum, Avg

ws = Workspace("./project")
(
    Query(ws)
    .where(type="task", in_sprint="sprint-3")
    .group_by("status")
    .aggregate(count=Count(), points=Sum("points"))
)
```

`describe` summarises a workspace — fields observed, types seen per field, and a sample of distinct values:

```bash
fmql describe -w ./project
fmql describe -w ./project --format json --top 10
```

## Editing & safety

All edits go through `fmql update` (or `fmql query` if you also need `RETURN`). Every edit is previewable, confirmable, and preserves comments, key order, quoting, and body bytes. See [Editing via update](#editing-via-update) for the operator reference and recipe library.

```bash
# Bulk migration with diff + confirm prompt
fmql update 'MATCH (t) WHERE t.status != "done" AND t.due_date < today() SET t.status = "escalated"' -w ./project

# Preview without writing
fmql update 'MATCH (t) SET t.status = "done"' -w ./project --dry-run

# Skip the confirm prompt
fmql update 'MATCH (t) WHERE t.flagged = false SET t.flagged = true' -w ./project --yes
```

Python equivalent:

```python
from fmql import Workspace, Query

ws = Workspace("./project")
plan = Query(ws).where(status="active").set(status="reviewed")
print(plan.dry_run())       # unified diff
plan.apply(confirm=False)   # write
```

**Safety model.** Bulk edits print a unified diff and prompt before writing. `--dry-run` shows the diff without writing; `--yes` skips the prompt. The prompt reopens `/dev/tty` so it survives output redirection — on systems without a tty (CI, containers), pass `--yes`.

**Formatting.** fmql re-emits edited YAML with 2-space mapping indent and 4-space sequence offset (ruamel defaults with explicit offset). Files that don't conform can still be parsed; only edited files are re-emitted, and untouched keys round-trip byte-for-byte.

## Writing a search backend

Third-party packages can register search backends via the `fmql.search_index` entry-point group. Core makes no assumptions about what an index is or where it lives — the backend decides.

Pick one of two protocols:

- `ScanSearch` — scans the workspace at query time. No build step.
- `IndexedSearch` — builds a persistent index that `fmql index` rebuilds and `fmql search --index LOCATION` queries.

Minimal scan backend:

```python
from fmql.search import BackendInfo, ScanSearch, SearchHit

class MyBackend:
    name = "mine"

    def query(self, text, workspace, *, k=10, options=None):
        hits = []
        for pid, packet in workspace.packets.items():
            if text.lower() in packet.body.lower():
                hits.append(SearchHit(packet_id=pid, score=1.0))
                if len(hits) >= k:
                    break
        return hits

    def info(self):
        return BackendInfo(name=self.name, version="0.1.0", kind="scan")
```

Register in your `pyproject.toml`:

```toml
[project.entry-points."fmql.search_index"]
mine = "my_package:MyBackend"
```

After `pip install`, `fmql list-backends` will pick it up and `fmql search "text" --backend mine --workspace ./ws` will invoke it. For indexed backends, also implement `parse_location`, `default_location`, and `build`; `fmql.search.conformance` exposes reusable assertions you can drive from your own tests.

## Development

```bash
uv sync --extra dev
make test    # run pytest
make lint    # ruff + black --check
make cov     # pytest with coverage (fails under 84%)
make format  # black
```