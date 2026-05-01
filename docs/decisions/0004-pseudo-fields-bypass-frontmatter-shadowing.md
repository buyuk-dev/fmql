---
id: 0004
title: Pseudo-fields bypass frontmatter shadowing
status: accepted
date: 2026-05-01
context_task: 0015
---

## Context

The existing virtual properties shipped in task [0003](../tasks/0003-bulk-migrations-cypher-update.md) (`t.path`, `t.filename`, `t.slug`) follow a "frontmatter wins" rule: if a packet has its own `path:` key in frontmatter, that value shadows the path-derived virtual. The README documents this explicitly:

> Frontmatter keys take precedence — if a packet already has its own `path` field, that value wins.

Task [0015](../tasks/0015-cypher-pseudo-fields-id-path.md) introduces `_id` and `_path` and asks (acceptance criterion 1):

> `_id` and `_path` are resolvable in `WHERE` without requiring any frontmatter changes.

The motivation is "no first-class way to pin a start node to a specific document … without adding bookkeeping fields … to the frontmatter of every file."

If `_path` follows the existing shadow-by-frontmatter rule, this guarantee silently breaks the moment a user has a `_path:` key in their frontmatter for unrelated reasons. The task's whole point is a *non-negotiable* identity surface.

## Decision

Pseudo-fields (`_id`, `_path`, and any future `_`-prefixed entries in `PSEUDO_FIELDS`) bypass frontmatter. A frontmatter `_path:` key does **not** shadow the pseudo-field; the canonical packet identity wins.

This is implemented in `packet_field()` (`packages/fmql/src/fmql/cypher/expr.py`) as an early return *before* the frontmatter lookup.

## Rationale

- The leading underscore signals a language-reserved namespace, analogous to Python dunders. Users should not expect their frontmatter keys in that namespace to be honored.
- The acceptance criterion "without requiring any frontmatter changes" is only satisfiable if frontmatter cannot break the pseudo-field. A shadow-by-frontmatter pseudo-field offers a weaker guarantee than the existing virtuals — pointless.
- We also reject `SET t._path = ...` and `REMOVE t._id` at validation time, so users can't accidentally introduce a frontmatter key that conflicts with the pseudo-field through normal Cypher edits. The remaining route is direct file editing, where the user has explicitly opted into a frontmatter override; in that case the pseudo-field still wins, which is the documented behavior.

## Consequences

- Two parallel surfaces in Cypher: `t.path` (shadowable by frontmatter, unchanged) vs `t._path` (canonical, not shadowable). Documented side by side in the README.
- The existing virtuals' shadow-by-frontmatter behavior is preserved — backwards compatible. Users who relied on overriding `t.path` via frontmatter keep that behavior.
- The `_validate()` rejection of `SET`/`REMOVE` on pseudo-fields is a hard guarantee at the language level, but it does not (and cannot) prevent a user from manually editing a `_path:` key into a YAML file. In that case, the pseudo-field still resolves to the canonical path; the frontmatter key becomes inert dead weight visible only via `RETURN t.field("_path")` or similar low-level access. This is the right trade-off: the pseudo-field is the authoritative answer; rogue frontmatter is a no-op.

## Alternatives considered

- **Mirror the existing `path`/`slug`/`filename` shadowing rule.** Simpler (no behavior divergence), but defeats the task's acceptance criterion. Rejected.
- **Reject queries where a packet has a frontmatter `_path:` key.** Loud failure mode, surfaces the conflict. Rejected because it punishes innocent users (e.g. someone with a `_path` key for a note-taking convention unrelated to fmql) and runs counter to the schemaless ethos.
