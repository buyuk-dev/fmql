from __future__ import annotations

FORMAT_VERSION = 1

CREATE_META = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

CREATE_PACKETS = """
CREATE TABLE IF NOT EXISTS packets (
    id INTEGER PRIMARY KEY,
    packet_id TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    indexed_at TEXT NOT NULL
)
"""

CREATE_PACKETS_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS packets_fts USING fts5(
    content,
    tokenize = 'unicode61 remove_diacritics 2'
)
"""


def create_vectors_sql(dim: int) -> str:
    if dim <= 0:
        raise ValueError(f"embedding dimension must be positive, got {dim}")
    return f"CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING vec0(embedding float[{dim}])"


DROP_ALL = [
    "DROP TABLE IF EXISTS vectors",
    "DROP TABLE IF EXISTS packets_fts",
    "DROP TABLE IF EXISTS packets",
    "DROP TABLE IF EXISTS meta",
]
