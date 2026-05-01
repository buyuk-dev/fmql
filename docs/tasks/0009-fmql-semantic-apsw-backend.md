---
id: 0009
title: fmql-semantic — switch to apsw to drop the loadable-extension sqlite3 install requirement
status: todo
priority: 2
created: 2026-04-29
updated: 2026-04-29
tags: [fmql-semantic, install, sqlite, packaging]
depends_on: []
phase: later
---

## Goal

`fmql-semantic` currently requires the host Python to be built with loadable-extension sqlite3 support, which excludes most macOS system Pythons and many Linux distro builds. The `pysqlite3-binary` workaround (ChromaDB's solution) does not solve this on macOS — there are no macOS wheels for it — which rules out the `sys.modules` swap approach. Switch to **apsw**, which ships pre-built wheels for macOS (x86_64 + arm64), Linux, and Windows, and always supports `enable_load_extension()` regardless of the host Python's build flags.

## Acceptance criteria

- [ ] Add a thin compatibility shim in `fmql-semantic` exposing the subset of the `sqlite3` API the project actually uses (cursors, exception types, parameter binding) so the rest of the code doesn't fork on backend.
- [ ] Swap the backend import to apsw via the shim. All existing tests pass against the new backend.
- [ ] Add a smoke test that exercises `enable_load_extension()` against a vector extension — the failure mode this whole change exists to fix.
- [ ] `pip install fmql-semantic` succeeds on a vanilla macOS system Python (no Homebrew/pyenv requirement) and on a stripped-down Linux Python build.
- [ ] README / install docs drop the "Python build must support loadable-extension sqlite3" caveat.
- [ ] `make format && make lint && make test` clean across the workspace.

## Notes

The compatibility shim is the load-bearing part: apsw's API isn't drop-in (cursor lifecycle, exception hierarchy, and parameter binding all differ from stdlib `sqlite3`). Keep the shim narrow — only what fmql-semantic uses today — to minimize maintenance surface.
