---
id: 0008
title: Cypher subset diverges from Neo4j on `+=` semantics and function shortcuts
status: accepted
date: 2026-05-02
context_task: 0022
---

## Context

Task [0021](../tasks/0021-deprecate-qlang-rename-cypher-to-query.md) made Cypher fmql's only query language. With qlang gone, every place where fmql's Cypher subset *looks* like real Cypher but means something different becomes a Neo4j-user footgun. Task [0022](../tasks/0022-cypher-compatibility-divergences.md) flagged two such gaps:

1. **`SET t.field += value` is list-append in fmql; Neo4j's `+=` is map-merge at node level.** Same token, different mental model. Worse, Neo4j's `+=` is undefined at property level — it only takes a map RHS against a node.
2. **Function-name collisions.** fmql exposes a function registry inside `SET`/`WHERE`/`RETURN` expressions. `id(v)` returns the resolved packet's `id` field; Cypher's `id(n)` returns the engine's numeric node id. `path(v)` resolves a value through the path resolver; Cypher's `path` is a node/relationship sequence type. `slug(v)` and `uuid(v)` follow the same shortcut shape and run the same future-collision risk should those names land in standard Cypher.

The task itself notes that this is a judgment call — the dogfood load on the four shortcuts is small (one user, the maintainer) but real, and `+=` map-merge has limited utility for frontmatter (`SET t.a = …, t.b = …` already covers it).

## Decision

### `+=` keeps list-append semantics; the divergence is documented loudly

- `SET t.field += expr` continues to mean "append `expr` to the list-valued field, initializing to `[expr]` when the field is absent."
- Neo4j-style map-merge (`SET n += {map}`) is **not** implemented. The grammar already rejects `var += expr` (LHS must be `var.field`), so there is no syntactic surface for map-merge. No grammar or executor change.
- The README's `SET` operator table grows a "Differs from Neo4j" note that names the mismatch explicitly. A new "Cypher subset — divergences from Neo4j" subsection in the README links here.
- Tests pin three behaviors: missing-field initializes to `[expr]`; list-valued RHS is appended as a single nested element (it does **not** extend); non-list LHS reports an error.

### The `id()` / `uuid()` / `slug()` / `path()` shortcuts are removed

- All four are dropped from `fmql.cypher.expr.REGISTRY`. Users compose explicitly: `field(resolve(v, "<name>"), "<name>")` for the first three, `resolve(v, "path")` for the last.
- Calling any of the four removed names raises `CypherError("function <name>() was removed; use <hint> instead")`. The hint names the explicit composition. Both the eval-time path (`eval_value_expr`) and the SET-validation path (`_check_value_expr_vars`) share the same error builder so the message surfaces consistently.
- `resolve()` and `field()` remain — they are the primitives the four shortcuts decomposed into, are unambiguously fmql-specific, and have no Neo4j collision.

## Rationale

### Why keep `+=` as list-append

- **Map-merge is low utility for frontmatter.** Frontmatter maps are already mutable through `SET t.a = …, t.b = …`. There is no analogue to a Neo4j node's "merge a property bag in one shot" use case that warrants a second `+=` overload.
- **Disambiguating by LHS shape (option (c) in the task)** would make the grammar accept `SET t += {map}` *and* `SET t.field += value`. Most permissive, most surface area, most chances to surprise someone — and it would commit the codebase to a feature nobody has asked for.
- **Renaming list-append (option (b))** — using a new token like `<<` or an `APPEND` clause — buys nothing today and forces the maintainer to relearn a working idiom. The cost is real for zero compatibility win.

### Why drop all four shortcuts, not just the colliders

- **`id()` is the worst-of-both-worlds case.** A reader who knows Neo4j parses `id(t)` as "the engine's identifier for this packet," not "the resolved target's `id` field." Keeping it as-is (option (b) in the task) preserves the exact misreading that motivated the task.
- **Consistency over partial cleanup.** Dropping only `id()` and `path()` (the direct colliders) leaves `slug()` and `uuid()` as a fmql-specific dialect that future Cypher releases could collide with. Removing all four collapses the function registry to two unambiguous primitives (`resolve`, `field`) and forecloses the future-collision class entirely.
- **Migration cost is negligible.** One user, the maintainer; the explicit form (`field(resolve(v, "id"), "id")`) is what `slug(v)` was sugar for, so the rewrite is mechanical.
- **The error message bridges the cliff.** Each removed name dispatches to a `CypherError` that names the explicit composition. The migration story for an unsuspecting paste from older notes is "run the query, read the error, copy the suggested form."

### Why a single ADR

The two decisions share context (Cypher compatibility), share a release window (this task), and share the README divergences subsection. Splitting them into separate ADRs (`0008` for `+=`, `0009` for functions) would force the README to link two files where one suffices and would scatter the rationale.

## Consequences

- **Breaking change for query strings using the four shortcuts.** All of `id(v)`, `uuid(v)`, `slug(v)`, `path(v)` now raise. The error includes the explicit composition; mechanical fixup. The maintainer's local scripts and notes were grepped during this task.
- **`+=` semantics are now part of fmql's stable surface.** The "list-valued RHS appends as one nested element" behavior is locked in by `test_append_with_list_valued_rhs_nests`. Changing it later would itself be a breaking change.
- **The README has a permanent home for divergences.** The new subsection is the canonical place to document any future construct where fmql's syntax matches Cypher's but the meaning differs. Each future divergence appends a row.
- **Function registry stays minimal.** `resolve` and `field` are both well-typed (each rejects bad arities and bad arg types with a clear message). The shortcut layer was sugar; removing it shrinks the surface area future maintainers have to reason about.

## Alternatives considered

- **`+=` option (b): rename list-append; reserve `+=` for future map-merge.** Rejected — see Rationale. Costs a working idiom for an unrequested feature.
- **`+=` option (c): disambiguate by LHS shape.** Rejected — biggest surface area, most ergonomics decisions to make (what does map-merge mean when keys overlap?), no demand pull.
- **Functions option (b): keep names, document loudly.** Rejected — the task's whole motivation is that `id(t)` looks identical to Cypher's id-of-node, so docs would have to outshout muscle memory. They will not.
- **Functions option (c): namespace under `fmql.` prefix.** Considered briefly. Cleanest separation but the most invasive change (every call site, every test, every doc example), and it commits to the idea that the unprefixed names will eventually mean something else — currently speculative. Revisit if fmql ever adds Cypher-aligned semantics for `id()`, `count()`, etc. in the unprefixed namespace.
- **Functions: drop only the direct colliders (`id`, `path`).** Plausible mid-point. Rejected for the consistency reason above: leaving `slug()` and `uuid()` keeps the shortcut pattern alive and the future-collision class open. Single-user migration cost does not justify partial cleanup.
- **Two ADRs.** Considered for narrow scoping. Rejected — see Rationale on shared context.
