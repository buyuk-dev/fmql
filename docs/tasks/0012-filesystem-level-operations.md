---
id: 0012
title: Filesystem-level operations (ls, mv, cp, rm, stat) over the workspace
status: todo
priority: P3
created: 2026-04-19
updated: 2026-04-29
tags: [wishlist, cli, filesystem, edits]
depends_on:
  - 0008-workspace-relative-paths-everywhere
---

## Goal

Round out the CLI with first-class filesystem operations that respect workspace semantics: inspect filesystem metadata (`stat`, `ls`) and perform basic file-tree edits (`mv`, `cp`, `rm`). Today these always require dropping out of fmql to the shell, which loses workspace-relative path normalization and breaks composability with `fmql query` / `fmql update` pipes.

## Acceptance criteria

- [ ] `fmql ls [PATH]` lists packets in a workspace path, with frontmatter-aware columns (id, title, status, mtime) instead of raw `ls -l` output.
- [ ] `fmql mv <src> <dst>` and `fmql cp <src> <dst>` move/copy packets, with workspace-relative path semantics from [0008](0008-workspace-relative-paths-everywhere.md).
- [ ] `fmql rm <path>` deletes packets with a confirmation prompt by default and `--force` to skip it.
- [ ] `fmql stat <path>` shows filesystem metadata plus parsed frontmatter and outgoing/incoming edge counts.
- [ ] Each operation composes with `fmql query` via stdin (`fmql query … | fmql rm -` etc.).
- [ ] `make format && make lint && make test` clean.

## Notes

Originally on the wishlist in `TODO.md`. The `mv` / `rm` operations naturally pair with [0013](0013-link-doctor-on-filesystem-changes.md) — once fmql knows about file moves and deletes, it can fix dangling references automatically.
