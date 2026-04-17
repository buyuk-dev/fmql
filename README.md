# fmql monorepo

Home of [`fmql`](https://pypi.org/project/fmql/) and related packages. Each
package under `packages/*` is fully self-contained (own version, own README,
own CHANGELOG, own PyPI release). The monorepo layout lets the core and its
plugins evolve together with atomic cross-package changes.

## Packages

| Package | Path | PyPI | Description |
|---|---|---|---|
| `fmql` | [packages/fmql](packages/fmql) | [pypi.org/project/fmql](https://pypi.org/project/fmql/) | Schemaless query engine and editor for directories of frontmatter files. |
| `fmql-semantic` | [packages/fmql-semantic](packages/fmql-semantic) | [pypi.org/project/fmql-semantic](https://pypi.org/project/fmql-semantic/) | Semantic search backend plugin. Pre-alpha stub; not published. |

See each package's README for usage.

## Development

```bash
uv sync --group dev         # install all packages (editable) + dev tooling
make lint                   # ruff + black --check across all packages
make test                   # pytest for every package
make cov                    # pytest with coverage (core fails under 84%)
```

## Releases

Tag-driven, per-package:

- Push `core-v<version>` to publish `fmql` to PyPI (tag must match
  `packages/fmql/pyproject.toml`'s version — the publish workflow verifies
  this and fails otherwise).
- Push `semantic-v<version>` to publish `fmql-semantic` (not yet wired up
  on PyPI; publishes will start once the package leaves stub status).

Each package has its own CHANGELOG. Unprefixed `v*` tags are historical.

## Design notes

- [docs/monorepo.md](docs/monorepo.md) — monorepo spec.
- [docs/design.md](docs/design.md) — `fmql` core architecture.
- [docs/plugins.md](docs/plugins.md) — search backend plugin protocol.
- [docs/fmql-semantic.md](docs/fmql-semantic.md) — `fmql-semantic` design.

## License

MIT, covers all packages. See [LICENSE](LICENSE).
