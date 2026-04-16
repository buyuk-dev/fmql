# fmq — FrontMatter Utilities

A schemaless query engine and editor for directories of frontmatter (markdown + YAML) files.

Point it at any directory. Query with filters, traversal, aggregation, and graph patterns. Edit properties across single files or entire result sets. No configuration, no schema.

## Status

Phase A (read path) — in progress. See [design_doc.md](design_doc.md) for the full target surface.

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
