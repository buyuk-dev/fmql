# TODO

- Hint on stderr when a Cypher / `--follow` query returns zero rows but the field is set on some docs (resolver mismatch).
- `fmql subgraph` subcommand (or Cypher path variable `p = ...`) to return full subgraphs as `{nodes, edges}`.
- Pseudo-field `a._id` / `a._path` in Cypher `WHERE` so start nodes can be pinned by packet id without frontmatter bookkeeping.
- Allow string / number literals as `RETURN` items (e.g. `RETURN a.title, "|", b.title`).
- Visible row separator in `rows` format (tab is invisible); `--separator` option or better default.
- All file paths in the CLI should be workspace-relative, everywhere (positional args, stdin, outputs).
- `fmql-semantic`: `--option env=.env` only loads `FMQL_*` keys; provider vars like `AZURE_API_BASE`, `AZURE_API_KEY`, `AZURE_API_VERSION`, `OPENAI_API_KEY` are silently ignored. LiteLLM reads them from `os.environ` directly, so users expecting a general dotenv loader hit confusing auth/connection errors. Fix: either push all parsed .env vars into `os.environ` so LiteLLM picks them up, or document the `FMQL_*`-only scope explicitly.
- `fmql-semantic`: remove the "Python build must support loadable-extension sqlite3" install requirement. `pysqlite3-binary` (ChromaDB's solution) does NOT solve this on macOS because there are no macOS wheels for it; rules out the `sys.modules` swap approach. Use **apsw** instead: pre-built wheels for macOS (x86_64 + arm64), Linux, Windows, always supports `enable_load_extension()` regardless of system Python build flags. Requires a compatibility shim in fmql-semantic because apsw's API (cursors, exceptions, parameter binding) is not drop-in with stdlib sqlite3. Ship a thin wrapper that exposes the subset fmql-semantic uses, and swap the backend import. Result: `pip install fmql-semantic` works on any Python, on any platform, and the README can drop its Python-build caveat entirely.

- [ ] fmql-semantic (not a blocker): that LiteLLM RuntimeWarning at the end of every indexing run is user-visible noise. Two ways to clean it up — either bump the pinned LiteLLM version (newer versions have fixed some of these async-logging paths) or suppress it explicitly around the embedding call
  
  


## Wishlist

- [ ] Pattern matching for inferring document type from its structure
- [ ] Frontmatter -> json, yaml serialization and deserialization (by packaging frontmatter into the "header" and markdown body into "body" prop).
- [ ] filesystem level operations (inspecting filesystem metadata, filesystem ops: mv, cp, rm, ls, etc...)


