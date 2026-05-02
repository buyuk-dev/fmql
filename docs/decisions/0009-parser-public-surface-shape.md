---
id: 0009
title: Parser public surface — alias `serialize_packet` to `serialize`, default `pid` from path
status: accepted
date: 2026-05-02
context_task: 0023
---

## Context

Task [0023](../tasks/0023-expose-parser-api-at-top-level.md) promotes the frontmatter parser primitives in `packages/fmql/src/fmql/parser.py` from "internal" to "public API." The mechanics are nearly trivial — three lines in `__init__.py` — but the *shape* of the public surface forces three small judgment calls that will be hard to undo later (renaming a public function in a published package is a breaking change). This ADR captures those three calls so future readers do not have to reverse-engineer them from the diff.

The three questions:

1. The internal symbol is `serialize_packet`. The acceptance criteria call for a shorter top-level name `serialize`. Do we rename the underlying function, alias it, or expose both?
2. The internal signatures require `pid` (and `abspath` on `parse`) as keyword-only args. Standalone parser users have no workspace and no natural source of a `pid`. Which arguments become optional, and what do they default to?
3. Should `serialize_packet` itself appear in `fmql.__all__`, or only the alias?

## Decision

### 1. `serialize_packet` keeps its name; the top level exposes a `serialize` alias

In `packages/fmql/src/fmql/__init__.py`:

```python
from fmql.parser import serialize_packet as serialize
```

`fmql.parser.serialize_packet` continues to exist with its original name and signature. `fmql.serialize` is `serialize_packet` under a shorter name.

### 2. `pid` defaults to the path; `abspath` stays required on `parse`

- `parse_file(path, *, pid=None)` — `pid` defaults to `path.as_posix()`.
- `parse(text, *, abspath, pid=None)` — `pid` defaults to `abspath.as_posix()`. `abspath` stays a required keyword-only arg.

### 3. Only the `serialize` alias is in `fmql.__all__`, not `serialize_packet`

`fmql.__all__` lists `parse`, `parse_file`, `serialize`. `serialize_packet` is reachable via `fmql.parser.serialize_packet` but is not part of the top-level public surface.

## Rationale

### Why alias instead of rename

- **Internal callers stay quiet.** `Packet.serialize()` (`packet.py:30`), `edits.py:182`, and `tests/test_parser_serialize.py:7` already import `serialize_packet`. A rename would touch every one of them and would force any out-of-tree consumer pinning to `fmql.parser.serialize_packet` to update on upgrade. An alias is purely additive.
- **Coordinates with task [0024](../tasks/0024-rename-packet-type.md).** That task is expected to rename `Packet` → `Document`, which would mechanically rename `serialize_packet` → `serialize_document` if the function name tracks the type. The top-level `serialize` alias is type-agnostic and survives that rename without churn — exactly the sidestep the task notes call out.
- **Two names is the lesser evil.** Yes, `fmql.serialize is fmql.parser.serialize_packet` is a little odd. But the alternative — having one name that means two things across the rename — is worse. The alias is a one-line indirection in `__init__.py`; nobody has to remember it once the README shows the canonical form.

### Why `pid` becomes optional but `abspath` stays required

- **`pid` has a free-and-obvious default.** When you have a `Path`, you have a workspace-relative-ish string for free (`.as_posix()`). The default is unambiguous and matches what `Workspace._scan` would synthesize for the same file (modulo the workspace-root prefix, which a standalone user does not care about).
- **The standalone use case the task targets is `parse_file(Path("note.md"))`.** That call works with no keyword args at all under this default. Forcing the user to pass `pid="note.md"` for what is obviously the right value is the friction the task exists to remove.
- **`abspath` has no defensible synthetic default.** `Packet.abspath: Path` is non-optional, and the dataclass shape is out of scope for this task (that is task 0024 territory). Synthesizing a `Path("<string>")` placeholder would either lie about a real filesystem location or require a sentinel that downstream code (e.g. `Workspace`) would have to pattern-match on. The standalone "I have a string in memory" case is rare enough — if it shows up, the user can pass any `Path` they want; the field is informational for parser-only flows.
- **Keyword-only keeps it forgiving.** Because both args are after `*`, swapping the declaration order (`abspath` now precedes `pid` in the signature) is invisible at every existing call site. Only the defaults change.
- **Internal callers already pass `pid` explicitly.** `workspace.py:57` and `edits.py:270` pass workspace-relative ids; the new default is ignored there. So this is purely additive for engine code.

### Why `serialize_packet` is not in `fmql.__all__`

- **One name per concept at the top level.** Both `serialize` and `serialize_packet` in `fmql.__all__` would invite confusion ("which one am I supposed to use?") and would lock in *both* names as public surface — doubling the breaking-change cost of any future rename.
- **The internal name is not hidden, just not promoted.** `from fmql.parser import serialize_packet` keeps working; existing imports do not break. The top level is the front door, the module is the side door.
- **`__all__` is a recommendation to readers and to `from fmql import *`.** Putting only the canonical name there points users at the right spelling without preventing anyone from reaching the older one.

## Consequences

- **`fmql.serialize` and `fmql.parser.serialize_packet` are the same function object.** `fmql.serialize is fmql.parser.serialize_packet` is `True`. The smoke test in `test_public_api.py` pins this — if a future refactor breaks the alias, the test fails before users notice.
- **Default `pid` values are now part of the stable surface.** If someone relies on `parse_file(p).id == p.as_posix()`, changing the default later (e.g. to `p.name` or to a UUID) is a breaking change. Documented in the docstrings of both entry points.
- **`abspath`-less parsing remains an open design question.** If a "give me a packet from a string with no path at all" use case shows up, this ADR does not preclude adding `abspath: Optional[Path] = None` later — it just defers the question. A follow-up ADR would have to decide what `Packet.abspath` carries in that case.
- **Task 0024 inherits a clean rename path.** When `Packet` becomes `Document`, the top-level alias absorbs the churn: `fmql.serialize` keeps its name; `fmql.parser.serialize_packet` would be renamed to `serialize_document` (or kept as a deprecated re-export, depending on how 0024 lands).

## Alternatives considered

- **Rename `serialize_packet` → `serialize` in `parser.py` directly.** Rejected. Forces three internal call sites to change and is a hard breaking change for any out-of-tree consumer importing from `fmql.parser`. Coordinated less well with task 0024 — that rename would push us to `serialize_document`, undoing the rename we just did.
- **Expose both `serialize` and `serialize_packet` in `fmql.__all__`.** Rejected. Two names for one concept at the front door; locks both into the public surface.
- **Keep `pid` required everywhere.** Rejected. The standalone use case the task exists to enable is `parse_file(Path("note.md"))` with zero ceremony. Requiring `pid="note.md"` is exactly the redundancy the task calls out.
- **Make `abspath` optional with a synthetic default like `Path("<memory>")`.** Considered. Rejected because (a) the task does not request it, (b) the synthetic value would either appear in user-facing error messages or require sentinel-aware code paths, and (c) the question is better answered by a follow-up ADR if the use case actually materializes.
- **Default `pid` to `path.name` instead of `path.as_posix()`.** Considered. `path.name` is shorter (`note.md`) but loses directory info, which is the differentiator when two files share a basename. `as_posix()` matches what `Workspace._scan` produces for the workspace-rooted view and is the more informative default.
