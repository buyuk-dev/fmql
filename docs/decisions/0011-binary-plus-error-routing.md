---
id: 0011
title: Binary `+` type-mismatch errors route per-packet via a `kind="error"` EditOp
status: accepted
date: 2026-05-03
context_task: 0026
---

## Context

Task [0026](../tasks/0026-cypher-binary-plus-list-concat.md) adds binary `+` to fmql's Cypher subset. The acceptance criteria pin the user-visible error shape:

> Any other type combination (e.g. `string + number`, `bool + anything`) → per-packet error, reported the same way `+=` against a non-list field is reported.

The `+=` reference is `test_append_to_non_list_field_errors` in `test_cypher_set.py:169`: a packet whose field is a non-list scalar produces a `(packet_id, message)` entry in `ApplyReport.errors` while other packets in the result set apply normally.

The implementation question is *where* the type check happens and *how* the error reaches `ApplyReport.errors`. The two pathways already in the codebase point in different directions:

- **`+=` errors at apply time.** The append op evaluates the RHS during `_build_edit_plan` (`executor.py:312`), produces a value, and queues a `kind="append"` EditOp. The check (`isinstance(current, (list, CommentedSeq))`) happens inside `_apply_op` (`edits.py:97-111`), and the function returns an error string when the LHS isn't a list. That string flows through `_apply_ops_to_map` → `FileChange.error` → `ApplyReport.errors` (`edits.py:262-265`).
- **`NOT non-bool` errors at eval time.** `_negate` raises `CypherError` (`expr.py:206-208`) inside `eval_value_expr`, which propagates out of `_build_edit_plan` and aborts the entire compile. There is no per-binding catch.

Neither matches what `+` needs:

- Apply-time checking is the wrong layer — by the time `_apply_op` runs, the value is just data; reconstructing "this came from a `string + number` mistake" would require sentinel objects flowing through eval.
- Eval-time raising aborts the compile, which is the *compile-time abort* shape (used today for SET conflicts, undeclared vars, unknown functions). It's the wrong shape for `+` because the user expectation is per-packet partial success.

## Decision

A two-piece mechanism that keeps eval-raises-on-error as the natural primitive but routes binop-specific errors through the existing apply-time error pipeline:

1. **`expr.BinaryOpError(CypherError)`** — a narrow exception subclass raised only by `_eval_add` for type-mismatch cases.
2. **A per-binding `try / except BinaryOpError` in `_build_edit_plan`** (`executor.py:312`). On catch, the error is recorded in a `binop_errors: dict[PacketId, str]` keyed by the binding's pid; the binding's set/append bookkeeping is skipped.
3. **A new `kind="error"` arm in `_apply_op`** (`edits.py:65-66`) that returns the recorded message verbatim. The op is emitted *first* in the per-pid op sequence, so `_apply_ops_to_map`'s "stop on first error" loop short-circuits any other ops queued for that pid — the file gets a no-op write with `FileChange.error` set.

The result is that `report.errors` ends up with `(pid, "cannot add int and str")` exactly as if `+=` had hit a non-list field, while other packets' ops apply normally.

## Rationale

### Why a narrow exception subclass and not `CypherError`

