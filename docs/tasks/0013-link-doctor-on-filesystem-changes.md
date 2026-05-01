---
id: 0013
title: Auto-doctor edge references when files move or are deleted
status: todo
priority: 3
created: 2026-04-19
updated: 2026-04-29
tags: [wishlist, edges, resolver, filesystem, integrity]
depends_on:
  - 0012-filesystem-level-operations
phase: wishlist
---

## Goal

Once filesystem operations are first-class ([0012](0012-filesystem-level-operations.md)), use that to keep the graph honest: when a packet is moved or deleted, find every other packet whose edge fields point at it and update or surface those references automatically.

## Acceptance criteria

- [ ] `fmql mv <src> <dst>` rewrites every edge that resolves to `<src>` so it now resolves to `<dst>`. Path-resolver edges get their values updated; id/slug-resolver edges are left alone (their target identity is preserved by the move).
- [ ] `fmql rm <path>` produces a "dangling references" report listing every packet that still points at the deleted target, with `--prune` to remove those edge entries and `--keep` to leave them alone (the default warns and aborts).
- [ ] A standalone `fmql doctor` command audits the workspace for dangling edges without requiring a triggering operation, reporting which target each broken reference *probably* meant (using the same scoring the resolver-mismatch hint uses).
- [ ] All three operations are dry-runnable with `--dry-run` showing the edits that would be applied.
- [ ] `make format && make lint && make test` clean.

## Notes

Originally on the wishlist in `TODO.md` (added in commit 8667abf, 2026-04-19). This is the payoff for [0012](0012-filesystem-level-operations.md) — owning the filesystem ops means fmql can keep the graph consistent across them, instead of leaving the user to grep-and-rewrite by hand after a `git mv`.
