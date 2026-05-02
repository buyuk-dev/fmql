---
id: 0010
title: Document I/O — structured `{header, body}` shape and CLI surface choices
status: accepted
date: 2026-05-03
context_task: 0017
---

## Context

Task [0017](../tasks/0017-frontmatter-document-serialization.md) adds two CLI commands that round-trip a markdown-with-frontmatter document through a structured `{header, body}` form in JSON or YAML. The acceptance criteria fix the canonical key names (`header`, `body`), the two formats, and the round-trip requirement, but leave four judgment calls unresolved:

1. What happens at the boundary between "no frontmatter" and "empty frontmatter"? JSON has no native distinction; markdown with no fence pair vs. an empty `---\n---\n` fence pair are semantically different.
2. Should the helpers (`to_obj`, `to_json`, `to_yaml`, `from_obj`, `from_json`, `from_yaml`) be added to the top-level Python public surface (`fmql.__init__`), or kept library-internal behind the CLI?
3. How symmetric should the two commands be — should `serialize` accept stdin and `deserialize` accept a file path, or stay file-in / stdin-out as the task examples show?
4. What line endings should `deserialize` emit on the synthesized markdown?

Each choice locks in observable behavior that is awkward to change later, so this ADR captures them up front.

## Decision

### 1. `header` tri-state semantics

| Structured input             | Resulting markdown                       |
| ---                          | ---                                      |
| `header` absent / `null`     | No fence pair (`has_frontmatter=False`)  |
| `header: {}` (empty mapping) | Empty fence pair `---\n---\n`            |
| `header: { ... }`            | Fence pair with serialized YAML          |

`to_obj` is the inverse: it omits the `header` key entirely when the source had no frontmatter at all, emits `header: {}` for an empty fence pair, and emits `header: { ... }` otherwise.

### 2. `fmql.document_io` is library-internal

The module exists at `fmql.document_io` with public-looking names (`to_json`, `from_yaml`, etc.) but is **not** added to `fmql.__init__` / `fmql.__all__`. The CLI is the documented surface; programmatic users can `from fmql.document_io import to_json` if they need to, but this import path is not yet promoted as a public API guarantee.

### 3. Asymmetric I/O — file in / stdin out

- `fmql serialize PATH` takes a single file path argument. No stdin support, no `-` sentinel.
- `fmql deserialize` reads the structured document from stdin only. No file path argument, no `-o OUTPUT` flag — output goes to stdout, redirect with `>`.

This matches the two task example invocations exactly.

### 4. `deserialize` emits LF-only fence lines

The synthesized `Packet` uses `eol="\n"`, `raw_prefix=""`, and `fence_style=("---","---")`. The `body` string is forwarded byte-for-byte from the structured input, so any line endings already inside the body are preserved. A document originally authored with CRLF that goes through `serialize → deserialize` will come back with LF on the fence/header lines — documented as expected.

## Rationale

### Why the tri-state header

- **Empty fence pair is real.** `---\n---\n` is a deliberately authored shape — many tools treat it as "this file participates in the frontmatter ecosystem, we just have no metadata yet." Collapsing it with "no frontmatter at all" loses information that round-trips would silently corrupt.
- **JSON null and key-absent are both reasonable spellings of "no frontmatter."** Different producers spell it differently — `jq` will emit `null` where Python's `json.dumps` of `{}` does not include the key. Treating both the same way keeps the surface forgiving without inventing a new sentinel.
- **It composes with `serialize_packet`'s existing heuristic.** The parser already differentiates `has_frontmatter` from `len(frontmatter) == 0` (`parser.py:173`). Mapping the structured form onto those two booleans is mechanical and reuses code that already has byte-exact round-trip tests behind it.

### Why `document_io` stays library-internal

