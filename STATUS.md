---
session_id: eb18c243-232b-4caf-9bc6-8570b4748856
task_id: '0029'
branch: feature/wikilinks-support
phase: done
started: '2026-05-17T01:03:13Z'
---
Task **0029 — Wikilink support (body parsing + frontmatter `[[]]` value recognition)** finalized.

Branch: `feature/wikilinks-support`. Plan: `~/.claude/plans/get-started-on-task-elegant-nest.md`. ADR: [`docs/decisions/0012-wikilinks-as-per-item-dispatch.md`](docs/decisions/0012-wikilinks-as-per-item-dispatch.md).

## Outcome

- **New `packages/fmql/src/fmql/wikilinks.py`** (pure parse + resolve, no Workspace state):
  - `BODY_WIKILINK_RE = (?<!!)\[\[…\]\]` — negative lookbehind skips Obsidian's `![[…]]` embed syntax (out of scope for v1 per task notes).
  - `WHOLE_VALUE_WIKILINK_RE = ^\s*\[\[…\]\]\s*$` — frontmatter items wholly wrapped in brackets, leaving partial-string matches alone.
  - `WikilinkTarget(raw, target)` — `target` is `raw` with `#heading`/`^block-id` stripped (resolution is file-level per task; block refs deferred).
  - `parse_body_wikilinks(body) -> list[WikilinkTarget]`.
  - `match_whole_value_wikilink(value) -> Optional[WikilinkTarget]`.
  - `resolve_wikilink(link, workspace) -> WikilinkResolution(target, candidates)` — path-form via `workspace.packets` membership (tries `target` and `target + ".md"`); basename-form via `workspace.index_by_stem()` with alphabetical-by-pid tiebreak.
  - `MENTIONS_FIELD = "mentions"` — the canonical edge type for body wikilinks; lives here (the wikilinks concept) so `edges.py`, `workspace.py`, and `diagnostics.py` all import from a non-circular leaf.

- **New `packages/fmql/src/fmql/edges.py`** (single source of truth for forward+reverse edge enumeration):
  - `resolve_item(workspace, src, item, resolver)` — per-item dispatch: if `match_whole_value_wikilink(item)` matches, resolve as wikilink (resolver is *not* called); else fall through to the configured resolver. This is the structural enforcement of the frontmatter-shadowing rule.
  - `iter_body_wikilink_targets(workspace, pid)` — resolved body-link targets, dropping danglers. Reused by both forward and reverse enumeration to avoid the three-site duplication of the body-resolve loop.
  - `iter_forward_targets(workspace, pid, field, resolver)` — for `field == MENTIONS_FIELD`, yields body-derived targets first; then iterates frontmatter items through `resolve_item`. Per-call `seen` set dedups across the two sources.
  - `iter_reverse_sources` — thin pass-through to `Workspace.reverse_index(field, resolver)`.

- **`packages/fmql/src/fmql/workspace.py`**:
  - `_body_wikilinks: dict[PacketId, list[WikilinkTarget]]` populated eagerly in `_scan()` (one regex pass per file at load; ADR 0012 commits to eager — lazy is a follow-up if 10k-vault profiling shows the cost).
  - `body_wikilinks(pid)` accessor for `edges.py` and `diagnostics.py`.
  - `reverse_index(field, resolver)` extended in place to fuse wikilink-derived sources with resolver-derived sources. Same name, same cache key `(field, id(resolver))`, broader semantics. Mention-field branch reuses `iter_body_wikilink_targets`; the per-item branch reuses `resolve_item` — zero duplication of the dispatch logic.
  - Dropped the planned `fused_reverse_index` second method after the grep showed the only external caller of `reverse_index` was a cache-identity test that doesn't care which semantics the method has.

- **Refactor (regression gate):** `traversal._neighbors`, `subgraph._edges_for`, `cypher/executor._neighbors` previously duplicated the same "get field, iter, resolve" loop three ways. All three now delegate to `edges.iter_forward_targets` / `iter_reverse_sources`. Existing test suite (605 tests) passed before any wikilink semantics landed, then 76 new tests added on top.

- **`packages/fmql/src/fmql/diagnostics.py`**:
  - New `WikilinkDiagnostic(kind, source, field, raw, candidates)` with `kind: "ambiguous" | "unresolved"`.
  - `diagnose_wikilinks(workspace, fields)` — for `field == "mentions"` scans body wikilinks; for any field also scans frontmatter `[[]]` items. Inner `_record` helper collapses the body-vs-frontmatter classification (two structurally-identical post-resolve branches).
  - `format_wikilink_warning(d)` produces the stderr line.
  - `emit_resolver_warnings` and `maybe_emit_warnings` now emit both `FieldMismatch` and `WikilinkDiagnostic` lines through the existing `--diagnose` / `WORKSPACE.md fmql.diagnose: true` plumbing — no new CLI flag.
  - `diagnose_field` short-circuits `[[]]`-shaped items so they don't get double-counted as resolver-unresolved (otherwise every `related: ["[[Strategy]]"]` would fire a false-positive resolver warning).

- **ADR 0012 (`docs/decisions/0012-wikilinks-as-per-item-dispatch.md`):** captures the per-item dispatch design (vs. a configurable `WikilinkResolver`, vs. a second-pass enumeration), the `mentions` magic-field union semantics with dedup, the `reverse_index` collapse, and four alternatives considered with explicit rejection rationale.

