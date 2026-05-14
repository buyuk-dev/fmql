---
id: 0028
title: Filesystem-timestamp pseudo-fields `_created` / `_updated` in Cypher
status: todo
priority: 2
created: 2026-05-09
updated: 2026-05-09
tags: [cypher, query, frontmatter, filesystem, pseudo-fields]
depends_on: []
phase: cypher
---

## Goal

Frontmatter `created` and `updated` keys are unreliable as a recency signal: users forget to update them, third-party templates omit them entirely, and fmql's own tasks already store hand-edited values in those keys (so they don't reflect when the file was actually touched). Querying "documents modified in the last week" or `ORDER BY recency` therefore requires either frontmatter discipline the user may not have, or external tooling.

Add read-only pseudo-fields backed by the filesystem stat, mirroring the [0015](0015-cypher-pseudo-fields-id-path.md) `_id` / `_path` pattern:

- `a._created` — the file's creation time (ISO 8601 string).
- `a._updated` — the file's last-modification time (ISO 8601 string).

The `_` prefix keeps these distinct from any frontmatter `created` / `updated` keys the user has authored (which continue to take precedence under their bare names).

## Acceptance criteria

- [ ] `_created` and `_updated` are added to `PSEUDO_FIELDS` in `packages/fmql/src/fmql/cypher/expr.py`. The existing pseudo-field plumbing already carries them through `WHERE`, `RETURN`, `ORDER BY`, and the SET/REMOVE rejection path; no grammar changes required.
- [ ] `pseudo_field(pid, name)` resolves `_created` / `_updated` by `os.stat`-ing the workspace-relative path:
  - `_created` → `st_birthtime` if available (macOS, BSD, NTFS); fallback to `st_ctime` on Linux/other. Document the fallback caveat in the README.
  - `_updated` → `st_mtime`.
- [ ] Both values are returned as ISO 8601 UTC strings of the form `"2026-05-09T14:32:11Z"` (second precision; no fractional seconds). Lex-comparable, matches the frontmatter timestamp style used elsewhere in the project.
- [ ] Frontmatter `created` / `updated` keys are unaffected — `t.created` reads the YAML value as it does today, and `t._created` reads the filesystem value. The two are independent.
- [ ] Attempting to `SET` / `REMOVE` either pseudo-field produces the existing pseudo-write error (`cannot SET pseudo-field …: pseudo-fields are read-only`); pinned by a regression test.
- [ ] Works in every clause that takes a pseudo-field today:
  - `WHERE t._updated > "2026-05-01"`
  - `WHERE t._created >= "2026-01-01" AND t._created < "2026-02-01"`
  - `RETURN t._updated`
  - `ORDER BY t._updated DESC`
- [ ] Tests in `packages/fmql/tests/test_cypher_*.py` cover:
  - `WHERE t._updated > "<iso>"` filter against fixture files with controlled mtimes (use `os.utime` in the test setup to pin known values).
  - `ORDER BY t._updated DESC LIMIT 5` returns the expected order.
  - `RETURN t._created, t._updated` projects the ISO strings.
  - `SET t._created = "..."` and `REMOVE t._updated` both raise `cannot ... pseudo-field` with the existing error shape.
  - Independence: a packet with frontmatter `created: 2020-01-01` and a real-file mtime of 2026 reports `t.created = "2020-01-01"` and `t._created = "2026-..."` from the same query.
  - Missing file (packet present in workspace but file unlinked between load and query): pseudo-field evaluates to `None` rather than raising. Pin the behavior so it's a documented contract.
- [ ] README updates:
  - The Cypher pseudo-field section gains rows for `_created` and `_updated` with a one-line note that the source is `os.stat` (not git) and the fallback for `_created` on Linux.
  - One example query: "documents modified in the last week" using `_updated`.
- [ ] `make format && make lint && make test` clean.

## Notes

### Why filesystem stat, not git

Git history is the more truthful answer to "when was this file actually written" — it survives copies, syncs, IDE-driven `touch`es, and `cp -p` round-trips. But it's much more expensive (one `git log -1 --format=%cI <path>` per packet, or a single `git log` parse to build a path → timestamp map), it requires the workspace to be a git checkout, and it raises questions about uncommitted edits (do they count as "now" or as the last commit's time?).

Ship filesystem stat in v1 — cheap, no extra dependencies, works for non-git workspaces. Treat git-sourced timestamps as a separate task if usage demand appears; the natural shape would be a `--timestamp-source=git` flag (or workspace config) that swaps the resolver, with the pseudo-field names unchanged.

### Why ISO 8601 strings, not epoch numbers

Three reasons:

