---
id: 0019
title: Project website hosted on GitHub Pages
status: todo
priority: 1
created: 2026-04-30
updated: 2026-04-30
tags: [docs, website, marketing, infra]
depends_on: []
phase: docs
---

## Goal

fmql's documentation today lives in `README.md` and a handful of files under `docs/` (design, plugins, fmql-semantic, monorepo). For users discovering the project, that means scrolling a long README on GitHub or jumping between unstructured markdown files. Ship a proper project website on GitHub Pages so we have:

- A real landing page that pitches "frontmatter knowledge graph engine" before dumping CLI flags on the reader.
- Navigable, searchable docs (install, quickstart, CLI reference, query/Cypher syntax, plugins, design, recipes).
- A stable URL we can point PyPI, GitHub topic listings, blog posts, and external write-ups at.
- Versioned docs so the site keeps matching the latest released `fmql` rather than drifting with `main`.

## Acceptance criteria

- [ ] A static site is built and served at a stable URL on GitHub Pages (either `buyuk-dev.github.io/fmql` or a custom subdomain — pick one and document it).
- [ ] Site source lives in the monorepo (e.g. `docs/site/` or `website/`); the existing `docs/*.md` files are either the source of truth or are referenced/included rather than duplicated, so docs don't fork.
- [ ] Build and deploy run from CI on push to `main` via a GitHub Actions workflow — no manual `gh-pages` branch maintenance.
- [ ] Information architecture covers, at minimum: landing / pitch, install, quickstart, CLI reference, query syntax (filter DSL + Cypher subset), traversal & resolvers, editing safety model, plugins (with `fmql-semantic` page), writing a search backend, and a link to GitHub for source / issues / tasks.
- [ ] Search across the docs works (built-in to the chosen framework is fine).
- [ ] The site renders code blocks with syntax highlighting for `bash`, `python`, `yaml`, and `cypher`.
- [ ] `README.md` keeps a short pitch + install + link to the site, and stops being the canonical full reference.
- [ ] Site footer links to PyPI, GitHub repo, license, and the issue tracker.
- [ ] Lighthouse / quick a11y pass: no broken links, all internal links resolve, mobile layout doesn't break.

## Notes

### Framework choice

Open question — pick one and justify in the PR. Strong candidates:

- **MkDocs + Material** — Python-native (fits the toolchain), excellent default theme, built-in search, simple `mkdocs.yml`. Lowest setup cost.
- **Docusaurus** — richer landing-page primitives, versioned docs first-class, MDX for embeddable widgets (e.g. a live "try a query" demo later). Higher setup cost but better growth ceiling.
- **Plain Jekyll (GitHub Pages default)** — least friction with GH Pages, but theming and IA are weaker out of the box.

Bias toward MkDocs Material unless the landing-page polish of Docusaurus is judged worth the extra config. Either way, the *content* matters more than the framework — don't sink the task into theme bikeshedding.

### Eat-our-own-dogfood opportunity

fmql is a tool for querying frontmatter-laden markdown corpora. The site is itself a frontmatter-laden markdown corpus. There's a tasteful demo to be had — e.g. generating "related pages" or a sitemap with `fmql query` / `fmql subgraph` at build time, or rendering a Mermaid dependency graph of the task list ([0018](0018-subgraph-mermaid-format.md)) on a "Roadmap" page. Out of scope for the v1 cut, but worth a follow-up task once the bones exist.

### Deferred / out of scope

- Versioned docs across multiple `fmql` releases — single "latest" is fine for v1.
- Custom domain (`fmql.dev` or similar). Use the default `*.github.io` URL until the project warrants the DNS.
- Blog / changelog channel. The GitHub Releases page is enough for now.
- Internationalization.

### Coordination

- Update PyPI project metadata (`pyproject.toml` `Homepage` / `Documentation` URLs) to point at the new site once it's live.
- Repo description and the README badges row should link to the site.
