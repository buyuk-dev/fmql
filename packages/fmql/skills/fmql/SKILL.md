---
name: fmql
description: Use fmql whenever the user works with a directory of markdown or frontmatter files — notes, tasks, Zettelkasten, an Obsidian vault, a project-management packet collection, a knowledge base, a "digital garden" — and wants to query, aggregate, traverse, or bulk-edit YAML frontmatter fields. Reach for this instead of grep whenever the user's question involves structured fields (status, priority, tags, due_date, assignees, uuid, dependency links like blocked_by or belongs_to) or whenever a mutation needs to apply across many files at once. Also triggers on "find all docs where…", "set status on every overdue task", "describe this workspace", "what's blocking task-X", "cycle detection", "traverse blocked_by", "bulk-edit frontmatter", "query my notes". If the user mentions "frontmatter", "YAML header", "markdown metadata", or points at a directory of .md files, load this skill.
---

# fmql

fmql (FrontMatter utilities) is a schemaless query engine and editor for directories of markdown files with YAML frontmatter. Think of a folder of `.md` files as a document collection: fmql lets you query it like a database, traverse references between files like a graph, and edit YAML properties across the whole result set in one command — without any schema setup.

## When to reach for fmql (vs. grep or ad-hoc scripts)

Use fmql when any of the following apply:

- The user's filter involves **typed comparisons** on frontmatter fields (`priority > 2`, `due_date < today`, `status IN [...]`). grep only does substrings; fmql compares the parsed YAML value.
- The user wants to **edit the same field across many files** (e.g. "escalate every overdue active task"). fmql preserves comments, key order, and quoting; grep + sed does not.
- The user wants to **follow references between files** (`blocked_by`, `belongs_to`, `in_sprint`) — transitively, or to detect cycles.
- The user wants to **understand** an unfamiliar workspace (what fields exist, what types, what values).
- The user wants to **combine a search hit list with a structured filter** (e.g. "pages matching 'auth rewrite' that are also `status = in_progress`").

Use grep instead when the user just wants a literal substring match in body text and doesn't care about frontmatter structure. Use fmql's `search` subcommand (with `--backend grep` — the default) when you want grep semantics but also want the result to pipe into other fmql commands.

## Invocation

The CLI entry point is `fmql`. Install with `pip install fmql` (or `uv run fmql …` from inside the fmql source tree). Python 3.11+. No configuration, no init step — point it at any directory of `.md` files with YAML frontmatter and it works.

For programmatic use (when writing a script rather than running shell commands):

```python
from fmql import Workspace, Query

ws = Workspace("./project")
for packet in Query(ws).where(status="active", priority__gt=2):
    print(packet.id, packet.frontmatter)
```

A "packet" is fmql's word for a single frontmatter file. Each packet has an `id` (path relative to the workspace root), a `frontmatter` dict, and a `body` string.

## Command surface

Eleven commands, grouped by phase:

**Read:**
| Command | Purpose | Example |
|---|---|---|
| `query` | Filter a workspace with qlang | `fmql query ./proj 'status = "active" AND priority > 2'` |
| `describe` | Introspect a workspace (fields, types, samples) | `fmql describe ./proj --format json --top 10` |
| `cypher` | Graph pattern query (Cypher subset) | `fmql cypher ./proj 'MATCH (a)-[:blocked_by*]->(a) RETURN a'` |
| `search` | Run a search backend (default: grep) | `fmql search "alice" --backend grep --workspace ./proj -k 10` |

**Edit** (single file or bulk via stdin):
| Command | Purpose | Example |
|---|---|---|
| `set` | Set frontmatter fields | `fmql set ./task-42.md status=done priority=1` |
| `remove` | Delete frontmatter fields | `fmql remove ./task-42.md temp_notes` |
| `rename` | Rename fields | `fmql rename ./task-42.md assignee=assigned_to` |
| `append` | Append to a list-valued field | `fmql append ./task-42.md tags=urgent` |
| `toggle` | Flip a boolean field | `fmql toggle ./task-42.md flagged` |

**Index / discovery / utility:**
| Command | Purpose | Example |
|---|---|---|
| `index` | Build an index for an indexed search backend | `fmql index ./proj --backend semantic` |
| `list-backends` | Enumerate installed search backends | `fmql list-backends --format json` |
| `version` | Print fmql version | `fmql version` |

Run `fmql <command> --help` for the full flag list on any command.

## Filter DSL (qlang) cheatsheet

Case-insensitive keywords, SQL-ish, typed. The whole expression is a single shell argument, so wrap it in quotes.

**Logical operators:** `AND`, `OR`, `NOT`, parentheses.

**Comparisons:** `=`, `!=`, `<`, `<=`, `>`, `>=`.

