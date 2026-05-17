---
id: 0012
title: Wikilinks as per-item dispatch in the edge enumerator, not a configurable resolver
status: accepted
date: 2026-05-17
context_task: 0029
---

## Context

Task [0029](../tasks/0029-wikilinks-support.md) adds two new edge sources to fmql's graph:

1. Body wikilinks (`[[Note Name]]` / `[[Note Name|alias]]`) → edges of type `mentions`.
2. Frontmatter values that are wholly `[[X]]` (scalar or list item) → edges typed by the property name, bypassing the configured resolver.

fmql's existing edge model is *per-field* and *resolver-driven*: a frontmatter property name binds to a `Resolver` (built-in `path` / `uuid` / `slug` / `id`, or a user-registered one), and every value in that field is fed through `resolver.resolve(raw, ...)`. The resolver is the single point where "raw value → target packet id" happens; see `resolvers.py:1-109`, the `Resolver` protocol in `types.py:10-13`, and ADR [0001](../tasks/0001-id-resolver-for-edge-fields.md) for the wider design.

The implementation question for task 0029: *where does wikilink-awareness live*, and *how do `[[]]` items coexist with the resolver path on the same field*?

Three shapes were on the table:

1. **A new `WikilinkResolver` class** registered like the others (`resolver_by_name("wikilink")`), opt-in via `WORKSPACE.md fmql.resolvers.related: wikilink`.
2. **A second pass after resolver enumeration** — run resolvers normally, then a separate pass walks frontmatter for `[[]]` items and emits additional edges.
3. **Per-item dispatch in a shared edge enumerator** — for each frontmatter item, if it matches `[[X]]` use the wikilink resolver, else fall through to the configured resolver. Body wikilinks are a special case attached to the magic field name `mentions`.

## Decision

Shape 3. Wikilink awareness lives in a new `fmql/edges.py` module (`iter_forward_targets` / `resolve_item`) that all three callsites (`traversal._neighbors`, `subgraph._edges_for`, `cypher/executor._neighbors`) now delegate to. The dispatch is:

```python
def resolve_item(workspace, src, item, resolver):
    link = match_whole_value_wikilink(item)   # str matching ^\s*\[\[X\]\]\s*$
    if link is not None:
        return resolve_wikilink(link, workspace).target
    return resolver.resolve(item, origin=src, workspace=workspace)
```

Body wikilinks are bolted onto the same enumerator under the constant `MENTIONS_FIELD = "mentions"`: when the field name being enumerated is `"mentions"`, `iter_forward_targets` first yields body-wikilink targets (resolved via `resolve_wikilink`) and *then* yields the field's frontmatter-derived edges. Per-call dedup ensures one edge per target, so a body link and a frontmatter `mentions: "[[X]]"` to the same target produce one edge, not two.

The same per-item dispatch is duplicated inside `Workspace.reverse_index(field, resolver)` (which now also handles wikilinks; the `_fused_*` shim from the plan was collapsed into the existing method).

## Rationale

### Why not a `WikilinkResolver` class

A `WikilinkResolver` would satisfy the existing `Resolver` protocol — input `raw`, output `Optional[PacketId]` — by checking the `[[X]]` shape and falling back to `None`. But binding it to a field means *every* value in that field goes through the wikilink path. Mixed lists like `related: ["[[Strategy]]", "playbook.md"]` would either:

- Lose the bare-string item (the wikilink resolver returns `None` for `"playbook.md"`), or
- Require chaining two resolvers (`wikilink → path`), which the resolver protocol doesn't currently express.

Task 0029 explicitly requires mixed lists to work: the `[[]]` item resolves as a wikilink, the bare string still goes through the bound resolver. That's per-item dispatch, not per-field binding. Forcing the wikilink-vs-resolver decision *before* iterating items is the wrong layer.

A second strike: a `WikilinkResolver` would still need to be *configured*. Obsidian users don't expect to add `fmql.resolvers.related: wikilink` to a `WORKSPACE.md` for `[[]]` to work — the syntax is the contract. Wikilinks should be recognised out of the box, on any field, in any vault.

A third strike: body wikilinks don't have a field. They come from `packet.body` text, not a frontmatter property. A resolver — whose contract is `(raw, origin, workspace) → Optional[PacketId]` — has no item to receive. Body wikilink edges would need a separate code path anyway. Putting that path alongside the per-item frontmatter dispatch in a shared `edges.py` is the natural co-location.

### Why not a second pass after resolver enumeration

Two passes would mean: (a) the resolver runs on `"[[Strategy]]"` first (and returns `None` because no resolver matches a bracket-wrapped string), then (b) the wikilink pass runs and produces the edge. Result: same edges, but the resolver gets called on every wikilink-shaped item for nothing, and `--diagnose` (which counts resolver-unresolved values as warnings) would loudly flag every `[[]]` item as a resolver miss. That would be a regression in the diagnostics signal.

You'd then have to teach `diagnose_field` to skip `[[]]`-shaped items — which the per-item dispatch model also requires, but only as a *small* hand-off ("the wikilink path counts this as resolved"). With two passes the diagnose logic has to model the union of both paths' resolution outcomes, which is harder to keep right.

