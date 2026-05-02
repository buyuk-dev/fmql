---
id: 0025
title: fmql organize — suggest folder structure aligned with query co-location
status: todo
priority: 3
created: 2026-05-02
updated: 2026-05-02
tags: [wishlist, cli, organize, workspace, heuristics]
depends_on:
  - 0012-filesystem-level-operations
  - 0013-link-doctor-on-filesystem-changes
phase: workspace
---

## Goal

Treat folders as **query-co-location boundaries**, not as taxonomy. Documents that are frequently returned by the same query benefit from sharing a parent directory: the directory becomes a cheap pre-filter for the query, an indexable unit (e.g. for semantic indices that scope to a subtree), and a boundary for permissions, sharing, and archival. Documents that are *never* co-queried do not benefit from being co-located, regardless of how the user originally organized them.

`fmql organize` operationalizes this principle: read a workspace's canonical queries, observe which directories the results actually span, and propose folder structure changes that bring the layout into alignment with the workload.

v1 ships in `--suggest` mode only — read-only, prints proposed moves with rationale, no file changes. `--apply` mode is a separate, later task once the heuristics have been validated against multiple workspaces and the suggestions are usually correct.

### Why

The current pattern in growing workspaces is that folders accumulate as taxonomy ("notes go in `notes/`, blog posts go in `blog-posts/`, samsung-related stuff goes in `samsung/`"). Over time the taxonomy diverges from how the workspace is actually queried — a `samsung/karol.md` file is also a "people" doc, also a "competitor-intel" doc, also a "draft" doc, but it can only live in one folder. fmql + frontmatter let you slice across all those dimensions in queries, which means the folder choice should be driven by the *one dimension where co-location matters for performance / indexability / boundary semantics*, not by abstract category.

`fmql organize` makes that decision auditable and incremental. Instead of a manual reorganization pass that the user does once and then drifts away from, the workspace's structure becomes a measurable property of its workload, with suggested corrections when they diverge.

This is also a publishable artifact for the WandaOS narrative — "the workspace reorganizes itself based on how it's actually used" is a concrete demonstration of the self-organizing-substrate thesis. The suggest-only v1 is the right shipping shape because it makes the principle visible without committing to automated moves before the heuristics are battle-tested.

### Non-goals (v1)

- **Auto-applying moves.** That depends on `fmql mv` (0012) + edge doctoring (0013) being solid, plus enough usage of `--suggest` to know the suggestions are usually right. Separate task once both are true.
- **Query-log-driven analysis.** Observing actual query traffic to learn co-occurrence is a richer second mode. v1 reads canonical queries from config; the log-driven mode is a later iteration.
- **Cross-workspace analysis.** Each workspace is organized independently. No federation logic, no comparison across workspaces.
- **Frontmatter migration suggestions.** If the folder hierarchy currently encodes a dimension that should move into frontmatter (e.g. status-as-folder in a project board), this task does *not* propose those migrations. That's a separate concern; a future `fmql migrate-frontmatter` or similar.

## Acceptance criteria

### CLI

- [ ] `fmql organize --suggest` (or just `fmql organize`, with `--suggest` as the default mode) reads the workspace's canonical queries from a config file, runs them, and prints proposed moves with rationale. Exits non-zero if any suggestions were emitted, zero if structure is already optimal (useful for CI / pre-commit checks).
- [ ] `--config <path>` overrides the default config location.
- [ ] `--query <name>` restricts analysis to a single named query (useful for iterating on the config).
- [ ] `--format <human|json>` switches output between human-readable rationale and machine-parseable suggestions (the latter feeds future `--apply` tooling).
- [ ] `--threshold <float>` controls how aggressive the suggester is — only suggest moves when the co-location confidence exceeds the threshold. Default reasonable (e.g. 0.7).

### Config format

