---
id: 0003
title: "`_id` aliases `_path` (workspace-relative path)"
status: accepted
date: 2026-05-01
context_task: 0015
---

## Context

Task [0015](../tasks/0015-cypher-pseudo-fields-id-path.md) introduces two pseudo-fields, `_id` and `_path`. The task description leaves their semantics open:

> `a._id` — a stable identifier for the document (e.g. slug / canonical id derived from path).
> `a._path` — the document's workspace-relative file path.

`_path` is unambiguous — the workspace-relative POSIX path. But "stable identifier" admits several plausible mappings: workspace-relative path, slug (`Path(pid).stem`), filename (`Path(pid).name`), a hash, a UUID, or something derived from frontmatter.

## Decision

`_id` aliases `_path`. Both evaluate to the workspace-relative POSIX path of the document — i.e. the value of `Packet.id` (`packages/fmql/src/fmql/packet.py:13`).

## Rationale

- `Packet.id` already *is* the workspace-relative path throughout the codebase (assigned in `Workspace._scan` at `workspace.py:55` as `p.resolve().relative_to(self.root).as_posix()`). It is the canonical identifier the engine uses to index and retrieve packets. Aliasing the Cypher-level `_id` to that same value keeps the language surface honest with the internal model.
- The other plausible candidates each have problems:
  - **Slug (`Path(pid).stem`)** — already addressable via the existing `slug` virtual; would duplicate that surface.
  - **Filename (`Path(pid).name`)** — already addressable via the existing `filename` virtual; not even unique (two `index.md` files in different directories collide), so it cannot be a "stable identifier."
  - **Hash / UUID / generated id** — invents a new identity scheme the rest of the system doesn't use.
- Aliasing keeps the change small and reversible: `pseudo_field(pid, name)` is a single helper. If a future task introduces a separate identity (e.g. a content-addressed hash), the mapping changes in one place without disturbing call sites.

## Consequences

- `t._id == t._path` for every packet. Documented in the README pseudo-fields table.
- Users who want the slug-shaped identity continue to use `t.slug` (or the future `_slug` if we ever add it).
- Migrating to a distinct `_id` value later is a one-line change in `pseudo_field()` plus a README update; no Cypher syntax change required.

## Alternatives considered

- **`_id == slug`** — concise but redundant with the existing `slug` virtual, and locks `_id` to a value that isn't actually unique across nested directories.
- **Reserve `_id` without defining it** — make `_id` parse but raise on read until a future task defines its value. Rejected as a worse user experience: the task ships a usable surface, not a placeholder.
