# fm — FrontMatter Utilities

A schemaless query engine and editor for directories of frontmatter (markdown + YAML) files.

[![PyPI](https://img.shields.io/pypi/v/fm.svg)](https://pypi.org/project/fm/)
[![CI](https://github.com/luon-ai/fm/actions/workflows/ci.yml/badge.svg)](https://github.com/luon-ai/fm/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/fm.svg)](https://pypi.org/project/fm/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Point it at any directory of markdown/YAML files. Query with filters, traversal, aggregation, and graph patterns. Edit properties across single files or entire result sets. No configuration, no schema, no setup.

## Installation

```bash
pip install fm
```

From source:

```bash
git clone https://github.com/luon-ai/fm.git
cd fm
uv sync                    # or: pip install -e '.[dev]'
```

Requires Python 3.11+.

## Quickstart

CLI:

```bash
fm query ./project 'status = "active" AND priority > 2'
fm query ./project 'due_date < today' --format json
```

Python:

```python
from fm import Workspace, Query

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
- **Pluggable search** — minimal `SearchIndex` protocol; ships with a text-scan fallback.

## CLI reference

| Command | Purpose | Example |
|---|---|---|
| `query` | Run a filter query against a workspace | `fm query ./project 'status = "active"'` |
| `set` | Set frontmatter fields | `fm set ./tasks/task-42.md status=done priority=1` |
| `remove` | Remove frontmatter fields | `fm remove ./tasks/task-42.md temp_notes` |
| `rename` | Rename frontmatter fields | `fm rename ./tasks/task-42.md assignee=assigned_to` |
| `append` | Append to list-valued fields | `fm append ./tasks/task-42.md tags=urgent` |
| `toggle` | Toggle boolean fields | `fm toggle ./tasks/task-42.md flagged` |
| `describe` | Workspace introspection | `fm describe ./project` |
| `cypher` | Graph pattern query (Cypher subset) | `fm cypher ./project 'MATCH (a)-[:blocked_by]->(b) RETURN a, b'` |

Common flags:

- `--format {paths,json,rows}` — output format (default: `paths` for `query`, `rows` for `cypher`).
- `--follow FIELD`, `--depth N|'*'`, `--direction {forward,reverse}` — traversal on `query`.
- `--resolver {path,uuid,slug}` — reference resolution strategy for traversal/Cypher.
- `--search QUERY`, `--index NAME` — pluggable search stage.
- `--dry-run`, `--yes` — preview or auto-confirm for edit commands.
- `--workspace ROOT` — explicit workspace root when piping paths into edit commands.

Run `fm <command> --help` for the full flag list on any command.

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
fm query ./project 'status = "active" AND priority > 2'
fm query ./project 'due_date < today AND status != "done"'
fm query ./project 'tags CONTAINS "urgent" OR priority >= 3'
fm query ./project 'status IN ["todo", "in_progress"]'
fm query ./project 'NOT (assigned_to IS EMPTY)'
fm query ./project 'title MATCHES "^\\[WIP\\]"'
```

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
from fm import Query, Workspace

ws = Workspace("./project")
Query(ws).where(status="active", priority__gt=2)
Query(ws).where(tags__contains="urgent")
Query(ws).where(status__in=["todo", "in_progress"])
Query(ws).where(assigned_to__not_empty=True)
Query(ws).where(title__matches=r"^\[WIP\]")
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
```

Node labels parse but are ignored (schemaless). The `WHERE` clause uses the same operators as the filter DSL.

```bash
fm cypher ./project 'MATCH (a)-[:blocked_by*]->(a) RETURN a'
fm cypher ./project 'MATCH (a)-[:belongs_to]->(e) WHERE e.type = "epic" RETURN a, e'
```

## Traversal & resolvers

`--follow FIELD` turns the result set into the starting seeds for a graph walk along that field. `--depth N` bounds the walk (use `*` for transitive). `--direction reverse` walks incoming edges instead of outgoing.

```bash
# Direct dependencies of one task
fm query ./project 'uuid = "task-42"' --follow blocked_by --depth 1

# Full transitive dependency chain
fm query ./project 'uuid = "task-42"' --follow blocked_by --depth '*'

# What does task-42 unblock? (reverse edge)
fm query ./project 'uuid = "task-42"' --follow blocked_by --direction reverse
```

References in frontmatter fields are resolved by the selected resolver:

- `path` (default) — relative filesystem paths, e.g. `blocked_by: ../tasks/task-41.md`.
- `uuid` — matches a `uuid` frontmatter field on other packets.
- `slug` — matches a `slug` frontmatter field on other packets.

Pass `--resolver uuid` / `--resolver slug` to switch. Unresolvable references are dropped silently.

## Aggregation & describe

Group-and-aggregate returns one row per group:

```python
from fm import Query, Workspace
from fm import Count, Sum, Avg

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
fm describe ./project
fm describe ./project --format json --top 10
```

## Editing & safety

Every edit is previewable, confirmable, and preserves comments, key order, quoting, and body bytes.

```bash
# Single file
fm set ./project/tasks/task-42.md status=escalated priority=1
fm remove ./project/tasks/task-42.md temp_notes
fm rename ./project/tasks/task-42.md assignee=assigned_to
fm append ./project/tasks/task-42.md tags=urgent
fm toggle ./project/tasks/task-42.md flagged

# Bulk: pipe query results into edits
fm query ./project 'status != "done" AND due_date < today' \
  | fm set status=escalated --workspace ./project --yes

# Preview without writing
fm set ./project/tasks/task-42.md status=done --dry-run
```

Python equivalent:

```python
from fm import Workspace, Query

ws = Workspace("./project")
plan = Query(ws).where(status="active").set(status="reviewed")
print(plan.dry_run())       # unified diff
plan.apply(confirm=False)   # write
```

Value coercion from CLI strings: `true`/`false` → bool; integers and floats parsed as numbers; ISO dates (`2026-05-01`) parsed as dates; `null` → None. Quote to force string: `label='"123"'`.

**Safety model.** Bulk edits print a unified diff and prompt before writing. `--dry-run` shows the diff without writing; `--yes` skips the prompt. When stdin is piped (`fm query ... | fm set ...`), the prompt reopens `/dev/tty` — on systems without a tty (CI, containers), pass `--yes`.

**Formatting.** fm re-emits edited YAML with 2-space mapping indent and 4-space sequence offset (ruamel defaults with explicit offset). Files that don't conform can still be parsed; only edited files are re-emitted, and untouched keys round-trip byte-for-byte.

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

- [Design document](docs/design_doc.md) — rationale, comparisons, target surface.
- [Implementation plan](docs/implementation_plan.md) — milestone map (frozen; written under the working name `fmq`).
- [LICENSE](LICENSE) — MIT.
- [GitHub](https://github.com/luon-ai/fm) — source, issues, releases.