- **The Python parser API is `parse` / `parse_file` / `serialize`** (ADR [0009](0009-parser-public-surface-shape.md)). The structured `{header, body}` form is genuinely useful as a CLI primitive (piping into `jq`, generating documents from another tool's output) but inside Python you already have the `Packet` object — `to_obj(parse_file(p))` is ergonomic but `parse_file(p).as_plain()` and `parse_file(p).body` already get you the same data, and `Packet.frontmatter` round-trips through ruamel without going through JSON's lossy date handling.
- **Promotion is purely additive.** If a Python use case shows up that the existing API does not cover, adding `from fmql import to_json, from_json, ...` later is a one-line addition to `__init__.py` and `__all__`. Going the other direction — un-promoting names that are already in `__all__` — is a breaking change.
- **One name per concept at the front door.** The existing `fmql.serialize` is `serialize_packet` (Packet → markdown string). Adding a separate `fmql.serialize_to_json` / `fmql.serialize_to_yaml` would put three things named `serialize*` in `__all__` and force readers to remember which one means what.

### Why asymmetric I/O

- **The task examples are the spec.** `fmql serialize notes/today.md --format json` and `cat doc.json | fmql deserialize --format json > notes/today.md` are exactly what the acceptance criteria show. Adding stdin support to `serialize` or a path argument to `deserialize` is non-zero ergonomics work (path/`-` discrimination, file-vs-stdin error messages, behavior of `-` when a real file is named `-`) and is not requested.
- **Smaller surface area is cheaper to evolve.** A future task can add `fmql serialize -` and `fmql deserialize PATH` if the use case shows up; the existing invocations keep working unchanged.
- **Stdout-only output keeps the deserialize side composable.** No `-o` flag means the convention is "always pipe or redirect," which aligns with the rest of the fmql CLI (no command writes to a path it picks itself; users redirect what they want to keep).

### Why LF-only fence lines on `deserialize`

- **The structured form has no line-ending field.** JSON has no concept of line endings; YAML normalizes them on parse. Detecting line endings from the body content would be a heuristic that gets the wrong answer for edge cases (body authored on Unix but published into a Windows-targeted artifact, etc.).
- **LF is the modern default for markdown tooling.** Pandoc, Hugo, MkDocs, Obsidian, and `git` all default to LF.
- **The escape hatch is documented.** Users who need byte-exact CRLF round-trip have a Python API (`parse → serialize`) that does so. The structured form is an interop convenience, not a byte-exact archival format — the README says so explicitly.

## Consequences

- **`document_io` semantics are now part of the stable surface.** Tests pin the tri-state `header` mapping and the LF-only emit on `deserialize`. Changing either later (e.g. dropping the empty-fence-pair distinction) is a breaking change for anyone who has scripts depending on byte-exact JSON↔markdown round-trips.
- **`fmql serialize` does not chain into `fmql query` output.** The structured form is a per-document shape, and `query` can return zero, one, or many rows. A future task can add a multi-document streaming variant (e.g. NDJSON, one `{header, body}` object per line) without disturbing this command.
- **`document_io._IO_YAML` is a separate ruamel instance from `parser._YAML`.** They are configured identically today, but the duplication insulates structured I/O from incidental changes to the parser's YAML configuration (e.g. enabling explicit-start markers for in-file frontmatter would otherwise leak `--- !!omap` etc. into the structured `header:` block).
- **Promotion to top-level Python is reversible-as-additive.** A future task that wants `from fmql import to_json` only adds names; it does not change existing imports.

## Alternatives considered

- **Two-state header (no `header: {}` distinction).** Considered. Rejected because empty fence pairs are deliberately authored in the wild and silently collapsing them on round-trip is exactly the kind of lossy interop bug this task exists to avoid.
- **Top-level `from fmql import to_json, ...`.** Considered. Deferred — the CLI is the demonstrated demand; if Python use materializes, promotion is a one-line additive change.
- **Symmetric stdin/file modes on both commands.** Considered. Rejected for now — task examples show file-in / stdin-out, and the `-` sentinel introduces real edge cases (path named `-`, mixed flag/positional ordering) that buy nothing the task asks for.
- **Detect line endings from body on `deserialize`.** Rejected — heuristic, surprising on mixed-content bodies, and the byte-exact use case is already covered by the Python API.
- **Reuse `parser._YAML` for structured-form I/O.** Rejected — one configuration change to support an unrelated parser feature could leak into the structured-form output, and the cost of a second `YAML(typ="rt")` instance is negligible.
