---
title: Pick Postgres for Atlas storage
date: 2025-11-04
status: accepted
relates_to:
  - '[[projects/Atlas]]'
  - Borealis
---

We chose Postgres over the two alternatives we evaluated. Primary driver was
operational familiarity on the [[team/Alice|engineering]] side; secondary was
the JSONB story for [[projects/Atlas]]'s semi-structured payloads.

The second `relates_to` entry is intentionally a bare string, not a wikilink —
it demonstrates fmql's mixed-list handling: the `[[]]` form creates an edge,
the bare string falls through to whatever resolver (if any) is configured.
