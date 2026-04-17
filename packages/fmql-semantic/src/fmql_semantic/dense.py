from __future__ import annotations

import sqlite3
from typing import Sequence

from sqlite_vec import serialize_float32  # type: ignore


def dense_search(
    conn: sqlite3.Connection,
    query_vec: Sequence[float],
    *,
    fetch_k: int,
) -> list[tuple[str, float]]:
    """Return [(packet_id, score)] ordered by descending similarity. Score = -distance."""
    rows = conn.execute(
        "SELECT v.rowid, v.distance, p.packet_id "
        "FROM vectors v JOIN packets p ON p.id = v.rowid "
        "WHERE v.embedding MATCH ? AND k = ? "
        "ORDER BY v.distance",
        (serialize_float32(list(query_vec)), fetch_k),
    ).fetchall()
    return [(packet_id, -float(distance)) for _, distance, packet_id in rows]