1. **Lex-compares correctly.** `"2026-05-09" < "2026-05-10"` is true with normal string comparison; no need to teach Cypher about datetimes to support `WHERE t._updated > "2026-05-01"`.
2. **Matches frontmatter convention.** The project already uses ISO date strings in frontmatter (`created: 2026-04-19`), so `t.created` and `t._created` print in the same shape. Less mental overhead.
3. **Readable in output.** `rows` / `json` formats display the value directly; epoch floats need post-processing to be human-meaningful.

The downside is that arithmetic on timestamps (e.g. "files modified in the last 7 days") requires a helper or a hard-coded threshold string. That's fine for v1; if it becomes a frequent pattern, a `now()` or `days_ago(7)` function is a natural follow-up.

### Why `_created` / `_updated`, not `_ctime` / `_mtime`

Two reasons:

1. **Symmetry with frontmatter.** Users who currently write `created:` / `updated:` in YAML reach for the same names with `_` prefix when they want the filesystem variant. No new vocabulary.
2. **`ctime` is misleading.** On Linux, `st_ctime` is the inode-change time (changes on `chmod`, ownership change, etc.), not the creation time. Calling the pseudo-field `_ctime` would imply the Unix semantics; `_created` makes the intent clear and lets the implementation pick the most-creation-like stat field available on each platform.

The asymmetry — `_created` is best-effort, `_updated` is reliable — is documented in the README so users know `_updated` is the safer signal for filtering and sorting.

### Implementation sketch

```python
# in packages/fmql/src/fmql/cypher/expr.py
import os
from datetime import datetime, timezone

PSEUDO_FIELDS: tuple[str, ...] = ("_id", "_path", "_created", "_updated")

def _fs_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def pseudo_field(workspace: Workspace, pid: PacketId, name: str) -> Any:
    if name in ("_id", "_path"):
        return pid
    if name in ("_created", "_updated"):
        abspath = workspace.abspath_for(pid)  # whatever the existing API is
        try:
            st = os.stat(abspath)
        except FileNotFoundError:
            return None
        if name == "_created":
            ts = getattr(st, "st_birthtime", st.st_ctime)
        else:
            ts = st.st_mtime
        return _fs_iso(ts)
    raise CypherError(f"not a pseudo-field: {name}")
```

Note: this changes `pseudo_field`'s signature to take the workspace (today it only takes `pid` and `name`). Update the one caller in `packet_field` accordingly. The shape is consistent with how `packet_field` already accepts a workspace.

### Watch-outs

- **Caching.** `os.stat` per evaluation is fine for typical workspace sizes, but for `ORDER BY t._updated` over a 10k-file workspace, the same packet's pseudo-field can be read multiple times during sort. If it shows up in profiling, memoize per-query in the `EvalCtx`.
- **Timezone.** Always emit UTC (`Z` suffix). Users comparing against `"2026-05-09"` (a date with no timezone) get a deterministic answer because the right-hand side lex-compares as a prefix.
- **Determinism in tests.** Filesystem timestamps from `git checkout` are non-deterministic across machines. Tests must explicitly `os.utime` fixture files to pin the mtimes they assert against.
- **Pseudo-field write rejection.** The existing `_reject_pseudo_write` path already covers any field in `PSEUDO_FIELDS`, so adding `_created` / `_updated` to the tuple inherits the rejection automatically. Pin with a regression test anyway — it's the kind of thing a future refactor could quietly break.
- **Frontmatter shadowing.** Pseudo-fields (`_`-prefixed) never shadow or get shadowed by frontmatter, by construction — the `_` prefix is reserved. Virtual fields (`path`, `filename`, `slug`) do get shadowed; pseudo-fields don't. Re-state this in the README so the distinction is clear.

### Out of scope

- **Git-sourced timestamps.** Separate task if demand appears; the design above leaves room for a `--timestamp-source=git` swap without renaming the pseudo-fields.
- **Datetime arithmetic / `now()` / `days_ago(N)`.** Useful for "modified in the last week" without hard-coding a threshold string, but a separate concern from exposing the raw filesystem values. Spec a follow-up if string-threshold queries turn out to be awkward in practice.
- **Sub-second precision.** Frontmatter conventions don't use it; filesystem stat varies by platform; not worth the complexity for v1.
- **A `_size` pseudo-field (or other stat-derived values).** Out of scope; this task is specifically about timestamps. If `_size`, `_ino`, etc. are wanted later, generalize through a `_stat.<field>` namespace or a separate task.
- **Exposing timestamps in `fmql describe`.** Worth doing eventually but tracked separately under [0007](0007-describe-on-resolver-mismatch.md)'s describe-output evolution.
