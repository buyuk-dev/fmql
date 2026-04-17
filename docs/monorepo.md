# fmql Monorepo — Quick Spec

**What:** Convert the `fmql` repo to host multiple related packages. First one stays `fmql` (core). Next one will be `fmql-semantic`. More may follow.

**Why:** Protocol evolution between core and plugins is easier when they live in one repo. One CI, one set of tooling, atomic cross-package changes.

## Layout

```
fmql/                       # repo root (github.com/buyuk-dev/fmql)
├── README.md               # monorepo overview, links to packages — shown on GitHub homepage
├── LICENSE                 # MIT, covers all packages
├── packages/
│   ├── fmql/               # the core package (formerly repo root contents)
│   │   ├── README.md       # shipped to PyPI as fmql's package description
│   │   ├── CHANGELOG.md
│   │   └── pyproject.toml
│   └── fmql-semantic/      # plugin, lands in a later release
│       ├── README.md       # shipped to PyPI as fmql-semantic's description
│       ├── CHANGELOG.md
│       └── pyproject.toml
└── docs/                   # cross-package design docs
```

Each `packages/*` directory is fully self-contained: own `pyproject.toml`, own version, own `CHANGELOG.md`, own README.

## Tooling

**uv workspaces** tie the packages together for local development. A top-level `pyproject.toml` declares the workspace members. `uv sync` at the root installs everything with local source links, so edits to `fmql` are immediately visible to `fmql-semantic` without reinstalling.

Published packages depend on each other normally via PyPI version specifiers. The workspace link is a dev-time convenience, invisible to end users.

## Versioning

Each package versions independently. Core can be at 0.3.0 while semantic is at 0.1.0.

Git tags encode which package is being released: `core-v0.2.0`, `semantic-v0.1.0`. No unprefixed version tags.

## Release flow

CI is tag-driven. A push of `core-v*` publishes the core package to PyPI. A push of `semantic-v*` publishes the semantic package. Other packages are untouched.

Each release is independent. No forced cross-package version bumps.

## CI

Every PR runs tests for all packages. This is intentional — the monorepo's main value is catching cross-package breakage early, so the test suite should exercise that.

Separate jobs per package, parallelised. Failure in one doesn't block visibility into the others.

## Changelogs

Per-package only. Each `packages/*/CHANGELOG.md` tracks that package's releases in isolation. No top-level aggregate — anyone who wants a cross-package view uses the git log.

## READMEs

Two kinds, distinct purposes:

- **Top-level `README.md`** — the GitHub homepage. Explains that this is a monorepo, lists packages with one-line descriptions, links to each package's PyPI page and subdirectory.
- **Per-package `packages/*/README.md`** — shipped to PyPI as that package's description. Focused on that package alone, written as if it were the only thing in the repo.

## Issues and discussions

Use GitHub labels to tag issues by package (`package:core`, `package:semantic`). Users filing from the wrong PyPI page get redirected via labels, not asked to re-file elsewhere.

## Migration

One-time work, done when `fmql-semantic` is ready to ship:

1. Move current `fmql` source into `packages/fmql/` using `git mv` to preserve history across the rename.
2. Add top-level workspace config and monorepo README.
3. Adopt the `core-v*` tag convention; document that old `v*` tags are historical.
4. Add `packages/fmql-semantic/` alongside.
5. We need to update `CI workflows accordingly, and ensure that repo settings (branch protections, tags rulesets, etc) are updated to reflect tagging convention changes.

Nothing changes for existing users installing the current `fmql` package. Next release tagged `core-v0.2.0` lands on PyPI identically to how current releases do.
