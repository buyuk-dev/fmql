---
id: 0022
title: Resolve Cypher-compatibility divergences (`+=` semantics, function-name collisions)
status: todo
priority: P3
created: 2026-04-30
updated: 2026-04-30
tags: [cypher, language, compatibility, footgun]
depends_on: [0021]
---

## Goal

Now that Cypher is becoming the single query language ([0021](0021-deprecate-qlang-rename-cypher-to-query.md)), the gaps where fmql's Cypher subset *looks* like real Cypher but means something different become real footguns — especially for users coming from Neo4j who will reach for muscle memory and silently get the wrong behavior. Audit those divergences, decide on a direction (align, rename, or document), and ship the chosen fix.

Two known divergences that triggered this task:

1. **`+=` operator on `SET`.** fmql treats `SET t.field += value` as *list-append*. Real Cypher's `+=` is **map-merge** at node level (`SET n += {prop: value}` merges a property map into `n`); it does not exist at property level at all. Same token, different mental model.
2. **Function-name collisions.** fmql's `id(v)` is a shortcut for "resolve `v` and return its `id` frontmatter field." Real Cypher's `id(n)` returns the internal numeric node id. Anyone who knows Neo4j will read `id(t)` as "the engine's identifier for this packet," not "the `id` field of the resolved target." `path(v)` is similarly loaded — Cypher has the concept of `paths` (sequences of nodes/rels), and fmql repurposes the name for "resolve through the path resolver."

## Acceptance criteria

This task is a decision-then-execute task. The acceptance criteria are: pick a resolution per divergence, implement it, document it, ship tests.

### `+=` divergence

- [ ] Pick one resolution and execute it:
  - **(a) Keep current semantics, document loudly.** `+=` stays list-append. The README's `SET` operator table grows a "Differs from Neo4j" note linking to a divergences section. No code change beyond docs.
  - **(b) Rename fmql's list-append.** Introduce a distinct token (e.g. `APPEND` clause, `<<` operator, or a `SET t.field = t.field + value` idiom) and remove `+=` as the list-append spelling. Reserve `+=` either for nothing (parse error with a hint) or for future map-merge support.
  - **(c) Disambiguate by LHS shape.** `SET t += {map}` means map-merge on the packet's frontmatter map; `SET t.field += value` means list-append on a field. Most permissive, most surface area, most chances to surprise someone.
- [ ] Whichever option ships, the README's `SET` operator table makes the choice explicit and gives a one-line comparison to real Cypher.
- [ ] Tests cover the chosen semantics, including the case where the LHS field doesn't exist (does `+=` still initialize to `[value]`?) and where the RHS is itself list-valued.

### Function-name collisions

- [ ] Inventory fmql's built-in functions exposed inside `SET`/`WHERE`/`RETURN` expressions and classify each:
  - Collides with a real-Cypher function: `id()`, possibly `path()`.
  - fmql-specific, no collision: `resolve()`, `field()`, `slug()`, `uuid()`.
  - Future-collision risk: anything matching common Cypher built-ins (`type()`, `labels()`, `properties()`, `keys()`, `size()`, `length()`, `head()`, `last()`, `coalesce()`, `count()`).
- [ ] Pick one resolution and execute it:
  - **(a) Rename collisions.** `id()` → `field_id()` or drop the shortcut entirely (require `field(resolve(v, "id"), "id")`). `path()` → `resolve_path()` or similar. Breaking change; cheap because there's one user.
  - **(b) Keep names, document loudly.** Add a "Functions reference" subsection that lists each function and explicitly says "fmql's `id()` is not Neo4j's `id()`." Cheaper to ship, more long-tail confusion.
  - **(c) Namespace.** Move fmql-specific functions behind a prefix (`fmql.id()`, `fmql.resolve()`) and reserve the unprefixed names for Cypher-aligned semantics in the future. Most disruptive but cleanest separation.
- [ ] If renames ship, grep all docs (README, design.md, task notes) for the old names and update.
- [ ] Tests cover each renamed function and its behavior with `None` / list-valued first args (broadcast still works).

### General

- [ ] Add a "Cypher subset — divergences from Neo4j" section to the README. Even if both divergences above end up resolved, future ones will appear; have a place ready for them.
- [ ] `make format && make lint && make test` clean.

## Notes

### Recommendation

Without prejudging the eventual decision, the cheapest plausible path is:

- **`+=`**: option (a) — keep list-append, document the divergence. Map-merge has limited utility for frontmatter (you can already write `SET t.a = …, t.b = …`), so option (c) buys a feature nobody's asked for.
- **Function names**: option (a), specifically dropping the `id()`/`uuid()`/`slug()`/`path()` shortcuts and keeping the explicit `field(resolve(v, "<name>"), "<name>")` form. The shortcuts saved keystrokes but cost mental-model clarity, and `id()` in particular is the worst of both worlds — it looks like Cypher's id-of-node and means something else. Migration cost is one user.

But this is a judgment call worth re-litigating when the task is picked up — particularly whether the dogfood load on the function shortcuts is high enough that dropping them hurts daily use.

### Out of scope

- Adding clauses fmql doesn't have today (`CREATE`, `MERGE`, `DELETE`, `WITH`, `UNWIND`, `CALL`). Filesystem-level packet creation/deletion is its own scope — see [0012](0012-filesystem-level-operations.md).
- Aligning operator precedence with Neo4j's parser. fmql's grammar is LALR via lark; Neo4j's is hand-rolled. Bit-exact precedence parity is not a goal.
- Internal-id semantics. fmql packets don't have a stable engine-assigned numeric id the way Neo4j nodes do. If we ever introduce one, that's the moment to revisit `id()`.
