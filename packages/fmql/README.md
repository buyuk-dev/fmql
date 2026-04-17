# fmql — FrontMatter Utilities

A schemaless query engine and editor for directories of frontmatter (markdown + YAML) files.

[![PyPI](https://img.shields.io/pypi/v/fmql.svg)](https://pypi.org/project/fmql/)
[![CI](https://github.com/buyuk-dev/fmql/actions/workflows/ci.yml/badge.svg)](https://github.com/buyuk-dev/fmql/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/fmql.svg)](https://pypi.org/project/fmql/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Point it at any directory of markdown/YAML files. Query with filters, traversal, aggregation, and graph patterns. Edit properties across single files or entire result sets. No configuration, no schema, no setup.

## Installation

```bash
pip install fmql
```

From source:

```bash
git clone https://github.com/buyuk-dev/fmql.git
cd fmql
uv sync                    # or: pip install -e '.[dev]'
```

Requires Python 3.11+.

## Quickstart

CLI:

```bash
fmql query ./project 'status = "active" AND priority > 2'
fmql query ./project 'due_date < today' --format json
```

Python:

```python
from fmql import Workspace, Query

ws = Workspace("./project")
q = Query(ws).where(status="active", priority__gt=2)
for packet in q:
    print(packet.id)
```

## Features

- **Filter DSL** — SQL-ish string queries, case-insensitive keywords, typed comparisons, date literals.
- **Python kwargs API** — Django-style `field__op=value` with a full operator registry.
- **Edit operations** — `set`, `remove`, `rename`, `append`, `toggle` on single files or bulk result sets, with diff preview and confirmation.
- **Format-preserving YAML** — round-trip via `ruamel.yaml`; edits preserve comments, key order, and quoting of untouched fields.
- **Traversal** — `follow()` resolves reference fields (paths, UUIDs, slugs) forward or reverse, bounded or transitive.
- **Aggregation** — `group_by(...).aggregate(Count, Sum, Avg, Min, Max)`.
- **Describe** — workspace introspection: observed fields, types, distinct-value samples.
- **Cypher subset** — graph patterns for dependency chains, cycle detection, multi-hop traversal.
- **Pluggable search** — third-party backends register via Python entry points (`fmql.search_index`). Ships with a `grep` scan backend; third-party packages can add indexed backends (`fmql-fts`, `fmql-semantic`, …).

## CLI reference

| Command | Purpose | Example |
|---|---|---|
| `query` | Run a filter query against a workspace | `fmql query ./project 'status = "active"'` |
| `set` | Set frontmatter fields | `fmql set ./tasks/task-42.md status=done priority=1` |
| `remove` | Remove frontmatter fields | `fmql remove ./tasks/task-42.md temp_notes` |
| `rename` | Rename frontmatter fields | `fmql rename ./tasks/task-42.md assignee=assigned_to` |
| `append` | Append to list-valued fields | `fmql append ./tasks/task-42.md tags=urgent` |
| `toggle` | Toggle boolean fields | `fmql toggle ./tasks/task-42.md flagged` |
| `describe` | Workspace introspection | `fmql describe ./project` |
| `cypher` | Graph pattern query (Cypher subset) | `fmql cypher ./project 'MATCH (a)-[:blocked_by]->(b) RETURN a, b'` |
| `search` | Run a search backend against a workspace/index | `fmql search 'alice' --workspace ./project` |
| `index` | Build an index for an indexed backend | `fmql index ./project --backend semantic --out ./project/.fmql/semantic` |
| `list-backends` | Enumerate discovered search backends | `fmql list-backends` |

Common flags:

- `--format {paths,json,rows}` — output format (default: `paths` for `query`, `rows` for `cypher`).
- `--follow FIELD`, `--depth N|'*'`, `--direction {forward,reverse}` — traversal on `query`.
- `--resolver {path,uuid,slug}` — reference resolution strategy for traversal/Cypher.
- `--search QUERY`, `--index NAME`, `--index-location LOCATION` — pluggable search stage (backend default: `grep`).
- `--dry-run`, `--yes` — preview or auto-confirm for edit commands.
- `--workspace ROOT` — explicit workspace root when piping paths into edit commands.

Run `fmql <command> --help` for the full flag list on any command.

## Query syntax

### Filter DSL (`query` command and `qlang`)

Logical operators (case-insensitive):

```
AND   OR   NOT   ( ... )
```

Comparisons:

```
= != > >= < <=
CONTAINS      — substring match on strings/lists
MATCHES       — regex match on strings
IN [v1, v2]   — membership test
IS EMPTY      — field missing or empty
IS NOT EMPTY
IS NULL
```

Values: quoted strings (`"active"`), numbers (`42`, `3.14`), booleans (`true`, `false`), ISO dates (`2026-05-01`), and date sentinels:

```
today          now
yesterday      tomorrow
today-7d       now+1h        today+30d
```

Examples:

```bash
fmql query ./project 'status = "active" AND priority > 2'
fmql query ./project 'due_date < today AND status != "done"'
fmql query ./project 'tags CONTAINS "urgent" OR priority >= 3'
fmql query ./project 'status IN ["todo", "in_progress"]'
fmql query ./project 'NOT (assigned_to IS EMPTY)'
fmql query ./project 'title MATCHES "^\\[WIP\\]"'
```

Ordering with `ORDER BY`:

```
<query> ORDER BY field [ASC|DESC] [NULLS FIRST|NULLS LAST] [, field …]
```

- `ASC` (default) or `DESC` per key.
- `NULLS FIRST` / `NULLS LAST` is optional. Default follows SQL convention: `ASC` → nulls last, `DESC` → nulls first.
- Multiple keys are evaluated left-to-right.
- Values of different types are bucketed by type (booleans → numbers → dates → strings) so mixed-type fields don't raise.

```bash
fmql query ./project 'status = "open" ORDER BY priority DESC'
fmql query ./project '* ORDER BY due_date ASC NULLS LAST'
fmql query ./project 'type = "task" ORDER BY status, priority DESC'
```

`ORDER`, `BY`, `ASC`, `DESC`, `NULLS`, `FIRST`, `LAST` are reserved words (case-insensitive) in the query grammar.

### Python kwargs API

`field__op=value` — everything before the final `__` is the field, everything after is the operator. No `__` means `eq`.

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

### Cypher subset (`cypher` command)

```
MATCH (a)-[:field]->(b)                 # single hop
MATCH (a)-[:field*]->(b)                # transitive
MATCH (a)-[:field*1..5]->(b)            # bounded depth
MATCH (a)-[:blocked_by*]->(a)           # cycle detection
WHERE a.status = "active" AND b.priority > 2
RETURN a
RETURN a, b
RETURN a.title
RETURN count(a)
ORDER BY a.priority DESC [NULLS LAST]   # sort returned rows; keys may reference
                                        # any bound variable, not just RETURN items
```

Node labels parse but are ignored (schemaless). The `WHERE` clause uses the same operators as the filter DSL. `ORDER BY` supports multiple comma-separated keys (`var` or `var.field`) with per-key `ASC`/`DESC` and optional `NULLS FIRST` / `NULLS LAST`; default nulls policy matches SQL (`ASC` → nulls last).

```bash
fmql cypher ./project 'MATCH (a)-[:blocked_by*]->(a) RETURN a'
fmql cypher ./project 'MATCH (a)-[:belongs_to]->(e) WHERE e.type = "epic" RETURN a, e'
```

## Traversal & resolvers

`--follow FIELD` turns the result set into the starting seeds for a graph walk along that field. `--depth N` bounds the walk (use `*` for transitive). `--direction reverse` walks incoming edges instead of outgoing.

```bash
# Direct dependencies of one task
fmql query ./project 'uuid = "task-42"' --follow blocked_by --depth 1

# Full transitive dependency chain
fmql query ./project 'uuid = "task-42"' --follow blocked_by --depth '*'

# What does task-42 unblock? (reverse edge)
fmql query ./project 'uuid = "task-42"' --follow blocked_by --direction reverse
```

References in frontmatter fields are resolved by the selected resolver:

- `path` (default) — relative filesystem paths, e.g. `blocked_by: ../tasks/task-41.md`.
- `uuid` — matches a `uuid` frontmatter field on other packets.
- `slug` — matches a `slug` frontmatter field on other packets.

Pass `--resolver uuid` / `--resolver slug` to switch. Unresolvable references are dropped silently.

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
fmql describe ./project
fmql describe ./project --format json --top 10
```

## Editing & safety

Every edit is previewable, confirmable, and preserves comments, key order, quoting, and body bytes.

```bash
# Single file
fmql set ./project/tasks/task-42.md status=escalated priority=1
fmql remove ./project/tasks/task-42.md temp_notes
fmql rename ./project/tasks/task-42.md assignee=assigned_to
fmql append ./project/tasks/task-42.md tags=urgent
fmql toggle ./project/tasks/task-42.md flagged

# Bulk: pipe query results into edits
fmql query ./project 'status != "done" AND due_date < today' \
  | fmql set status=escalated --workspace ./project --yes

# Preview without writing
fmql set ./project/tasks/task-42.md status=done --dry-run
```

Python equivalent:

```python
from fmql import Workspace, Query

ws = Workspace("./project")
plan = Query(ws).where(status="active").set(status="reviewed")
print(plan.dry_run())       # unified diff
plan.apply(confirm=False)   # write
```

Value coercion from CLI strings: `true`/`false` → bool; integers and floats parsed as numbers; ISO dates (`2026-05-01`) parsed as dates; `null` → None. Quote to force string: `label='"123"'`.

**Safety model.** Bulk edits print a unified diff and prompt before writing. `--dry-run` shows the diff without writing; `--yes` skips the prompt. When stdin is piped (`fmql query ... | fmql set ...`), the prompt reopens `/dev/tty` — on systems without a tty (CI, containers), pass `--yes`.

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

After `pip install`, `fmql list-backends` will pick it up and `fmql search "text" --backend mine --workspace ./ws` will invoke it. For indexed backends, also implement `parse_location`, `default_location`, and `build`; `fmql.search.conformance` exposes reusable assertions you can drive from your own tests. See [docs/plugins_arch.md](docs/plugins_arch.md) for the full protocol.

## Development

```bash
uv sync --extra dev
make test    # run pytest
make lint    # ruff + black --check
make cov     # pytest with coverage (fails under 84%)
make format  # black
```

## Status

**v0.1.0** — first public release. All five design phases shipped: read path (filters, qlang, Python API), edit path (surgical YAML edits + bulk pipe), relationships & traversal (`follow` + resolvers), aggregation & describe, and the Cypher subset with pluggable search.

## Links

- [Design document](docs/design.md) — rationale, comparisons, target surface.
- [LICENSE](LICENSE) — MIT.
- [GitHub](https://github.com/buyuk-dev/fmql) — source, issues, releases.
