---
id: 0008
title: Make every CLI path workspace-relative — args, stdin, outputs
status: todo
priority: 3
created: 2026-04-29
updated: 2026-04-29
tags: [cli, ux, workspace]
depends_on:
  - 0004-workspace-target-ergonomics
phase: next
---

## Goal

After [0004](0004-workspace-target-ergonomics.md) collapsed workspace handling onto a single `--workspace/-w` flag, the next step is to make path *content* workspace-relative everywhere: positional arguments, paths read from stdin, and paths emitted on stdout. Today the rules differ subtly between commands, which makes piping (`fmql query … | xargs fmql update`) more fragile than it should be.

## Acceptance criteria

- [ ] Audit every CLI entry point for path inputs and outputs. For each, document the current behavior (absolute? relative-to-cwd? relative-to-workspace?) before changing anything.
- [ ] Positional path args: absolute paths inside the workspace are normalized to workspace-relative; absolute paths outside the workspace error cleanly; relative paths are interpreted relative to cwd, then normalized to workspace-relative.
- [ ] Stdin paths: same normalization rules, so `fmql query … | fmql update -` works regardless of where the user piped from.
- [ ] Output paths: emitted as workspace-relative POSIX strings, never absolute, never `./`-prefixed.
- [ ] `--resolver path` semantics stay consistent: a path resolver value compares against the workspace-relative form.
- [ ] Round-trip test: `fmql query <workspace> '*' --format paths | fmql query <workspace> -` returns the same packet set regardless of the cwd at each step.
- [ ] `make format && make lint && make test` clean.

## Notes

Original wording from `TODO.md`: "All file paths in the CLI should be workspace-relative, everywhere (positional args, stdin, outputs)." This is the natural follow-up to [0004](0004-workspace-target-ergonomics.md) — the workspace flag is unified, but the *path* surface still has subtle inconsistencies.
