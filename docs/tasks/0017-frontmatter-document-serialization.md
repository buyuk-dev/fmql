---
id: 0017
title: Frontmatter documents — JSON / YAML serialization and deserialization
status: todo
priority: 1
created: 2026-04-19
updated: 2026-04-19
tags: [cli, frontmatter, serialization, interop]
depends_on: []
github_issue: https://github.com/buyuk-dev/fmql/issues/10
phase: cli
---

## Goal

fmql documents are markdown files with a YAML frontmatter header and a markdown body. Today there is no standard way to round-trip a document through a structured format like JSON or YAML — useful for piping into other tools, generating documents programmatically, or embedding fmql output in a larger data pipeline.

Provide lossless serialization and deserialization between a markdown-with-frontmatter document and a structured object with two canonical keys:

- `header` — the parsed frontmatter (object).
- `body` — the raw markdown body (string).

## Acceptance criteria

- [ ] `fmql serialize` emits `{header, body}` in JSON and YAML.
- [ ] `fmql deserialize` reconstructs a valid markdown-with-frontmatter file from the structured form.
- [ ] Round-trip (`serialize` → `deserialize`) is byte-identical for well-formed inputs, or at minimum preserves frontmatter keys, body content, and ordering where the underlying YAML library allows.
- [ ] Round-trip tests cover both formats on a representative document.
- [ ] Behavior for edge cases (no frontmatter, empty body, non-string scalar values) is covered by tests and documented.

## Notes

### Serialize

```bash
fmql serialize notes/today.md --format json
```

```json
{
  "header": { "title": "Today", "tags": ["inbox"] },
  "body": "# Today\n\nSome notes...\n"
}
```

Same shape for `--format yaml`.

### Deserialize

```bash
cat doc.json | fmql deserialize --format json > notes/today.md
```

Cloned from GitHub issue [#10](https://github.com/buyuk-dev/fmql/issues/10).