**String / list / existence:**
- `CONTAINS "sub"` — substring in string field, or element in list field.
- `MATCHES "regex"` — regex against string.
- `IN ["a", "b", 3]` — membership.
- `IS EMPTY` / `IS NOT EMPTY` — field missing, null, or empty-sequence.
- `IS NULL` — field explicitly null.

**Values:** quoted strings (`"active"`), integers (`42`), floats (`3.14`), booleans (`true`/`false`), ISO dates (`2026-05-01`).

**Date sentinels:** `today`, `now`, `yesterday`, `tomorrow`, and arithmetic — `today-7d`, `now+1h`, `today+30d`.

**Examples:**

```bash
fmql query ./proj 'status = "active" AND priority > 2'
fmql query ./proj 'due_date < today AND status != "done"'
fmql query ./proj 'tags CONTAINS "urgent" OR priority >= 3'
fmql query ./proj 'status IN ["todo", "in_progress"]'
fmql query ./proj 'NOT (assigned_to IS EMPTY)'
fmql query ./proj 'title MATCHES "^\\[WIP\\]"'
```

**Type honesty — critical:** `priority > 2` only matches packets where `priority` is an int/float greater than 2. If one file has `priority: high` (string), it's silently excluded from the result — *not* coerced, *not* an error. This is intentional: mixed-type workspaces stay queryable without accidental conversions. If the user is confused about missing results, run `fmql describe` and look at the observed types per field.

**Use `'*'` as the query to match every packet** — handy when you want to start from "everything" and then `--follow`.

## Traversal (`--follow`)

Once you have a result set, you can walk references out of it:

```bash
# Direct dependencies of task-42
fmql query ./proj 'uuid = "task-42"' --follow blocked_by --depth 1

# Transitive dependency chain
fmql query ./proj 'uuid = "task-42"' --follow blocked_by --depth '*'

# What does task-42 unblock? (incoming edges)
fmql query ./proj 'uuid = "task-42"' --follow blocked_by --direction reverse
```

Pick a resolver with `--resolver`:
- `path` (default) — `blocked_by: ../tasks/task-41.md` resolves relative to the packet's file.
- `uuid` — `blocked_by: task-41` matches the packet whose frontmatter has `uuid: task-41`.
- `slug` — same idea but matching a `slug` field.

Unresolvable references are dropped silently. `--include-origin` keeps the starting packets in the output.

For anything beyond simple one-field walks (multi-hop patterns, multiple relationship types, cycle detection, WHERE clauses on both ends), use `cypher` instead.

## Cypher subset (graph patterns)

```
MATCH (a)-[:field]->(b)                   # single hop
MATCH (a)-[:field*]->(b)                  # transitive
MATCH (a)-[:field*1..5]->(b)              # bounded depth
MATCH (a)-[:blocked_by*]->(a)             # cycle detection
WHERE a.status = "active" AND b.priority > 2
RETURN a
RETURN a, b
RETURN a.title
RETURN count(a)
```

Node labels are parsed but ignored (fmql is schemaless). `WHERE` uses the same operators as qlang. Default output is TSV (`--format rows`); use `--format json` for structured parsing.

```bash
fmql cypher ./proj 'MATCH (a)-[:blocked_by*]->(a) RETURN a'
fmql cypher ./proj 'MATCH (a)-[:belongs_to]->(e) WHERE e.type = "epic" RETURN a, e'
```

## Workspace introspection — always start here

When you're handed an unfamiliar workspace, run `describe` first. It tells you which fields actually exist, what types they take, and a sample of distinct values. Writing qlang by guessing field names leads to empty results you'll blame on a bug; `describe` removes the guesswork:

```bash
fmql describe ./proj --format json --top 10
```

JSON output gives you `{field, types, sample_values, count}` per field — easy to scan, easy to parse.

## Bulk edits — the read→edit pipeline

The idiomatic mutation pattern is `query | edit`:

```bash
# Preview
fmql query ./proj 'due_date < today AND status != "done"' \
  | fmql set status=escalated --workspace ./proj --dry-run

# Apply after inspecting the diff
fmql query ./proj 'due_date < today AND status != "done"' \
  | fmql set status=escalated --workspace ./proj --yes
```

Why `--workspace` is required when piping: stdin carries packet paths, and the edit command needs the workspace root to resolve them.

**Safety model.** Edits are format-preserving — `ruamel.yaml` round-trips the file, so comments, key order, quoting, and body bytes on untouched keys survive intact. But the files still get rewritten. Two guardrails:
- `--dry-run` shows a unified diff without writing. **Use this first on any result set you can't eyeball manually.**
- Without `--yes`, bulk edits print the diff and wait for confirmation at `/dev/tty`. In a CI/non-TTY environment, pass `--yes` or the edit will hang.

