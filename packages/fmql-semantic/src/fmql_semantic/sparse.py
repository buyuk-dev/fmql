from __future__ import annotations

import re
import sqlite3

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _fts5_query(text: str) -> str:
    words = _WORD_RE.findall(text)
    if not words:
        return ""
    return " OR ".join(f'"{w}"' for w in words)


def sparse_search(
    conn: sqlite3.Connection,
    query: str,
    *,
    fetch_k: int,
) -> list[tuple[str, float]]:
    """Return [(packet_id, score)] ordered by descending BM25 relevance. Score = -bm25."""
    q = _fts5_query(query)
    if not q:
        return []
    rows = conn.execute(
        "SELECT f.rowid, bm25(packets_fts) AS s, p.packet_id "
        "FROM packets_fts f JOIN packets p ON p.id = f.rowid "
        "WHERE packets_fts MATCH ? "
        "ORDER BY s "
        "LIMIT ?",
        (q, fetch_k),
    ).fetchall()
    return [(packet_id, -float(s)) for _, s, packet_id in rows]
