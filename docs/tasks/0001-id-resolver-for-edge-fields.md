---
id: 0001
title: ID resolver for edge fields, with type-aware mismatch warnings
status: done
priority: P1
created: 2026-04-19
updated: 2026-04-27
tags: [resolver, edges, ux]
depends_on: []
---

## Goal

Edge-shaped frontmatter fields (`depends_on: [1, 8, 17]`) should resolve reliably even when their values are integers, strings, slugs, or paths. Today, resolvers bind to field *names* implicitly with no type awareness — `depends_on: [1, 8, 17]` went through every resolver without matching and the output was silently empty edges. The `subgraph` hint saved that case, but `query --follow` might not have.

## Acceptance criteria

- [x] Ship a built-in `id` resolver that matches against the `id` frontmatter field — covers the most common case for roadmap / ADR / ticket corpora and handles YAML's leading-zero coercion.
- [x] Per-workspace resolver configuration (`WORKSPACE.md`) so multiple reference-shaped fields with different target spaces can coexist (one resolver per workspace breaks as soon as you have `depends_on: slug` and `supersedes: path`).
- [x] When a declared edge field contains values no resolver matches, surface a warning — at minimum from `subgraph`, and behind an opt-in `--diagnose` flag for `query` and other commands that touch edges.
- [x] `make format && make lint && make test` clean.

## Notes

Resolved in commit 16c024b (2026-04-27): introduced `IdResolver`, `WORKSPACE.md` workspace config for per-field resolver binding, and the opt-in `--diagnose` flag. The original feedback called this the highest-weight backlog item alongside list-valued `set` and bulk migrations.
