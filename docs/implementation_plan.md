# fmq — Implementation Plan

> **Note:** This plan was written under the working name `fmq`. The project is now published as **`fmql`** (module, CLI, and PyPI distribution). The body below is preserved as frozen planning history; treat every `fmq` reference as the present-day `fmql`.

## Context

The repo at [/Users/michal/Projects/wandaos/fmq](/Users/michal/Projects/wandaos/fmq) is empty except for [design_doc.md](/Users/michal/Projects/wandaos/fmq/design_doc.md), which specifies **`fmq` (FrontMatter Utilities)**: a Python package + CLI that treats a directory of markdown/YAML frontmatter files as a queryable, editable, schemaless database — with filters, traversal, aggregation, graph patterns, pluggable search, and bulk edits that preserve formatting.

Nothing is built yet. This plan turns the design doc into a concrete, milestoned build with the following user-confirmed constraints locked in:

- **Full design doc surface** (filters, follow, cypher subset, aggregation, pluggable search, describe, single-file + bulk edits).
- **YAML library:** `ruamel.yaml` (round-trip; preserves comments/order/quoting — required for surgical edits).
- **CLI framework:** Typer.
- **Packaging:** `uv` + hatchling, `pyproject.toml`.
- **Reference resolution in `follow()`:** user-configurable; default is relative path.
- **Indexing:** in-memory scan per `Workspace()` init; no persistent cache.
- **CLI pipe format:** newline-delimited paths by default; `--format json` for JSONL.

Additional design-doc constraints: truly schemaless, type-honest filter semantics (no coercion; non-comparable values silently excluded), Django-style `field__op=value` kwargs, bulk edits require preview + confirmation with `--dry-run` / `--yes`, MIT licensed, pure Python, minimal required deps, optional `fmq[semantic]` / `fmq[sqlite]` extras.

---

## 0. Current execution target — Phase A (Read path)

This section is the concrete deliverable for the current iteration. Phases B–E remain specified below for context but are **out of scope** until Phase A ships and is demo-verified.

**Phase A ships:** `uv run fmq query ./project 'status = "active" AND priority > 2'` against any directory of frontmatter files, with typed comparisons and JSON output, and a Python-level `Workspace` / `Query` API covering the same surface.

### Phase A file-by-file deliverables

