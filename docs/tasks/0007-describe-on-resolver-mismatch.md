---
id: 0007
title: Surface `fmql describe` output on resolver mismatch
status: todo
priority: P2
created: 2026-04-19
updated: 2026-04-29
tags: [cli, ux, resolver, describe]
depends_on:
  - 0001-id-resolver-for-edge-fields
---

## Goal

`fmql describe` would have told us up front that `depends_on` is `list[int]` across 17 files — the smoking gun behind "why don't my edges resolve?". Today it's under-advertised: users only run it after they already know to look. Run a focused version of it implicitly when the resolver fails, so the diagnostic is right next to the symptom.

## Acceptance criteria

- [ ] When a declared edge field contains values no resolver matches (the case [0001](0001-id-resolver-for-edge-fields.md) hint covers), append a one-line summary of the field's observed value-types — e.g. `depends_on observed as list[int] in 17 packets; resolvers tried: id, slug, path`.
- [ ] The summary is emitted by `subgraph` unconditionally and by other edge-touching commands behind `--diagnose` (matches the existing opt-in shape).
- [ ] `fmql describe` itself gets a more visible mention in `docs/README.md` and in the top-level `fmql --help` epilog, as the canonical "what types are in my workspace" tool.
- [ ] `make format && make lint && make test` clean.

## Notes

Originally surfaced as feedback item #7. Pairs naturally with [0001](0001-id-resolver-for-edge-fields.md) — the resolver-mismatch hint is where this diagnostic belongs.