- **README** (`packages/fmql/README.md`): new "Wikilinks (Obsidian compatibility)" subsection under Traversal & resolvers covering both shapes, resolution rules (basename / path-form / fragment-strip / alphabetical tiebreak), the per-item shadowing rule, and out-of-scope embeds + heading refs. Uses `_id` pseudo-field in examples to match the actual Cypher surface.

- **Tests (76 new across 4 modules):**
  - `tests/test_wikilinks.py` (20): regex pinning (body, alias, embed-skip, fragment-strip, whole-value match), basename resolve (single, ambiguous-alphabetical, missing), path-form (with/without `.md`, missing).
  - `tests/test_traversal_wikilinks.py` (11): `mentions` forward + reverse via `follow`; frontmatter `[[]]` scalar + list typed by property name; mixed list with explicit `UuidResolver` to pin the "resolver doesn't run for `[[]]` items" shadowing rule; dangling silently drops; `depth='*'`; regression pin that `project_pm_ws` (no wikilinks) behavior is unchanged; three Cypher MATCH cases (`mentions`, property-name, mixed list).
  - `tests/test_diagnostics_wikilinks.py` (10): unresolved / ambiguous body wikilinks; unresolved frontmatter `[[]]`; silence on clean workspace; format strings; integration through `emit_resolver_warnings` and `maybe_emit_warnings`; the `diagnose_field` skip-wikilink pin.
  - `tests/cli/test_query_cmd_wikilinks.py` (5): CLI `MATCH (a)-[:mentions]->(b)`, `MATCH (a)-[:primary]->(b)`, `--follow mentions`, `--diagnose` emits, no-`--diagnose` silence.
  - `tests/conftest.py`: new `obsidian_vault_ws` fixture (8 packets: body wikilinks incl. alias / embed-skip / fragment, frontmatter `[[]]` scalar + mixed list, ambiguous basename `Strategy`, dangling `[[Ghost]]`, path-form `[[business/notes/Roadmap]]`).

- **Workflow housekeeping:** archived prior STATUS body (task 0027) to `docs/changelog/0011.md`; flipped task 0029 to `done` with today's date (2026-05-17); added new "Phase: parser" row to `docs/roadmap.md`.

## Verification

- `make format` — reformatted three files (`edges.py`, `diagnostics.py`, `test_diagnostics_wikilinks.py`) on first pass; rerun clean.
- `make lint` — clean first run (ruff + black --check).
- `make test` — `fmql` 681 passed (was 605; +76 from the new wikilink tests across four modules), `fmql-semantic` 56 passed.

## Notes

- **`MENTIONS_FIELD` lives in `wikilinks.py`, not `edges.py`.** The first cut put it in `edges.py` and `workspace.py` did a lazy in-method import to dodge a perceived cycle. The /simplify review caught both: (a) the cycle was only at type-check time (edges.py uses `if TYPE_CHECKING: from fmql.workspace import Workspace`), so a top-level import works fine at runtime; (b) since wikilinks.py is the leaf module that originates the concept, putting the constant there resolves the import-direction smell — every consumer imports from one place. ADR 0012's "constant lives in" line was updated accordingly.

- **Two methods became one.** The plan had a `fused_reverse_index(field, resolver)` sitting alongside the original resolver-only `reverse_index(field, resolver)`. After implementing both and grepping for callers, only a cache-identity test reached `reverse_index` from outside the engine; that test only asserts `idx1 is idx2`, so the semantic change is invisible to it. Collapsing to one method drops the dead dual-surface — CLAUDE.md's "no backwards-compatibility hacks" principle covers this even at pre-1.0.

- **`mentions` is a reserved field name in the engine's vocabulary, with union semantics.** A user who has `mentions: ["task-1"]` in frontmatter AND body `[[task-1]]` gets one edge, not two (per-call `seen` set in `iter_forward_targets`; per-target dedup in `reverse_index`). Documented in the README and pinned by the `obsidian_vault_ws`-driven tests. The future `WORKSPACE.md body_link_edge_type` config (out of scope per task) is a one-line swap from the module constant to a workspace-config read.

- **Single quotes are not valid Cypher string delimiters in fmql.** Initial tests used `WHERE a.id = 'Index.md'` and failed at the parser ("No terminal matches ''' in the current parser context"). The grammar accepts `ESCAPED_STRING` (double quotes) only. Fixed the four affected tests + the README example. This is consistent with Cypher's own preference, not a divergence — worth noting because Cypher elsewhere often shows examples with single quotes.

- **`a.id` vs `a._id`.** Same fix pass: the pseudo-field is underscore-prefixed (`_id` / `_path`) per ADR 0003 — `a.id` resolves to the `id` frontmatter key, which most packets in the new fixture don't carry, so `WHERE a.id = "..."` matched nothing. README and tests now use `a._id`. The README's other examples were already correct; only the new wikilinks section needed the fix.

- **`diagnose_field` short-circuit is load-bearing.** Without it, the existing `--diagnose` plumbing would re-flag every `[[Strategy]]` as an unresolved value against the bound resolver, producing duplicate-and-misleading warnings alongside the new `WikilinkDiagnostic` lines. The one-line `if match_whole_value_wikilink(item) is not None: continue` is the entire fix; pinned by `test_wikilink_items_skipped_in_field_diagnose` in `test_diagnostics_wikilinks.py`.

- **Out of scope per task and ADR 0012:** `![[…]]` embeds (skipped at regex level via negative lookbehind), `#heading` / `^block-id` fragment edges (resolved to file only), configurable body-link edge type via `WORKSPACE.md`, lazy body parsing (eager is the v1 choice; performance follow-up if 10k-vault profiling shows it matters).