| file | contents |
|---|---|
| [pyproject.toml](pyproject.toml) | hatchling build backend, `requires-python = ">=3.11"`, deps: `ruamel.yaml>=0.18`, `typer>=0.12`, `lark>=1.1`; `[project.scripts] fmq = "fmq.cli.main:app"`; `[project.optional-dependencies] dev = ["pytest", "pytest-cov"]` |
| [.python-version](.python-version), [.gitignore](.gitignore), [LICENSE](LICENSE), [README.md](README.md) | standard scaffold; MIT; README = short "quickstart" lifted from design doc |
| [src/fmq/__init__.py](src/fmq/__init__.py) | re-exports: `Workspace`, `Query`, `Packet`, `today`, `now`, `__version__` |
| [src/fmq/errors.py](src/fmq/errors.py) | `FmqError`, `ParseError`, `QueryError`, `FilterError` |
| [src/fmq/types.py](src/fmq/types.py) | `PacketId = str`; `Resolver` / `SearchIndex` Protocols (stubs ok — only `PacketId` used in A) |
| [src/fmq/parser.py](src/fmq/parser.py) | `parse(text: str, *, abspath: Path) -> Packet` — detect `---\n` fence, split frontmatter / body, load with shared `YAML(typ="rt", pure=True)` instance. Captures `eol`, `newline_at_eof`, `fence_style`, `has_frontmatter`. Files without a fence → `has_frontmatter=False`, empty `CommentedMap`, whole file in `body` |
| [src/fmq/packet.py](src/fmq/packet.py) | `Packet` dataclass (per §2) + `as_plain() -> dict` helper that walks `CommentedMap` / `CommentedSeq` to plain Python for comparisons |
| [src/fmq/workspace.py](src/fmq/workspace.py) | `Workspace(root, *, glob=("**/*.md",))`: resolves root, walks glob, parses each file into `Packet`, stores in `packets: dict[PacketId, Packet]`. PacketId = workspace-relative POSIX path. Skip files that raise `ParseError` with a warning (don't abort scan). No resolvers/indexes in A — attributes exist, empty |
| [src/fmq/filters.py](src/fmq/filters.py) | kwarg parser (`field__op=value` → `(field, op, value)`); operator registry `{op_name: (accepts_fn, match_fn)}`; **Phase A operator set** = `eq`, `ne`/`not`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`, `icontains`, `startswith`, `endswith`, `matches`, `exists`, `not_empty`, `is_null`, `type`. Non-comparable values drop silently. Nested field access deferred (no `foo.bar` in A) |
| [src/fmq/dates.py](src/fmq/dates.py) | `today()`, `now()`, parse `today-7d` / `now+1h` strings; resolved at query-compile time; `--utc` flag later, default local tz |
| [src/fmq/query.py](src/fmq/query.py) | `Query(workspace)`; immutable builder: `where(**kwargs)`, `all()`, `__iter__`, `ids()`. Internal `_stages: list[Stage]`; `FilterStage` only in A. Executor seeds `set(workspace.packets)`, applies filters, returns `Packet` objects in stable ID-sorted order |
| [src/fmq/qlang/grammar.lark](src/fmq/qlang/grammar.lark), [src/fmq/qlang/compile.py](src/fmq/qlang/compile.py) | lark grammar per §6 (filter-only subset: AND/OR/NOT/parens, `= != > >= < <= CONTAINS MATCHES`, `IN [...]`, `IS EMPTY/NOT EMPTY/NULL`, bare identifiers for date sentinels). Compiler walks tree → chained `Query.where(**kwargs)` for flat ANDs; OR/NOT compile to an internal `where_expr(ast)` that evaluates the tree per-packet |
| [src/fmq/cli/__init__.py](src/fmq/cli/__init__.py), [src/fmq/cli/main.py](src/fmq/cli/main.py) | Typer `app`; registers `query` command; `version` command returns `fmq.__version__` |
| [src/fmq/cli/cmd_query.py](src/fmq/cli/cmd_query.py) | `fmq query <path> <query-string> [--format paths\|json]`. Loads workspace, compiles qlang, iterates results, prints PacketId per line (paths) or JSONL `{"id": ..., "frontmatter": {...}}` (json) |

### Phase A tests (`tests/`)

- [tests/conftest.py](tests/conftest.py) — `tmp_workspace(factory)` fixture materializing a dict spec (path → frontmatter dict + optional body) into tmp dir.
- [tests/fixtures/project_pm/](tests/fixtures/project_pm/) — committed sample workspace mirroring the design doc PM use case (tasks/epics/sprints with `status`, `priority`, `due_date`, `in_sprint`, `blocked_by`, `uuid`).
- [tests/test_parser.py](tests/test_parser.py) — round-trip preservation; no-frontmatter files; CRLF; BOM; empty frontmatter block.
- [tests/test_workspace.py](tests/test_workspace.py) — scan correctness; PacketId canonicalization (POSIX, relative); bad YAML skipped with warning.
- [tests/test_filters.py](tests/test_filters.py) — operator matrix, including type-honest exclusion (string `priority` vs `priority__gt=2`).
- [tests/test_query.py](tests/test_query.py) — `where` chaining, `all()`, iteration order, `ids()`.
- [tests/test_dates.py](tests/test_dates.py) — `today`, `today-7d`, `now+1h` resolution.
- [tests/test_qlang.py](tests/test_qlang.py) — every qlang form compiles and returns the same IDs as the equivalent Python `Query`.
- [tests/cli/test_query_cmd.py](tests/cli/test_query_cmd.py) — Typer `CliRunner`: paths format, json format, quoting, exit codes.

### Phase A verification

```bash
uv sync
uv run pytest -q
uv run fmq --help
uv run fmq query tests/fixtures/project_pm 'status = "active" AND priority > 2'
uv run fmq query tests/fixtures/project_pm 'due_date < today' --format json
uv run fmq query tests/fixtures/project_pm '*' --format paths | wc -l
```

### Phase A explicit non-goals

These stay deferred to later phases and **will not ship in A**, even if tempting:
- No edits (`set`/`remove`/`rename`/`append`/`toggle`) — Phase B.
- No `follow()` / traversal / resolvers / reverse direction — Phase C.
- No aggregation / `group_by` / `describe` — Phase D.
- No Cypher, no pluggable search (not even `TextScanIndex`), no `contrib` extras — Phase E.
- No stdin piping on the `query` command side (emit only).
- No nested field access (`foo.bar`), no `len`/`len_gt`/`len_lt`, no `istartswith`/`iendswith` — add with Phase B if needed, otherwise Phase D.

---

## 1. Repo / package layout

```
fmq/
├── pyproject.toml                  # uv + hatchling, deps, extras
├── README.md
├── LICENSE                         # MIT
├── design_doc.md                   # existing
├── CHANGELOG.md
├── .gitignore
├── .python-version
├── src/fmq/
│   ├── __init__.py                 # public API: Workspace, Query, File, Packet
│   ├── errors.py                   # FmqError hierarchy
│   ├── types.py                    # PacketId, Resolver/SearchIndex Protocols
│   ├── parser.py                   # frontmatter split + ruamel round-trip
│   ├── packet.py                   # Packet dataclass
│   ├── workspace.py                # scan, packet index, resolver/search registries
│   ├── query.py                    # lazy pipeline, result materialization
│   ├── filters.py                  # Django-style kwarg parsing + operator registry
│   ├── traversal.py                # follow(): depth, direction, cycles
│   ├── aggregation.py              # group_by + Count/Sum/Avg/Min/Max
│   ├── cypher/                     # lark grammar + executor (Phase E)
│   ├── edits.py                    # set/remove/rename/append/toggle + EditPlan
│   ├── search.py                   # SearchIndex Protocol + TextScanIndex fallback
│   ├── describe.py                 # workspace introspection
│   ├── resolvers.py                # RelativePathResolver (default), Uuid, Slug
│   ├── dates.py                    # today/now/relative offsets for filter values
│   ├── qlang/                      # lark grammar + compiler for CLI string queries
│   └── cli/                        # Typer app: query, set, remove, rename, append,
│                                   #   toggle, describe, cypher, version
├── tests/
│   ├── conftest.py                 # synthetic workspace factory fixtures
│   ├── fixtures/                   # project_pm, mixed_types, refs_by_path/uuid, cycles
│   ├── test_parser.py, test_packet.py, test_workspace.py,
│   ├── test_filters.py, test_query.py, test_traversal.py,
│   ├── test_aggregation.py, test_cypher.py,
│   ├── test_edits_roundtrip.py     # diff-based format-preservation golden tests
│   ├── test_describe.py, test_qlang.py, test_search.py, test_dates.py,
│   ├── cli/                        # per-command CLI tests + pipe tests
│   └── integration/test_end_to_end.py
└── docs/                           # quickstart, query_language, cypher_subset, extending_search
```

---

## 2. Core data model

```python
# types.py
PacketId = str  # workspace-relative POSIX path, canonical

class Resolver(Protocol):
    def resolve(self, raw: Any, *, origin: PacketId, workspace: "Workspace") -> Optional[PacketId]: ...

class SearchIndex(Protocol):
    name: str
    def search(self, query: str) -> Iterable[PacketId]: ...
```

```python
# packet.py
@dataclass
class Packet:
    id: PacketId                  # e.g. "tasks/task-42.md"
    abspath: Path
    frontmatter: CommentedMap     # ruamel round-trip object (NOT a dict)
    body: str                     # post-frontmatter text, byte-preserved
    raw_prefix: str               # pre-frontmatter (BOM/shebang — rare)
    fence_style: tuple[str, str]  # ("---", "---"); reject "+++" (TOML) initially
    eol: str                      # "\n" vs "\r\n"
    newline_at_eof: bool
    has_frontmatter: bool
```

**Invariant:** edits never round-trip through a plain `dict`. Reads flow through `as_plain()` for comparisons; writes mutate the `CommentedMap` in place and re-serialize with the same `YAML(typ="rt", pure=True)` instance that loaded it — this is what preserves keys, order, comments, quoting, flow vs block style.

```python
# workspace.py
class Workspace:
    root: Path
    glob: tuple[str, ...]              # default ("**/*.md",)
    packets: dict[PacketId, Packet]
    _by_field_value: dict[str, dict[Any, set[PacketId]]]  # lazy per-field
    resolvers: dict[str, Resolver]     # per-field override
    default_resolver: Resolver          # RelativePathResolver()
    search_indexes: dict[str, SearchIndex]
```

---

## 3. Query pipeline

Lazy. Each builder method returns a new `Query` with an appended `Stage`. Execution starts at a terminal (iteration, `ids()`, aggregation, or an edit sink).

```python
class Query:
    def where(self, **kwargs) -> "Query"
    def follow(self, field, *, depth=1, direction="forward", resolver=None) -> "Query"
    def search(self, query, *, index="text") -> "Query"
    def cypher(self, text: str) -> "Query"
    def group_by(self, field) -> "GroupedQuery"
    def all(self) -> "Query"
    def __iter__(self) -> Iterator[Packet]        # materialization
    def ids(self) -> list[PacketId]
    # terminal edit sinks
    def set(self, **kwargs) -> "EditPlan"
    def remove(self, *fields) -> "EditPlan"
    def rename(self, **mapping) -> "EditPlan"
    def append(self, **kwargs) -> "EditPlan"
    def toggle(self, field) -> "EditPlan"
```

Executor seeds `set[PacketId] = set(ws.packets)`, then each stage narrows / expands / transforms. Aggregation is terminal and emits grouped rows. Edit sinks consume the final packet set via `edits.plan(...)`.

---

## 4. Filter DSL

`field__op=value` kwargs parsed in `filters.py`. Default op is `eq`.

**v1 operators:**

| op | semantics |
|---|---|
| `eq` (default), `ne` / `not` | strict equality, YAML-native types, no coercion |
| `gt`, `gte`, `lt`, `lte` | numeric + datetime; **silently excludes non-comparable** |
| `in`, `not_in` | membership |
| `contains`, `icontains` | list elem or substring / case-insensitive |
| `startswith`, `endswith`, `istartswith`, `iendswith` | strings |
| `matches` | regex (strings) |
| `exists` | field present |
| `not_empty` | not `None`, `""`, `[]`, `{}` |
| `is_null` | present and `None` |
| `len`, `len_gt`, `len_lt` | collection length |
| `type` | YAML-native type: `int`, `float`, `str`, `bool`, `date`, `datetime`, `list`, `map`, `null` |

**Type-honest rule (centralized):** each op has an `accepts(value) -> bool` guard; failing values drop the packet from the result — never raise.

Date sentinels resolved via `dates.py`: `today`, `now`, `yesterday`, `tomorrow`, relative offsets (`today-7d`, `now+1h`). Passed as `fmq.today()` in Python, bare identifiers in qlang.

---

## 5. Edit module

All mutation via the same `ruamel.yaml.YAML(typ="rt", pure=True)` instance that loaded each packet. Per-packet ops:

- `set(field, value)` — new keys append at bottom, preserving existing comments.
- `remove(field)` — no-op if absent.
- `rename(old, new)` — preserve position by walking `ca` (comment attachments).
- `append(field, value)` — list-only; creates list if absent; refuse on type conflict (no `--force` in v1).
- `toggle(field)` — bool-only; refuse non-bool (no `--cast` in v1).

Splice model: load → mutate `CommentedMap` → dump YAML → splice back between original fences + untouched body + EOL style.

```python
@dataclass
class EditOp:
    packet_id: PacketId
    kind: Literal["set", "remove", "rename", "append", "toggle"]
    args: dict

class EditPlan:
    ops: list[EditOp]
    def preview(self) -> str         # unified-diff per file
    def dry_run(self) -> str         # == preview
    def apply(self, *, confirm: bool = True) -> ApplyReport
```

`apply(confirm=True)` prints preview and reads yes/no from stdin; `--yes` / `confirm=False` skips. `--dry-run` calls `preview()` and returns.

**Edge cases to test:** empty frontmatter block, file with no frontmatter (set creates one), trailing whitespace / CRLF / missing EOF newline, anchors & aliases, merge keys `<<:` (preserve on dump; read-only in v1 — document), flow-style sequences (`tags: [a, b]` — appending preserves flow), unicode, quote-style preservation for numeric-looking strings.

---

## 6. CLI design

Typer command tree:

```
fmq
├── query <path> <query> [--follow FIELD] [--depth N] [--direction forward|reverse]
│                       [--search Q] [--index NAME] [--format paths|json]
├── set     <target...> key=value...
├── remove  <target...> <field>...
├── rename  <target...> old=new...
├── append  <target...> key=value
├── toggle  <target...> <field>
├── describe <path>
├── cypher   <path> <query-string>
└── version
```

`<target>` accepts filesystem paths or `-` (read packet ids from stdin). Common flags: `--dry-run`, `--yes`, `--format {paths,json}`.

**Stdin auto-detect** (`cli/stdin.py`): line starting with `{` → JSONL; otherwise paths.

**String query grammar:** **lark** (pure Python, good error messages; reused for Cypher). Hand-rolled buys nothing once we're already shipping lark for cypher.

```
query       : or_expr | "*"
or_expr     : and_expr ("OR" and_expr)*
and_expr    : not_expr ("AND" not_expr)*
not_expr    : "NOT"? atom
atom        : "(" or_expr ")" | predicate
predicate   : IDENT OP value
            | IDENT "IN" "[" value ("," value)* "]"
            | IDENT "IS" ("EMPTY" | "NOT" "EMPTY" | "NULL")
OP          : "=" | "!=" | ">" | ">=" | "<" | "<=" | "CONTAINS" | "MATCHES"
value       : STRING | NUMBER | BOOL | DATE | IDENT   # IDENT covers today/now
```

Compilation: flat AND → direct `where()` kwargs; OR / NOT → internal `Query.where_expr(tree)`.

**Workspace resolution for piped edits:** receiving command uses `--workspace`, else first positional, else longest common parent of piped paths.

---

## 7. Reference resolution

```python
# resolvers.py
class RelativePathResolver:       # default
    def resolve(self, raw, *, origin, workspace):
        if not isinstance(raw, str): return None
        candidate = (workspace.root / Path(origin).parent / raw).resolve()
        try:   pid = candidate.relative_to(workspace.root).as_posix()
        except ValueError: return None
        return pid if pid in workspace.packets else None

class UuidResolver:               # indexes ws.packets by frontmatter["uuid"]
class SlugResolver:               # indexes by frontmatter["slug"] or filename stem
```

Workspace registers per-field:

```python
Workspace("./p", resolvers={"blocked_by": UuidResolver(), "belongs_to": SlugResolver()})
```

`follow(field, resolver=...)` accepts a per-call override. List-typed field values yield multiple edges (each resolved independently).

**Cycles:** BFS with visited-set keyed by `PacketId`. `depth="*"` unbounded with visited cutoff. `direction="reverse"` lazily builds full reverse adjacency on first use (flagged as a future perf item).

---

## 8. Cypher subset

**Lark grammar + hand-rolled executor.** In-memory graph size (thousands of packets) makes embedding a real Cypher engine overkill.

**Supported in v1:**

- `MATCH (a)-[:field]->(b)` single hop
- `MATCH (a)-[:field*]->(b)` variable-length, optional bounds `*1..5`
- `MATCH (a)-[:field*]->(a)` self-cycle (cycle detection)
- Chains: `(a)-[:f1]->(b)-[:f2]->(c)`
- `WHERE a.status = "active" AND a.priority > 2` — reuses filter operators
- `RETURN a`, `RETURN a, b`, `RETURN a.field`, `RETURN count(a)`
- Node labels `(a:Task)` parse but are ignored (schemaless).

**Not supported** (raise `CypherUnsupported`): `CREATE`, `MERGE`, `DELETE`, `SET`, `OPTIONAL MATCH`, `WITH`, `UNWIND`, multi-pattern MATCH, `shortestPath`, aggregations beyond `count()`.

Relationship walks reuse the same resolver machinery as `follow()`.

---

## 9. Search protocol

```python
class SearchIndex(Protocol):
    name: str
    def search(self, query: str) -> Iterable[PacketId]: ...

class TextScanIndex:   # default fallback, zero deps
    name = "text"
    def __init__(self, ws): self.ws = ws
    def search(self, query):
        q = query.lower()
        for pid, p in self.ws.packets.items():
            if q in p.body.lower() or q in serialize_for_scan(p.frontmatter).lower():
                yield pid
```

`fmq[semantic]` (sentence-transformers + vector store) and `fmq[sqlite]` (FTS5) live in `fmq.contrib.*`, added in Phase E. Core stays dep-free for search.

---

## 10. Testing strategy

`pytest` + `pytest-cov`. Fixtures in `tests/conftest.py`:

- `tmp_workspace(factory)` — materialize synthetic workspace from dict spec
- `project_pm_ws` — canonical tasks/epics/sprints (mirrors design doc examples)
- `mixed_types_ws` — heterogeneous `priority` field for type-honest tests
- `refs_by_path_ws`, `refs_by_uuid_ws`, `cycles_ws` — traversal

**First-pass coverage (in implementation order):**

1. Parser byte-round-trip on unmodified files.
2. ruamel format preservation under each edit op (diff-based goldens).
3. Filter operator matrix incl. type-honest exclusion.
4. `where` chaining, `all()`.
5. `follow()` depth / direction / cycles.
6. Aggregation (count/sum/avg) on heterogeneous fields.
7. `describe` output against `mixed_types_ws`.
8. qlang compile → same results as Python Query.
9. CLI: `query` both formats, `query | set` round-trip, `--dry-run`, `--yes`.
10. Cypher: single hop, variable-length, cycle detection.

---

## 11. Milestones

Each phase ends tagged + demo-able.

### Phase A — Read path — **shipped**
`pyproject.toml`, repo skeleton, `parser.py`, `packet.py`, `workspace.py` (scan), `filters.py` (core ops), `query.py` (`where`/`all`/iterate/`ids`), `dates.py`, `qlang` (filter-only), `cli.query`, tests. **Ships:** `fmq query ./project 'status = "active" AND priority > 2'`.

### Phase B — Edit path — **shipped**
`edits.py` (all ops + `EditPlan`), CLI edit commands + stdin + `--dry-run` / `--yes` / confirmation, golden round-trip tests. **Ships:** single-file edits + `fmq query ... | fmq set ...`.

### Phase C — Relationships & traversal - **shipped**
`resolvers.py` (path/uuid/slug), `traversal.py` (`follow()`), `Filter → Follow → EditSink` composition, CLI `--follow` / `--depth` / `--direction`. **Ships:** "tag dependency chain" use case.

### Phase D — Aggregation & describe - **shipped**
`aggregation.py`, `describe.py`, CLI `describe` + aggregation formatter. **Ships:** sprint progress / what's slipping reports.

### Phase E — Cypher & pluggable search
`cypher/` grammar + executor, `search.py` protocol + `TextScanIndex`, `contrib/` extras (`semantic`, `sqlite`), CLI `cypher` + `--search` / `--index`. **Ships:** full design-doc surface.

---

## 12. Critical files

Highest-leverage (everything else is glue):

- [pyproject.toml](pyproject.toml)
- [src/fmq/parser.py](src/fmq/parser.py)
- [src/fmq/workspace.py](src/fmq/workspace.py)
- [src/fmq/query.py](src/fmq/query.py)
- [src/fmq/filters.py](src/fmq/filters.py)
- [src/fmq/edits.py](src/fmq/edits.py)
- [src/fmq/cli/main.py](src/fmq/cli/main.py)

---

## 13. Verification plan

Commit a sample workspace at `tests/fixtures/project_pm/`. Per phase:

**After A:**
```
uv run fmq query tests/fixtures/project_pm 'status = "active" AND priority > 2'
uv run fmq query tests/fixtures/project_pm 'due_date < today' --format json
```

**After B:**
```
uv run fmq set tests/fixtures/project_pm/tasks/task-42.md status=escalated --dry-run
uv run fmq query tests/fixtures/project_pm 'status = "active"' | uv run fmq set status=reviewed --yes
git diff tests/fixtures/project_pm     # verify only YAML changed; comments preserved
```

**After C:**
```
uv run fmq query tests/fixtures/project_pm 'uuid = "task-42"' --follow blocked_by --depth '*'
```

**After D:**
```
uv run fmq describe tests/fixtures/project_pm
```

**After E:**
```
uv run fmq cypher tests/fixtures/project_pm 'MATCH (a)-[:blocked_by*]->(a) RETURN a'
uv run fmq query tests/fixtures/project_pm 'type = "task"' --search "indemnification" --index semantic
```

Integration tests in `tests/integration/test_end_to_end.py` gated by phase marker so CI runs only what has shipped.

---

## Risks & tricky bits

1. **ruamel round-trip drift.** Even load + dump without edits can be byte-different (empty lines, folded scalars). Goldens assert structure + style, not bytes. `--strict-bytes` mode is a post-MVP idea.
2. **New-key insertion position.** ruamel appends; users may expect grouping. Ship append-at-end; document; `--position` flag later.
3. **Date parsing.** `due_date__lt=today` cheap; string ISO values via `datetime.fromisoformat`. No `dateutil` dep unless forced.
4. **"today" meaning.** Resolved once at query construction, local tz. `--utc` flag for deterministic tests. Fixtures pin a clock.
5. **Cypher scope creep.** The grammar is the cliff. Freeze §8 scope; reject rest with a clean error pointing at docs.
6. **Pipe without workspace context.** Receiving command resolves via `--workspace` / first positional / longest common parent.
7. **List-append type conflicts.** `append(tags="urgent")` when `tags` is a string → refuse, suggest `set`. Same for `toggle` on non-bool.
8. **Reverse-index cost.** First `direction="reverse"` call scans full workspace. Flagged as perf item, fine for v1.
9. **Search in qlang.** Not in design doc's string examples — keep CLI-flag-only (`--search`, `--index`) across Phases A–D. Revisit in E.
10. **Workspace rescan.** Constraint is in-memory scan per init, but long-lived Python Workspaces exist. Expose `ws.rescan()` explicitly; no watch mode.
