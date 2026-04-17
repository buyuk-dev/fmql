# Changelog

All notable changes to this package will be documented in this file.

## [0.1.0] - 2026-04-17

### Added

- Hybrid-retrieval `semantic` backend registered via the `fmql.search_index` entry point.
- Dense embeddings through LiteLLM (`litellm.aembedding`) stored in `sqlite-vec` virtual tables with DDL-pinned dimensions.
- Sparse BM25 retrieval via SQLite FTS5 (`unicode61 remove_diacritics 2` tokenizer).
- Reciprocal Rank Fusion (k=60) combining dense + sparse rankings.
- Optional cross-encoder reranking via `litellm.arerank` with soft-fail fallback to RRF.
- Query modes: hybrid (default), `dense_only`, `sparse_only`, `no_rerank`.
- Incremental indexing keyed on content hash; deletions reconciled on rebuild.
- Model pinning in index metadata; mismatches refuse to build without `--force`.
- Format-version gate (`FORMAT_VERSION = 1`) raises `IndexVersionError` on incompatible indexes.
- Config resolution: `--option KEY=VALUE` > dotenv (`--option env=path`) > `FMQL_*` env > defaults.
- Optional `progress` extra adds `tqdm` progress bars.
