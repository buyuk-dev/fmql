---
id: 0030
title: `--path-format` flag for `fmql query` (workspace | relative | absolute)
status: todo
priority: 2
created: 2026-05-14
updated: 2026-05-14
tags: [cli, query, paths, ergonomics]
depends_on: []
phase: cli
---

## Goal

`fmql query` emits packet ids — workspace-relative POSIX paths — in `paths` and `json` output. That's the right default when you're staying inside fmql, but it breaks shell pipelines that want to feed the output to another tool:

```
$ fmql query -w docs/tasks 'MATCH (m) WHERE m.status="todo" RETURN m' | xargs cat
cat: 0028-cypher-pseudo-fields-created-updated.md: No such file or directory
```

…because cwd is the repo root, not `docs/tasks/`. Today's workarounds (running from inside the workspace dir, or `sed 's|^|docs/tasks/|'`) are awkward enough that users reach for them every time they script around fmql.

Add a `--path-format` flag on `fmql query` that controls how packet paths are rendered:

- `workspace` — workspace-relative (current behavior; default).
- `relative` — relative to the process cwd.
- `absolute` — absolute filesystem path.

## Acceptance criteria

- [ ] `fmql query` accepts `--path-format {workspace,relative,absolute}` (default `workspace`). Implemented as a `typer.Option` with an `Enum`, mirroring `--format`.
- [ ] Affects every place the CLI prints a packet path:
  - `--format paths`: each output line is rendered in the requested format.
  - `--format json`: the `id` field of each row payload is rendered in the requested format. (The packet is still keyed by its workspace id internally; only the emitted string changes.)
  - `--format rows`: rows that project a packet variable (single-var RETURN with default cell formatting via `_format_cell`) render the path in the requested format. Rows that project scalar fields are unaffected.
- [ ] Path rendering uses `Packet.abspath` as the source of truth:
  - `workspace`: emit `p.id` unchanged (POSIX, forward slashes).
  - `absolute`: emit `str(p.abspath)`.
  - `relative`: emit `os.path.relpath(p.abspath, Path.cwd())`. Forward slashes on POSIX; native separator on Windows is acceptable (matches `os.path.relpath` convention).
- [ ] Combines correctly with `--follow` and `--search` (the `_emit_packets` path), not just the direct compile path.
- [ ] `--path-format relative` works when cwd is *outside* the workspace root (produces a `../`-prefixed path); pin with a test.
- [ ] Tests in `packages/fmql/tests/test_cli_query.py` (or equivalent) cover:
  - Each of the three values against a fixture workspace, in `paths` format.
  - `json` format: parsing the emitted line and asserting `payload["id"]` shape.
  - `--follow` + `--path-format absolute`.
  - cwd outside the workspace root, with `relative`.
  - Default (no flag) is identical to today's output — pin so we don't silently regress.
- [ ] README / `fmql query --help` documents the flag with one shell-pipeline example (`fmql query ... --path-format relative | xargs cat`).
- [ ] `make format && make lint && make test` clean.

## Notes

### Scope: query only, for now

`fmql subgraph` also emits node ids, and `fmql describe` surfaces paths in its stats output. Both could benefit from the same flag, but they have different output shapes (subgraph: structured JSON/DOT; describe: human-readable summary) and the conversion points are different. Keep this task focused on `query` — the place users actually script against — and spec subgraph/describe symmetry as a follow-up if it comes up.

### Why a flag, not an env var or config key

Path rendering is a per-invocation concern: the same workspace gets queried from different cwds and piped to different tools in the same session. A flag is the right granularity. A workspace config default (`paths.format: relative`) might make sense later but adds surface area we don't need yet.

### Why `workspace` stays the default

Two reasons:

1. **Backwards compatibility.** Existing scripts and the test suite assume workspace-relative output.
2. **Stable identity.** A packet's workspace id is its identity within fmql — it doesn't change when you `cd` somewhere else or move the workspace. `relative` and `absolute` are presentation, not identity. Defaulting to identity keeps "what you see is what's stored."

### Why include `absolute` as well as `relative`

`relative` covers the common shell case. `absolute` covers two others: (a) feeding the path to a tool invoked with a different cwd (e.g. an editor launched from a script that `cd`s elsewhere), and (b) producing output that's safe to copy-paste into logs or issue trackers without ambiguity. Both have come up in practice; cost of supporting both is one extra enum branch.

### Implementation sketch

```python
# in packages/fmql/src/fmql/cli/cmd_query.py

class PathFormat(str, Enum):
    workspace = "workspace"
    relative = "relative"
    absolute = "absolute"


def _render_path(packet: Packet, fmt: PathFormat) -> str:
    if fmt is PathFormat.workspace:
        return packet.id
    if fmt is PathFormat.absolute:
        return str(packet.abspath)
    return os.path.relpath(packet.abspath, Path.cwd())
```

Plumb `path_format: PathFormat = PathFormat.workspace` into `query_cmd`. Two changes downstream:

1. The direct `--format paths` branch currently emits `row[0]` (a `PacketId`). Resolve through `ws.packets.get(pid)` to get the packet, then `_render_path(packet, path_format)`. (One dict lookup per row; same cost as the `json` branch already pays.)
2. `_emit_packets` already has a `Packet`; thread `path_format` in and use `_render_path` directly.

For `--format rows`, the cell formatter (`_format_cell`) doesn't know it's looking at a packet path vs. an arbitrary scalar. Detect the single-var-return case (already computed as `single_var`) and substitute the rendered path for that one column before joining. Don't touch multi-column rows or scalar projections.

### Watch-outs

- **Symlinks.** `Packet.abspath` is whatever the workspace scan resolved (`p.resolve().relative_to(self.root)` — see `workspace.py:55`). If the workspace root contains symlinks, `abspath` is the resolved target; `relative` and `absolute` reflect that. Document this in passing in the help text; users who need the unresolved path should stick with `workspace`.
- **Windows.** `os.path.relpath` emits backslashes on Windows. Acceptable — Windows users piping to Windows tools expect that. Don't normalize unless a real complaint surfaces.
- **Empty result, exit code.** The flag must not change exit codes or stderr behavior; only the formatting of emitted paths.
- **`json` output stability.** The `id` field becomes user-controlled in shape. Consumers that key off `id` to round-trip back into fmql should keep using `--path-format workspace` (the default). Call this out in the help text.

### Out of scope

- **`fmql subgraph` / `fmql describe`.** Spec separately if needed; scopes and output shapes differ.
- **Workspace-config default for path format.** Possible follow-up; flag alone covers the scripting case.
- **Renaming or repathing on `SET`.** This task is read/output only; it doesn't change how `SET`/`REMOVE` resolve targets.
- **A `--path-base <dir>` option** (render relative to an arbitrary base, not just cwd). Niche; revisit if asked.
