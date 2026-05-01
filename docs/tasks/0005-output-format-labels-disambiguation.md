---
id: 0005
title: Disambiguate `--format json` between NDJSON and JSON-array output
status: todo
priority: 2
created: 2026-04-19
updated: 2026-04-29
tags: [cli, output, ux, docs]
depends_on: []
phase: cli
---

## Goal

`--format json` on `fmql query` emits NDJSON; on `fmql subgraph` it emits a single JSON object. The flag label doesn't distinguish, so `jq` users will write `jq -s` by habit after getting burned once. Either rename the values or document the difference loudly.

## Acceptance criteria

- [ ] Pick one of: (a) keep `json` and add `jsonl` / `json-array` / `ndjson` siblings with explicit semantics; (b) split per-command (`--format ndjson` on `query`, `--format json` on `subgraph`) and deprecate the ambiguous label; (c) keep the label and document the difference in `--help` plus a callout in `docs/README.md`.
- [ ] Whichever option is chosen, the help text for `--format` on every command states exactly what the output shape is (one object per line vs single object vs single array).
- [ ] If labels change, keep the old `--format json` accepted for at least one minor version with a stderr deprecation warning.
- [ ] `make format && make lint && make test` clean.

## Notes

Originally surfaced as feedback item #5. Categorized as a papercut rather than a hard bite — but the kind of papercut that compounds across `jq` pipelines.