Per-item dispatch makes the shadowing rule (`[[]]` wins, resolver doesn't run) a direct property of the code flow rather than a post-hoc fixup.

### Why `mentions` as a magic field name

The task ships `mentions` as the canonical body-wikilink edge type. The simplest way to make that queryable via the existing Cypher pattern (`MATCH (a)-[:mentions]->(b)`) is for the edge enumerator to recognise `field == "mentions"` and pull body-link targets in addition to whatever the field's frontmatter would produce. This means:

- `MATCH (a)-[:mentions]->(b)` and `--follow mentions` work without any new CLI flag, new AST node, or new pattern syntax — they're just normal field traversal where the enumerator happens to know one more source.
- The constant lives in `wikilinks.py` (`MENTIONS_FIELD = "mentions"`), imported by `edges.py`, `workspace.py`, and `diagnostics.py`. Single source of truth for "what does `mentions` mean."
- The task notes flag a future `WORKSPACE.md body_link_edge_type: <name>` config; that swap-in is a one-line change to read the constant from workspace config instead of from the module.

Union semantics (body wikilinks + frontmatter `mentions` items, with dedup) is the principle of least surprise for a user who already has a frontmatter `mentions` property. The alternative (raise on collision) would break vaults that legitimately use both. The dedup `set` in `iter_forward_targets` keeps the result honest.

### Why duplicate the dispatch in `Workspace.reverse_index`

The forward enumerator (`iter_forward_targets`) is per-pid: cheap to wrap each call in the `match_whole_value_wikilink → resolve_wikilink else resolver.resolve` dispatch. The reverse enumerator scans *all* packets to build `{target_pid: [source_pids]}` for a field; pulling that out as a helper would mean re-yielding (src, tgt) pairs from a generator and re-bucketing them in the reverse-index code anyway — same lines, more indirection. Reusing `resolve_item` for the per-item step gets the wikilink behaviour for free; the per-packet loop stays where it belongs (on the workspace, alongside the cache it populates).

The collapsed shape — one `reverse_index` method instead of separate `reverse_index` / `fused_reverse_index` — drops the dead "resolver-only" variant. Before the refactor there were zero external callers asking for "edges without wikilinks"; the only argument for the dual surface was "compatibility with the old behavior," which we don't owe at pre-1.0.

## Consequences

- **Wikilinks work with zero configuration.** No `WORKSPACE.md` change, no resolver binding, no CLI flag. Drop an Obsidian vault into `fmql query 'MATCH (a)-[:mentions]->(b) RETURN a, b'` and edges appear.
- **The frontmatter-shadowing rule is structurally enforced.** A `[[]]`-shaped item is dispatched to the wikilink path; the resolver is not called for it. No double-counting, no double edges. Pinned by `test_mixed_list_resolver_does_not_run_for_wikilink_item` in `test_traversal_wikilinks.py`.
- **`mentions` is a reserved field name in the engine's vocabulary.** Users with `mentions: ["task-1"]` in frontmatter get *both* their resolver-derived edge AND any body-wikilink edges, deduped. Documented in the README. If a user actively wants to suppress this (e.g. `mentions` means something domain-specific to them), the workaround is to rename the property; the future `body_link_edge_type` config offers a sharper escape.
- **`--diagnose` carries wikilink warnings via the existing entry point.** `maybe_emit_warnings(ws, fields, diagnose=…)` now emits both `FieldMismatch` warnings (resolver-bound issues) *and* `WikilinkDiagnostic` warnings (ambiguous / unresolved wikilinks). No CLI surface change.
- **`diagnose_field` short-circuits `[[]]` items as resolved.** Without this, every `[[Strategy]]` in a `related:` list would count as an unresolved value against the bound resolver and trigger a false-positive warning. The single-line short-circuit (`if match_whole_value_wikilink(item) is not None: ... continue`) is the only diagnose-side change.
- **`Workspace.reverse_index` is now wikilink-aware.** External callers depending on the *resolver-only* shape would observe the change. The grep before refactor showed only the test `test_reverse_index_cached` reaches this method outside `edges.py` — that test asserts cache identity, which still holds. No other in-tree consumer.
- **Embedded `![[X]]` and `#heading` / `^block` fragments are out of scope.** Body parsing strips them at the regex level (`(?<!!)` lookbehind for embeds) and at normalisation time (`raw.split('#')[0].split('^')[0]`). Heading-anchored links resolve to the file; block-level edges are deferred per task notes.

## Alternatives considered

- **`WikilinkResolver` registered like `uuid` / `slug` / `id`.** Rejected as above: incompatible with mixed lists, requires `WORKSPACE.md` opt-in for a syntax that should be ambient, no path for body wikilinks.
- **Second pass after resolver enumeration.** Rejected: forces `diagnose_field` to model union-of-paths instead of dispatch-per-item; calls the resolver on items the wikilink path will claim anyway; the shadowing rule becomes a post-hoc rewrite rather than a structural property.
- **Make body wikilinks a configurable opt-in (e.g. `WORKSPACE.md fmql.body_links: true`).** Rejected for v1. The Obsidian-compat use case is the headline motivation for the task — making it off-by-default just adds a configuration step the user has to remember. If body parsing turns out to be too expensive on 10k-file vaults (task notes flag this as a watched future risk), a *performance* off-switch can land later without changing the default.
- **Add a new AST node for wikilink edges (e.g. `MATCH (a)-[:[[]]]->(b)`).** Rejected: invents grammar for a problem that field-name dispatch already solves cleanly. `mentions` is a perfectly good label; the wikilinks-are-just-another-edge-source framing is what makes the existing query surface "just work."
- **Reject `mentions`-property collisions with an error.** Rejected: punishes vaults that legitimately overload the name. Union with dedup yields the expected graph (everything you'd think mentions Playbook, mentions Playbook). The escape hatch is to rename the property or wait for the `body_link_edge_type` config.
- **Keep `reverse_index` resolver-only and add `fused_reverse_index` alongside.** Considered (and was the plan-file shape). Collapsed because the only external caller is a cache-identity test that doesn't care which semantics the method has, and carrying two near-identical surfaces is the kind of "just in case" code CLAUDE.md tells us to avoid.
