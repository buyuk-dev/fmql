---
id: 0014
title: Visible row separator in `rows` output format
status: todo
priority: 2
created: 2026-04-19
updated: 2026-04-19
tags: [cli, output, ux]
depends_on: []
github_issue: https://github.com/buyuk-dev/fmql/issues/7
phase: wishlist
---

## Goal

The `rows` output format uses a tab character to separate columns. Tabs are invisible in most terminals and copy-paste targets, which makes it hard to tell where one column ends and the next begins — especially when values themselves contain whitespace.

## Acceptance criteria

- [ ] `rows` format produces output where column boundaries are visually unambiguous by default.
- [ ] If a `--separator` option is added, it is documented in `--help` and the README.

## Notes

Two viable directions, pick one:

- Change the default separator to something visible (e.g. ` | ` or a `\t`-with-a-prefix), **or**
- Add a `--separator` CLI option so users can pick their own, while keeping a sensible visible default.

Open to either direction — the main goal is that the default output is human-readable without post-processing.

### Example

Given a query returning `a.title`, `b.title`:

```
# current (tab-separated, invisible boundary)
Foo    Bar

# desired default
Foo | Bar
```

Cloned from GitHub issue [#7](https://github.com/buyuk-dev/fmql/issues/7).
