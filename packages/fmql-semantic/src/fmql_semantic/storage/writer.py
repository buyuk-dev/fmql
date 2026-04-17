from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from sqlite_vec import serialize_float32  # type: ignore

from fmql_semantic import __version__ as semantic_version
from fmql_semantic.storage import meta as meta_mod
from fmql_semantic.storage.connection import open_db
from fmql_semantic.storage.schema import (
    CREATE_META,
    CREATE_PACKETS,
    CREATE_PACKETS_FTS,
    DROP_ALL,
    FORMAT_VERSION,
    create_vectors_sql,
)


def _drop_all(conn: sqlite3.Connection) -> None:
    for stmt in DROP_ALL:
        conn.execute(stmt)


def _ensure_tables(conn: sqlite3.Connection, *, dim: int) -> None:
    conn.execute(CREATE_META)
    conn.execute(CREATE_PACKETS)
    conn.execute(create_vectors_sql(dim))
    conn.execute(CREATE_PACKETS_FTS)


def open_for_build(
    location: str,
    *,
    embedding_model: str,
    embedding_dim: int,
    fields: Sequence[str],
    force: bool,
    fmql_version: str,
) -> sqlite3.Connection:
    """Open or create the index for writing.

    Validates format_version and model pin; on mismatch + force=True, drops everything.
    Creates tables if missing. Writes meta.
    """
    path = Path(location)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()

    conn = open_db(location, readonly=False, load_vec=True)
    try:
        if exists and force:
            _drop_all(conn)
            conn.commit()
            exists = False

        meta = meta_mod.read_all(conn) if exists else {}
        if meta:
            meta_mod.check_format_version(meta)
            meta_mod.check_model_pin(meta, embedding_model)
            stored_dim = meta.get("embedding_dim")
            if stored_dim and int(stored_dim) != embedding_dim:
                raise RuntimeError(
                    f"existing index dim={stored_dim} differs from current probe {embedding_dim}; "
                    "this should have been caught by check_model_pin"
                )

        _ensure_tables(conn, dim=embedding_dim)
        meta_mod.write(
            conn,
            {
                "format_version": str(FORMAT_VERSION),
                "backend_version": semantic_version,
                "fmql_version": fmql_version,
                "embedding_model": embedding_model,
                "embedding_dim": str(embedding_dim),
                "fields": ",".join(fields),
                "built_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        conn.commit()
    except Exception:
        conn.close()
        raise
    return conn


def fetch_existing_hashes(conn: sqlite3.Connection) -> dict[str, tuple[int, str]]:
    """Return {packet_id: (rowid, content_hash)} for all currently indexed packets."""
    rows = conn.execute("SELECT id, packet_id, content_hash FROM packets").fetchall()
    return {pid: (rid, h) for rid, pid, h in rows}


def delete_packets(conn: sqlite3.Connection, rowids: Iterable[int]) -> int:
    rowids_list = list(rowids)
    if not rowids_list:
        return 0
    placeholders = ",".join("?" * len(rowids_list))
    conn.execute(f"DELETE FROM vectors WHERE rowid IN ({placeholders})", rowids_list)
    conn.execute(f"DELETE FROM packets_fts WHERE rowid IN ({placeholders})", rowids_list)
    conn.execute(f"DELETE FROM packets WHERE id IN ({placeholders})", rowids_list)
    return len(rowids_list)


def _next_rowid(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM packets").fetchone()
    return int(row[0]) + 1


def upsert_batch(
    conn: sqlite3.Connection,
    rows: Sequence[tuple[str, str, str]],
    embeddings: Sequence[Sequence[float]],
) -> None:
    """rows: [(packet_id, content_hash, document_text), ...] aligned with `embeddings`."""
    if not rows:
        return
    assert len(rows) == len(embeddings), "rows/embeddings length mismatch"
    now = datetime.now(timezone.utc).isoformat()

    existing = conn.execute(
        f"SELECT packet_id, id FROM packets WHERE packet_id IN ({','.join('?' * len(rows))})",
        [pid for pid, _, _ in rows],
    ).fetchall()
    existing_map = {pid: rid for pid, rid in existing}

    for (packet_id, chash, doc), vec in zip(rows, embeddings):
        if packet_id in existing_map:
            rowid = existing_map[packet_id]
            conn.execute(
                "UPDATE packets SET content_hash=?, indexed_at=? WHERE id=?",
                (chash, now, rowid),
            )
            conn.execute("DELETE FROM vectors WHERE rowid=?", (rowid,))
            conn.execute("DELETE FROM packets_fts WHERE rowid=?", (rowid,))
        else:
            rowid = _next_rowid(conn)
            conn.execute(
                "INSERT INTO packets(id, packet_id, content_hash, indexed_at) VALUES(?,?,?,?)",
                (rowid, packet_id, chash, now),
            )
        conn.execute(
            "INSERT INTO vectors(rowid, embedding) VALUES(?, ?)",
            (rowid, serialize_float32(list(vec))),
        )
        conn.execute(
            "INSERT INTO packets_fts(rowid, content) VALUES(?, ?)",
            (rowid, doc),
        )
