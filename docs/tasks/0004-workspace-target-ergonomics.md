---
id: 0004
title: Unify workspace / target handling across CLI commands
status: done
priority: 1
created: 2026-04-19
updated: 2026-04-28
tags: [cli, ux, workspace]
depends_on: []
phase: workspace
---

## Goal

Workspace and target ergonomics were inconsistent across the CLI:
- `-w <file>` crashed with a `FileNotFoundError` Python traceback; `-w <dir> <abspath-outside-dir>` gave a clean `error: path not inside workspace`. Same conceptual failure, two different error modes.
- Edit commands required `cwd` inside the workspace or relative paths passed as plain filenames; query commands happily took `docs/tasks` from repo root. The divergence was surprising.

## Acceptance criteria

- [x] All CLI commands accept a single `--workspace/-w` flag, defaulting to cwd.
- [x] `-w <file>` errors cleanly (no Python traceback); `-w <missing-path>` errors cleanly; `-w` omitted means cwd.
- [x] Legacy `set / append / remove / rename / toggle` commands removed; all edits route through `fmql update 'MATCH … [WHERE …] [SET …] [REMOVE …]'` (see [0003](0003-bulk-migrations-cypher-update.md)).
- [x] `make format && make lint && make test` clean.

## Notes

Resolved alongside [0003](0003-bulk-migrations-cypher-update.md) as part of the CLI unification work. Subsequent task [0008](0008-workspace-relative-paths-everywhere.md) extends this to make every path argument and output workspace-relative.
