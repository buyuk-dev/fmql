# fmq — FrontMatter Utilities

A schemaless query engine and editor for directories of frontmatter (markdown + YAML) files.

Point it at any directory. Query with filters, traversal, aggregation, and graph patterns. Edit properties across single files or entire result sets. No configuration, no schema.

## Status

- Phase A (read path) — shipped.
- Phase B (edit path) — shipped.

See [docs/design_doc.md](docs/design_doc.md) for the full target surface and [docs/implementation_plan.md](docs/implementation_plan.md) for the milestone map.

## Quickstart

```bash
uv sync
uv run fmq query ./project 'status = "active" AND priority > 2'
uv run fmq query ./project 'due_date < today' --format json
```

```python
from fmq import Workspace, Query

ws = Workspace("./project")
q = Query(ws).where(status="active", priority__gt=2)
for packet in q:
    print(packet.id)
```

## Editing

Every edit is previewable, confirmable, and preserves comments, key order, quoting, and body bytes.

```bash
# single file
uv run fmq set ./project/tasks/task-42.md status=escalated priority=1
uv run fmq remove ./project/tasks/task-42.md temp_notes
uv run fmq rename ./project/tasks/task-42.md assignee=assigned_to
uv run fmq append ./project/tasks/task-42.md tags=urgent
uv run fmq toggle ./project/tasks/task-42.md flagged

# bulk: pipe query results into edits
uv run fmq query ./project 'status != "done" AND due_date < today' \
  | uv run fmq set status=escalated --workspace ./project --yes

# preview without writing
uv run fmq set ./project/tasks/task-42.md status=done --dry-run
```

```python
from fmq import Workspace, Query

ws = Workspace("./project")
plan = Query(ws).where(status="active").set(status="reviewed")
print(plan.dry_run())     # unified diff
plan.apply(confirm=False)  # write
```

Values are coerced from strings: `true`/`false` → bool, integers, floats, ISO dates (`2026-05-01`), `null` → None. Quote to force string: `label='"123"'`.

**Safety:** bulk edits print a unified diff and prompt before writing. `--dry-run` shows the diff without writing; `--yes` skips the prompt. When stdin is piped (`fmq query ... | fmq set ...`), the prompt reopens `/dev/tty` — on systems without a tty, pass `--yes`.

**Formatting:** fmq re-emits edited YAML with 2-space mapping indent and 4-space sequence offset (ruamel defaults with explicit offset). Files that don't conform can still be parsed; only edited files are re-emitted, and untouched keys round-trip byte-for-byte.
