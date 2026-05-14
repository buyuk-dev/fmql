---
id: 0029
title: Wikilink support — body parsing and frontmatter `[[]]` value recognition
status: todo
priority: 1
created: 2026-05-09
updated: 2026-05-09
tags: [parser, edges, obsidian, frontmatter, body]
depends_on: []
phase: parser
---

## Goal

Today fmql only reads frontmatter, and frontmatter property values are treated as plain strings regardless of syntax. This blocks two things power users expect from any tool that claims to read a markdown vault:

1. Body `[[Note Name]]` wikilinks — Obsidian's primary linking mechanism. Today they're invisible to fmql.
2. Frontmatter values wrapped in `[[]]` — Obsidian's Properties feature treats these as link-typed properties and renders them as graph edges. Today fmql treats them as opaque strings.

Add wikilink parsing in both places:

- *Body wikilinks.* Each `[[X]]` in a note body creates an edge of type `mentions` (the canonical untyped edge name) targeting the resolved note.
- *Frontmatter `[[]]` values.* When a frontmatter property's value is `[[X]]` (in a list or scalar), create an edge of type `<property_name>` targeting the resolved note. E.g., `related: ["[[Strategy]]"]` creates a `related` edge — same type the bare-string form would have produced under fmql's current resolver, but now actually creates an edge regardless of whether a resolver is configured.

This unlocks Obsidian-graph parity (vault contents render the same in Obsidian and in fmql queries) and is the prerequisite for the `vault-prep` agent template that converts path-style `related:` arrays to `[[]]` form.

## Acceptance criteria

- [ ] Body wikilinks parsed during workspace load. Pattern `\[\[([^\]|]+)(\|[^\]]*)?\]\]` (the `|alias` form is permitted but the alias is ignored for resolution; the part before `|` is the link target).
- [ ] Each parsed body wikilink creates an edge of type `mentions` from the source packet to the resolved target packet.
- [ ] Frontmatter values matching the `[[X]]` shape (whole value is wrapped in brackets, in a list or scalar) create edges of type equal to the property name. Mixed lists are allowed (`related: ["[[A]]", "B"]` creates one edge from the first item; the second item still goes through the existing resolver path).
- [ ] Wikilink resolution: `[[Note Name]]` matches a packet whose basename (without `.md`) equals `Note Name`. Path-form `[[folder/Note Name]]` resolves to that specific workspace-relative path. Multiple matches: take the first deterministic order (alphabetical by path) and emit a `--diagnose` warning, mirroring the existing resolver-mismatch convention from [0001](0001-id-resolver-for-edge-fields.md).
- [ ] Missing target: edge points to a `None` / unresolved packet, surfaced via `--diagnose` (existing dangling-edge plumbing). Doesn't fail the load.
- [ ] Existing fmql behavior unchanged for users who don't use wikilinks. Frontmatter without `[[]]` syntax stays in the resolver path it's on today; no double-counting if both a resolver match and a `[[]]` form exist for the same value (`[[]]` wins, resolver doesn't run).
- [ ] `MATCH (a)-[:mentions]->(b)` returns body-wikilink edges; `MATCH (a)-[:related]->(b)` returns frontmatter `[[]]` edges typed by property name; both compose with `WHERE` and `RETURN`.
- [ ] `--follow mentions` and `--follow related --depth N` traverse the new edges as expected.
- [ ] Tests in `packages/fmql/tests/test_*` cover:
  - Single body wikilink, multiple body wikilinks per file, alias form (`[[Note|alias]]`).
  - Frontmatter `[[]]` in list values and scalar values.
  - Ambiguous resolution (two files with the same basename) — deterministic pick + diagnose.
  - Missing target — unresolved edge + diagnose.
  - Path-form wikilink (`[[business/notes/Strategy]]`).
  - Coexistence: bare-string `related: [Strategy]` going through the resolver, `[[]]` form bypassing it; same workspace, both work.
  - `MATCH ... mentions` and `MATCH ... related` against fixtures.
  - `--follow mentions` traversal output.
- [ ] README updates: a section under "Edges" documenting both wikilink shapes, the `mentions` convention for body links, and the property-name convention for frontmatter `[[]]` values. Cross-link from the Obsidian-compatibility note.
- [ ] `make format && make lint && make test` clean.

## Notes

### Body link edge type

Default edge type for body wikilinks is `mentions`. The brainstorming session ([fmql_brainstorming_session.md](https://github.com/buyuk-dev/wandaos-business)) argued for body links as untyped with a single canonical type; `mentions` matches that intent and is intuitive. If users want a different name, expose a `WORKSPACE.md` config (`body_link_edge_type: <name>`) in a follow-up; ship the default in v1.

### Plugin vs. core

The original brainstorming captured body parsing as plugin-shaped. For v1 ship it in core — wikilink parsing is foundational enough that requiring a plugin adds friction for the dominant user flow (Obsidian compatibility). If a plugin model later proves itself for other extractors (Dataview fields, task syntax, etc.), the body-wikilink path can be refactored behind that interface. Don't pre-commit to plugin-shape today.

### Frontmatter shadowing

If a frontmatter property has a `[[]]` value AND a configured resolver for that property name, `[[]]` wins — no double-edge, no resolver-call. This keeps semantics single-source and matches the principle that explicit syntax overrides inferred behavior. Document in README.

### Performance

Body parsing is O(file_size) per note. For typical workspaces this is fine; a regex pass on each load is cheap. Cache the parsed wikilinks alongside frontmatter in the workspace state so query-time access is constant.

For 10k-file workspaces, the body-parse pass at load time is the largest single cost. If it shows up in profiling, the natural mitigation is parallelism (per-file body parsing is embarrassingly parallel) or caching parsed-wikilink artifacts to disk between runs. Out of scope for this task; flagged for follow-up if needed.

### Obsidian compatibility test

Add at least one test that takes an Obsidian-shaped vault fixture (notes with both body wikilinks and frontmatter `[[]]` properties under various property names) and asserts the resulting graph matches what Obsidian would render. Pin the parity claim with a real fixture; don't trust prose alone.

### Out of scope

- *Embedded wikilinks* (`![[Note]]`) — render-the-content-here syntax, not a graph edge in the traversal sense. Skip in v1; address if/when needed.
- *Block / heading references* (`[[Note#heading]]`, `[[Note^block-id]]`). The link-target part is the same parse target as a plain `[[Note]]`; the heading/block fragment can be ignored for edge resolution in v1. Resolution is to the file. Document in README.
- *External / web wikilinks* — not a thing in standard Obsidian; skip.
- *Backlinks panel data* (Obsidian's "Linked mentions" / "Unlinked mentions"). Out of scope; that's a UI concern, not a substrate one.
- *Configurable body link edge type* via `WORKSPACE.md`. Default to `mentions`; configuration is a follow-up.