**Value coercion.** CLI strings are auto-coerced: `status=done` → string, `priority=1` → int, `flagged=true` → bool, `due_date=2026-05-01` → date, `cleared=null` → None. To force a literal string that looks like another type, quote inside the value: `label='"123"'`.

**Choose the right edit verb:**
- `set` — any field, any type, overwrite existing.
- `remove` — delete keys entirely (different from `set x=null`).
- `rename` — change the key name, preserve the value.
- `append` — push onto a list; creates the list if missing.
- `toggle` — flip a boolean.

## Search backends

`fmql search` and `fmql query --search` run pluggable search backends. The default is `grep` (literal substring match, zero setup). Check what's available:

```bash
fmql list-backends           # human-readable
fmql list-backends --format json
```

You can combine search with a structured filter in one pipeline:

```bash
fmql query ./proj 'status = "in_progress"' --search "auth rewrite" --index grep
```

For meaning-based / hybrid retrieval over a notes vault, the separate `fmql-semantic` package registers a `semantic` backend — load the fmql-semantic skill when the user wants semantic search, RAG, embeddings, or hybrid BM25+dense retrieval.

## Output formats for agent parsing

- `--format paths` (default for `query`, `search`) — one packet id per line. Pipes cleanly into `fmql set`, `fmql remove`, etc.
- `--format json` — one JSON object per line (NDJSON-ish). `query` emits `{id, frontmatter}`; `search` emits `{id, score, snippet}`; `describe` emits one object describing the whole workspace.
- `--format rows` — TSV. Default for `cypher`, available on `search`.

When you need to parse results, prefer JSON over paths: paths lose the field values, forcing a second query to recover them.

## Example workflows

**1. First look at an unfamiliar workspace**

```bash
fmql describe ./vault --format json --top 10
```

Read the output, identify the interesting fields, then narrow down with `query`.

**2. Bulk escalate stale work**

```bash
fmql query ./proj 'status IN ["todo","in_progress"] AND due_date < today' \
  | fmql set status=escalated --workspace ./proj --dry-run
# inspect the diff, then:
fmql query ./proj 'status IN ["todo","in_progress"] AND due_date < today' \
  | fmql set status=escalated --workspace ./proj --yes
```

**3. "What's blocking task-42?"**

```bash
fmql query ./proj 'uuid = "task-42"' \
  --follow blocked_by --depth '*' --resolver uuid --format json
```

**4. Find dependency cycles**

```bash
fmql cypher ./proj 'MATCH (a)-[:blocked_by*]->(a) RETURN a'
```

**5. Count completed tasks per sprint**

```python
from fmql import Workspace, Query, Count

ws = Workspace("./proj")
(
    Query(ws)
    .where(type="task", status="done")
    .group_by("in_sprint")
    .aggregate(count=Count())
)
```

## Gotchas

- **No TTY → must pass `--yes`.** Piping into an edit in CI or a sandboxed shell with no `/dev/tty` will hang at the confirmation prompt.
- **Regex backslashes in shells.** `MATCHES "^\\[WIP\\]"` — the double backslash is needed so the shell passes a single backslash through to the regex engine.
- **`IN` list literals use JSON syntax:** `IN ["a", "b"]`, commas separate, strings quoted.
- **Malformed frontmatter is silently skipped.** If `describe` reports fewer packets than you expect, a file's YAML probably doesn't parse. Open it manually.
- **`query` default format is `paths`, not JSON.** If you pipe it into `jq`, you'll get nothing — pass `--format json`.
- **Reserved-looking field names are fine.** fmql has no schema; `type`, `status`, `id` are just keys. (Note: fmql uses the file path as the packet `id`, independent of any `id` field inside the frontmatter.)
- **Python API uses `field__op=value`** (Django-style) — `priority__gt=2`, `tags__contains="urgent"`, `assigned_to__not_empty=True`.

## Quick reference — Python operators

When writing a Python script instead of shell commands:

| Operator suffix | Meaning |
|---|---|
| (none) / `eq` | equals |
| `ne` / `not` | present and not equal |
| `gt`, `gte`, `lt`, `lte` | typed ordering |
| `in`, `not_in` | list membership |
| `contains`, `icontains` | substring (string field) or element (list field); `i` = case-insensitive |
| `startswith`, `endswith` | string prefix/suffix |
| `matches` | regex |
| `exists` | field is present |
| `not_empty` | present and non-empty |
| `is_null` | value is explicitly `None` |
| `type` | type-name match (`"int"`, `"str"`, `"list"`, `"date"`, …) |

`Query(ws).where(...)` is lazy — iterate it, call `.group_by().aggregate(...)`, chain `.follow(...)`, or call `.set(...).dry_run() / .apply()` for edits.

---

If the user's question isn't really about frontmatter-structured data — e.g. they just want to grep through some source files — don't force fmql into it. This skill is for the cases where treating the directory as a queryable collection pays off.
