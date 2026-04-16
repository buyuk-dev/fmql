# FrontMatter Utilities (fm)

**A schemaless query engine and editor for directories of frontmatter files.**

Point it at any directory of markdown/YAML files. Query with filters, traversal, aggregation, and graph patterns. Edit properties across single files or entire result sets. No configuration, no schema, no setup.

---

## The Problem

Frontmatter files (markdown + YAML metadata) are everywhere — project management, knowledge bases, documentation, static sites, personal notes. But working with them across a directory is limited to `grep` for reading and manual editing for writing. There's no tool that treats a directory of frontmatter files as a queryable, editable database with relationships, aggregation, and graph traversal.

Existing tools are per-ecosystem (Obsidian, Hugo, Logseq) and weak on both querying and bulk operations. Nothing lets you say "find all tasks blocked by something tagged critical, transitively" — let alone "set the status of all overdue tasks to 'escalated'."

## The Idea

A Python package + CLI that treats a directory of frontmatter files the way MongoDB treats a collection of documents — schemaless, type-aware, queryable, and editable.

**Core design decisions:**

- **Truly schemaless.** No schema files, no declarations, no configuration. The engine respects the types YAML already provides (int, float, string, bool, datetime, list, map). No additional inference or coercion. Heterogeneous data is handled honestly — a query like `priority > 2` matches files where `priority` is an integer greater than 2, and simply excludes files where it's a string or missing.

- **Relationships derived from query operators.** YAML doesn't have a "reference" type, so the engine doesn't pretend it does. When a user calls `follow("blocked_by")`, the engine resolves the values in that field as references (paths, UUIDs, slugs) and traverses. The query operation defines what a relationship is, not a schema.

- **Graph patterns via Cypher-compatible subset.** For the ~5% of queries that need real graph shape (dependency chains, cycle detection, subgraph extraction), support a subset of Cypher pattern syntax. Not the foundation — an escape hatch for when filters + traversal aren't enough.

- **Pluggable search indexes.** Minimal protocol: `search(query: str) -> Iterable[PacketId]`. Register any index (semantic, full-text, custom). Without one, falls back to text scan. Keeps the core dependency-free.

- **Edit operations on files.** Set, remove, rename, and append to frontmatter properties — on individual files or across query result sets. Edits are surgical: they modify only the YAML frontmatter block, preserving the body content, formatting, and comments. Query results pipe directly into edit operations, enabling bulk mutations like "set status to 'escalated' on all overdue tasks."

## Query Examples

```python
from fm import Workspace, Query

ws = Workspace("./project")
q = Query(ws)

# filter by properties (types come from YAML)
q.where(status="active", priority__gt=2)

# follow a relationship
q.where(uuid="abc-123").follow("blocked_by")

# transitive traversal
q.where(uuid="abc-123").follow("blocked_by", depth="*")

# reverse: what does this task unblock?
q.where(uuid="abc-123").follow("blocked_by", direction="reverse")

# aggregation
q.where(type="task", in_sprint="sprint-3").group_by("status").count()

# combine with search
q.where(type="task").search("indemnification clauses", index="semantic")

# graph pattern (Cypher subset) for the rare complex case
q.cypher("MATCH (a)-[:blocked_by*]->(a) RETURN a")  # cycle detection
```

CLI:

```bash
fm query ./project 'status = "active" AND priority > 2'
fm query ./project 'type = "task"' --follow blocked_by --depth 3
fm describe ./project   # show observed fields, types, inconsistencies
```

## Edit Examples

Single-file operations:

```python
from fm import File

f = File("./project/tasks/task-42.md")

f.set(status="escalated")                 # set a property
f.set(priority=1, assigned_to="alice")    # set multiple
f.remove("temp_notes")                    # remove a property
f.rename(assignee="assigned_to")          # rename a property
f.append(tags="urgent")                   # append to a list
f.toggle("flagged")                       # toggle a boolean
```

Bulk operations — query results pipe into edits:

```python
# escalate all overdue open tasks
q.where(status__not_in=["done"], due_date__lt=today).set(status="escalated")

# tag everything in a dependency chain
q.where(uuid="task-42").follow("blocked_by", depth="*").append(tags="blocked-chain")

# remove a deprecated field from all files
q.all().remove("old_field")

# move a sprint's tasks to the next sprint
q.where(in_sprint="sprint-3", status__not="done").set(in_sprint="sprint-4")
```

CLI:

```bash
# single file
fm set ./project/tasks/task-42.md status=escalated priority=1
fm remove ./project/tasks/task-42.md temp_notes
fm rename ./project/tasks/task-42.md assignee=assigned_to

# bulk: pipe query results into edits
fm query ./project 'status != "done" AND due_date < today' | fm set status=escalated
fm query ./project 'in_sprint = "sprint-3"' | fm append tags=migrated
fm query ./project '*' | fm remove old_field
```

**Safety:** Bulk edits show a preview (files affected, changes to be made) and require confirmation before writing. `--dry-run` flag for scripting. `--yes` to skip confirmation. Git-friendly by design — run `git diff` after any edit to see exactly what changed.

## What Makes It Different

| | grep/ripgrep | Obsidian search | Datasette | **This** |
|---|---|---|---|---|
| Works on any frontmatter dir | ✓ | ✗ (vault only) | ✗ (needs DB) | ✓ |
| Typed comparisons (dates, numbers) | ✗ | partial | ✓ | ✓ |
| Relationships / traversal | ✗ | ✗ | manual joins | ✓ |
| Graph patterns | ✗ | ✗ | ✗ | ✓ |
| Aggregation | ✗ | ✗ | ✓ | ✓ |
| Edit / bulk mutations | ✗ | ✗ | ✗ | ✓ |
| Pluggable search (semantic, etc.) | ✗ | ✗ | ✗ | ✓ |
| Zero setup | ✓ | ✗ | ✗ | ✓ |

## Concrete Use Case: Project Management

A JIRA-like system built on frontmatter files. Tasks, epics, sprints — each a markdown file with YAML metadata. Relationships via fields like `blocked_by`, `belongs_to`, `assigned_to`.

Queries that matter daily:

- My open tasks this sprint — `where(assigned_to="me", status__in=["todo", "in_progress"], in_sprint="current")`
- What's blocked — `where(blocked_by__not_empty=True).follow("blocked_by")`
- Sprint progress — `where(in_sprint="sprint-3").group_by("status").aggregate(count=Count(), points=Sum("points"))`
- Dependency chain — `where(uuid="task-42").follow("blocked_by", depth="*")`
- What's slipping — `where(status__not_in=["done"], due_date__lt=today)`

Edits that matter daily:

- Close a task — `fm set ./tasks/task-42.md status=done`
- Escalate overdue — `q.where(status__not_in=["done"], due_date__lt=today).set(status="escalated")`
- Reassign someone's tasks — `q.where(assigned_to="bob").set(assigned_to="alice")`
- Move incomplete work to next sprint — `q.where(in_sprint="sprint-3", status__not="done").set(in_sprint="sprint-4")`

## Package Shape

- **Pure Python**, minimal dependencies. `pip install fm`.
- **CLI** for terminal use and scripting.
- **Library** for embedding in larger systems.
- `describe` command for workspace introspection — shows all observed fields, their types across files, inconsistencies.
- Optional `fm[semantic]`, `fm[sqlite]` extras for index backends.
- MIT licensed, designed for open-source release.

## Status

Design phase. Looking for feedback on the query model and API surface before implementation.
