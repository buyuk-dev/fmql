## fmql design takeaways

A few things actually bit us, in rough priority:

#### [done] **1. Resolvers bind to field *names* implicitly; no type awareness.**
`depends_on: [1, 8, 17]` went through *every* resolver without matching and the output was silently empty edges. The `subgraph` hint saved us, but `query --follow` might not have. Two directions worth considering:
- Ship a built-in `id` resolver (match against the `id` frontmatter field) — this is the most common case for roadmap/ADR/ticket corpora and the one YAML's leading-zero coercion makes hardest to hand-roll.
- Per-field resolver binding, declared in frontmatter or a workspace config (`depends_on: slug`, `supersedes: path`). "One resolver per workspace" breaks as soon as you have two reference-shaped fields with different target spaces.
- At minimum: when a declared edge field contains only ints and no resolver matches, promote the hint from `subgraph` to a `stderr` warning on *every* command that touches edges.


#### [done] **2. `fmql set` can't write lists.**
YAML frontmatter is list- and dict-native; the edit surface is scalar-only. That forced a `remove` + N×`append` loop wrapped in a Python script for what is conceptually one update. Options:
- `--json` flag: `fmql set … 'depends_on:=["a","b"]'` (borrowing httpie's `:=` for "parse as JSON").
- Accept a YAML literal when the value starts with `[` or `{`.
- Either way, `coerce_value` should at least refuse to stringify list-shaped input — right now `depends_on=["foo","bar"]` silently becomes the string `'["foo","bar"]'`, which is worse than erroring.

#### [done] **3. Bulk migrations have no first-class story.**
`fmql cypher` already gives you a pattern-matching read path; the symmetric edit path is missing. Something like `fmql update docs/tasks 'MATCH (t) SET t.depends_on = resolve_slug(t.depends_on)'` or even a simpler per-packet rewrite with a small expression language would have collapsed today's migration to one line. The current shape pushes every non-trivial change into external scripts, and external scripts then recapitulate fmql's own parsing/IO.

#### [done] **4. Workspace/target ergonomics are inconsistent.**
- `-w <file>` crashes with a `FileNotFoundError` Python traceback; `-w <dir> <abspath-outside-dir>` gives a clean `error: path not inside workspace`. Same conceptual failure, two different error modes.
- Edit commands require `cwd` inside the workspace or relative paths passed as plain filenames. Query commands happily take `docs/tasks` from repo root. The divergence is surprising.
- Suggestion: if `-w` points at a file, treat it as workspace=parent, target=file. And normalize absolute paths into workspace-relative when they're underneath.

Resolved by collapsing all CLI commands onto a single `--workspace/-w` flag (default cwd), removing the legacy `set/append/remove/rename/toggle` family, and routing all edits through `fmql update 'MATCH … [WHERE …] [SET …] [REMOVE …]'`. Cypher SET grew the missing operators (`+=`, `REMOVE` clause, unary `NOT`, list comprehensions) plus virtual properties (`t.path`, `t.filename`, `t.slug`) so filtering by file identity works in MATCH/WHERE/SET/RETURN. `-w <file>` now errors cleanly; `-w <missing>` errors cleanly; `-w` omitted means cwd.

#### **5. Output format labels are ambiguous.** 
`--format json` on `query` emits NDJSON; on `subgraph` it emits a single JSON object. The flag label doesn't distinguish; `jq` users will write `jq -s` by habit after getting burned once. Either rename (`jsonl` / `json-array`) or document explicitly.

#### **6. Mental-model mismatch shows up in docs.** 
The project's own `docs/README.md` (before today) had SQL-flavored examples — `SELECT … FROM … WHERE …` — which aren't valid qlang. That's authored by a human who knew fmql but reached for SQL anyway. Worth taking seriously: qlang/cypher are fine, but if SQL is what people type first, a compatibility/translation layer or a very visible "this is NOT SQL, here's the cheatsheet" box in the docs would prevent the same drift in other users' repos.

#### **7. `describe` is under-advertised.**
Would have told us up front that `depends_on` is `list[int]` across 17 files — which is exactly the "why don't my edges resolve?" smoking gun. Consider running `describe` implicitly on resolver mismatch and including the output in the hint.

Highest-weight for the backlog: **#1** (resolver design), **#2** (list-valued set), **#3** (no bulk-update path) — those were the real friction; the rest are papercuts.