- [ ] Canonical queries live in `.fmql/organize.yaml` (or equivalent — pick a path consistent with existing fmql config conventions; check 0008's workspace-relative-paths handling). Schema: a list of named queries with a Cypher / qlang body and optional weight.
- [ ] Example config in the docs covering a realistic case: a workspace with `notes/`, `blog-posts/`, `samsung/` folders and queries like `topic = "samsung"`, `type = "blog-post"`, `category = "strategy"`.
- [ ] Missing config: helpful error pointing to docs and an example. Don't auto-generate, don't guess — explicit declaration is part of the value.

### Heuristics (v1, simple and explainable)

- [ ] For each canonical query, compute the result set and tabulate which directory each result lives in.
- [ ] **Outlier detection**: if N% of a query's results live in folder A and a small number of results live elsewhere, suggest moving the outliers into A. N configurable via threshold; default 70%.
- [ ] **Folder coherence**: for each folder, check what fraction of its contents appear together in any single canonical query. If the folder contains documents that are never co-queried, flag it as low-coherence (no specific move, just a warning that the folder may not be earning its keep).
- [ ] **Conflict resolution**: a document may be a candidate for relocation by multiple queries. The suggester picks the highest-confidence destination and notes the runner-up in the rationale. No silent loss.
- [ ] Each suggested move has a one-line rationale: `"Move A → B because query 'samsung-related' returns A and 12 of 14 results live in B (confidence 0.86)."`

### Output

- [ ] Human format: grouped by suggested destination directory, each move listed with rationale, count and confidence summary at the bottom.
- [ ] JSON format: array of `{src, dst, confidence, rationale, query}` objects suitable for piping into a future `--apply` tool or a custom script.
- [ ] If no suggestions: print a one-line "structure is aligned with current canonical queries" message and exit 0.

### Tests

- [ ] Synthetic workspace fixtures with known co-query patterns; assert specific suggestions are emitted with the expected confidence.
- [ ] Edge cases: empty workspace, workspace with no canonical queries, query that returns no results, query that returns documents from one folder (no suggestions), query that returns documents evenly split across folders (suggestion or no? — pick a behavior and assert it).
- [ ] Threshold behavior: same fixture, different thresholds, different suggestion counts.
- [ ] `make format && make lint && make test` clean.

### Docs

- [ ] `docs/organize.md`: explain the principle, the config format, the heuristics, the suggest-vs-apply distinction, and link to 0012 / 0013 for the eventual apply path.
- [ ] README mention with one-line description and link to `docs/organize.md`.

## Notes

### Where the principle is documented

The "folders as query-co-location boundaries" framing should be stated explicitly somewhere in the fmql or WandaOS docs (likely the AIOS concept doc or a fmql design doc). This task assumes that doc exists and references it. If it doesn't yet, write a short architecture note as part of this task and link to it from `docs/organize.md`.

### Why suggest-only in v1

Two reasons. First, the heuristics are unvalidated — the principle is sound but the threshold tuning, the conflict resolution, and the outlier definition all need real-workspace testing before they're trustworthy enough to auto-apply. Suggest-only mode produces the data needed to refine them. Second, automated file moves on a workspace have high blast radius: broken markdown links, lost git history continuity, agents whose state depends on paths. 0012 + 0013 together address most of that, but until we've used `--suggest` enough to know the suggestions are *right*, we shouldn't be moving files based on them.

### When to spec the `--apply` follow-up

Sometime after this task ships and has been used on a few real workspaces (the WandaOS workspace itself is the first dogfooding target). When the suggestions stop surprising the user — i.e. the user reads them and almost always agrees — write the follow-up task that adds `--apply` on top of `fmql mv` (0012) and the link doctor (0013). Likely two-week effort once that point is reached.

### Single-user dogfooding

The founder's WandaOS workspace is the first and primary user of this. The whole point is to test the principle against a real, messy workspace before generalizing. Don't optimize the v1 for hypothetical multi-user scenarios — make it work well for the dogfooding case and let real usage drive the next iteration.

### Future modes (out of scope)

- **Query-log mode**: observe actual queries (from a query log fmql would need to start writing) and use frequency-weighted co-occurrence as the signal instead of explicit canonical queries. Richer, more automatic, but requires opt-in logging and raises privacy considerations for shared workspaces.
- **Index-target mode**: instead of (or in addition to) co-query detection, declare "I want to build a semantic index over X" and have organize suggest the folder structure that makes X scope cleanly.
- **Negative co-location**: detect documents that are *never* co-queried and live in the same folder, suggest splitting. Currently captured weakly via "folder coherence" warning; could become a first-class signal.
