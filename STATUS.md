---
session_id: a8c83712-8a5d-442c-a205-77eec2e847b5
task_id: 23
branch: feature/expose-parser-api-at-top-level
phase: done
started: '2026-05-02T12:02:00Z'
---
# Status

Task **0023 — Expose the frontmatter parser API at the top level of the `fmql` package** finalized.

Branch: `feature/expose-parser-api-at-top-level`. Plan: `~/.claude/plans/get-started-on-task-humming-blossom.md`.

## Outcome

- **`packages/fmql/src/fmql/parser.py`**: made `pid` optional on both public entry points and added the docstrings the task called out as missing. `parse(text, *, abspath, pid=None)` and `parse_file(path, *, pid=None)` now default `pid` to `abspath.as_posix()` / `path.as_posix()` when omitted, so the standalone use case is `parse_file(Path("note.md"))` with zero ceremony. `abspath` stays required on `parse(text)` — `Packet.abspath: Path` is non-optional and synthesizing fake paths is task 0024 territory. The defaulting rule lives in one place: `parse` resolves it; `parse_file` just forwards `pid=pid`.
- **`packages/fmql/src/fmql/__init__.py`**: re-exported `parse`, `parse_file`, and `serialize` (alias for `serialize_packet`) and added all three to `__all__`. `fmql.parser.serialize_packet` stays importable for existing callers (`edits.py:182`, `tests/test_parser_serialize.py:7`); only the shorter alias gets promoted to the front door.
- **`Packet.serialize()`** (`packet.py:27`) untouched — its local import of `serialize_packet` keeps working.
- **README.md**: new "Use fmql as a frontmatter parser" subsection between the Python quickstart and `## Features`. Three-line example (open file, mutate `frontmatter`, write back) plus a one-line note about lossless round-tripping. Targets the half of the audience that just wants a `python-frontmatter` replacement.
- **Tests** (`packages/fmql/tests/test_public_api.py`, new): 8 cases pinning the public surface — `__all__` membership, `serialize is fmql.parser.serialize_packet` alias identity, `pid` defaults on both entry points, explicit-`pid` overrides, byte-exact round-trip via the alias on a real fixture, and a parse-mutate-serialize standalone flow.
- **ADR** (`docs/decisions/0009-parser-public-surface-shape.md`): captures the three judgment calls — alias vs rename for `serialize_packet`, why `pid` defaults from the path while `abspath` stays required, and why only the alias appears in `__all__`. Rationale, consequences, and alternatives considered (including the deferred "abspath-less parsing" case).
- **Workflow housekeeping**: archived prior STATUS body to `docs/changelog/0007.md`; flipped task 0023 to `done`; updated `docs/roadmap.md`.

## Verification

- `make format` — reformatted one file (`tests/test_public_api.py`); rerun clean.
- `make lint` — failed once on `I001` (ruff wanted the aliased `serialize_packet as serialize` import on its own line, not chained with `parse, parse_file`); split the import line and re-ran clean.
- `make test` — `fmql` 548 passed (was 540; +8 from the new `test_public_api.py`), `fmql-semantic` 56 passed.

## Notes

- **`pid` default is now part of the stable surface.** `parse_file(p).id == p.as_posix()` and `parse(t, abspath=p).id == p.as_posix()` are pinned by tests. Changing the default later (e.g. to `p.name`) would be a breaking change; the docstrings name the rule explicitly.
- **Single source of truth for the defaulting rule.** Initial draft duplicated the `pid if pid is not None else …` expression in both `parse` and `parse_file`. The simplify pass collapsed it: `parse_file` now passes `pid=pid` straight through, `parse` is the only place the fallback lives.
- **Ruff vs the consolidated import.** Tried `from fmql.parser import parse, parse_file, serialize_packet as serialize` to keep the re-export concise; ruff's `I001` rejects mixing aliased and non-aliased names in one statement and won't auto-fix to a form that satisfies both. The two-line split is the canonical form here.
- **Coordinates with task [0024](docs/tasks/0024-rename-packet-type.md).** When `Packet` becomes `Document`, the top-level `serialize` alias absorbs the rename: `fmql.serialize` keeps its name, and `serialize_packet` would either become `serialize_document` or be kept as a deprecated re-export. The alias is the sidestep the task notes called out.