Catching plain `CypherError` per binding would silently change the behavior of *every* eval-time raise — `_negate` non-bool, `field()` arity errors, `resolve()` unknown-resolver, unknown-function dispatch — from compile-time abort to per-packet error. Those error classes today are programming-shape errors (the user wrote a query that's wrong everywhere) and producing a per-packet error per binding for them would just turn one mistake into N spammy report entries. `BinaryOpError` is the precise scope: only the type-mismatch in `_eval_add`, where per-packet partial success is the correct shape because different packets really can have different field types.

### Why `kind="error"` and not a side-channel on `EditPlan`

`EditPlan` is already an opaque container of `EditOp`s; threading errors through it would mean adding a `compile_errors` field, plus duplicating the `_apply_ops_to_map` short-circuit logic to consult the side channel before running ops. The `kind="error"` arm reuses the existing `_apply_op` → `FileChange.error` → `ApplyReport.errors` plumbing without modification. The cost is one extra entry in the `OpKind` Literal — a one-line type extension — and one extra arm in `_apply_op` (two lines). No other site in the codebase needs to know the kind exists; the dispatch is local to `_apply_op`.

### Why error op first, not last

`_apply_ops_to_map` runs ops in order and returns the first error string (`edits.py:135-138`). Putting the error op first means subsequent ops on the same file are silently skipped at apply time, which is the right semantics — if one of three SET items errored, the user wanted all-or-nothing-per-packet, not partial-per-packet. Symmetric with how `+=` non-list errors work today: when `_apply_op` hits the append-to-non-list arm and returns an error, any further queued ops on that file aren't reached either.

The op-assembly loop also `continue`s after emitting the error op, so non-error ops aren't even queued for an errored pid. This makes the plan structure honest about what won't happen — `EditPlan.summary()` reports "1 changed, 1 skipped (error), 0 no-op" rather than "0 changed, 1 skipped (error), 1 no-op-because-short-circuited."

### Why first-error-wins per pid

A pid can have multiple bindings (different MATCH paths land on it) and multiple SET items per binding. We could collect all errors and join them; we could keep only the first; we could keep only the last. First-wins (`binop_errors.setdefault(pid, str(e))`) is the simplest stable choice and matches how `_apply_ops_to_map` itself returns only the first error from a sequence of ops on a file. If multiple bindings produce different error messages for the same pid, the user sees one of them with no ordering guarantee beyond "deterministic for a given input" (binding enumeration is `sorted(workspace.packets)`, so iteration order is stable).

## Consequences

- **`BinaryOpError` is part of fmql's internal stable surface, not the public API.** It's imported by `executor.py` from `expr.py` for the per-binding catch. Tests assert on the public `ApplyReport.errors` message, not the exception class — the error string is what users (and downstream code) actually see.
- **`OpKind` gains `"error"`.** Any future EditOp consumer (today: only `_apply_op`, `EditPlan.compile`, `EditPlan.preview_*`, `EditPlan.summary`, `EditPlan.has_changes`) needs to handle the new kind. Most of them already operate via `FileChange.error`, which the new arm sets correctly through the existing plumbing — no other call sites change.
- **`+=` non-list errors and `+` type-mismatch errors now share the `ApplyReport.errors` channel and message style** (`"cannot append to non-list field …"` vs. `"cannot add <type> and <type>"`). Same shape, different prefixes — easy to tell apart, both surface the same way in CLI output and in tests.
- **The mechanism generalizes.** If a future binop (or any eval-time per-packet error class) needs the same routing, adding a sibling exception class (`BinaryOpError`, `FutureBinopError`) and extending the catch tuple is the entire change. The `kind="error"` arm already accepts any message string.

## Alternatives considered

- **Apply-time check via sentinel return value.** Have `_eval_add` return a `_BinopError("msg")` sentinel object instead of raising. `_apply_op` for `kind="set"` and `kind="append"` then detects the sentinel before assigning and returns the message. **Rejected**: forces every consumer of `eval_value_expr`'s return value to know about the sentinel — including `list_lit` items, `func_call` arguments, and `list_comp` projection, where the sentinel would otherwise be silently nested into a list or passed to `field()`. Too many sites need to learn the protocol.
- **Generic `CypherError` catch in `_build_edit_plan`.** **Rejected** — see Rationale. Changes behavior of unrelated eval-time errors that are correctly compile-time aborts today.
- **New `compile_errors: dict[PacketId, str]` field on `EditPlan`.** **Rejected** for duplicating logic — the existing `FileChange.error` channel already does this exact job; threading a parallel one means modifying `apply()`, `preview_errors()`, `summary()`, and `has_changes()` to consult both. Higher surface area for the same outcome.
- **Drop per-packet semantics; raise compile-time on first binop type error.** **Rejected** as a regression in user experience — a heterogeneous workspace where most packets have well-typed fields would have one bad packet poison the whole `fmql update` invocation. The same data shape works fine for `+=` non-list, so `+` matching it is the consistent choice.
- **Aggregate all errors per pid into one message.** **Rejected** as over-engineered for the single-user, single-task driver. First-error-wins is what `_apply_ops_to_map` already does; matching it is principle-of-least-surprise.
