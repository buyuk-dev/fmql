from __future__ import annotations

import sqlite3

from fmql.search.errors import BackendUnavailableError, IndexVersionError
from fmql_semantic.storage.schema import FORMAT_VERSION


def read_all(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        rows = conn.execute("SELECT key, value FROM meta").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {k: v for k, v in rows}


def write(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    conn.executemany(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        [(k, str(v)) for k, v in values.items()],
    )


def check_format_version(meta: dict[str, str]) -> None:
    raw = meta.get("format_version")
    if raw is None:
        return
    try:
        stored = int(raw)
    except ValueError as e:
        raise IndexVersionError(
            f"index has malformed format_version={raw!r}; rebuild with --force"
        ) from e
    if stored != FORMAT_VERSION:
        raise IndexVersionError(
            f"index format_version={stored} is incompatible with this backend "
            f"(expected {FORMAT_VERSION}). Rebuild with "
            f"`fmql index ... --backend semantic --force`."
        )


def check_model_pin(meta: dict[str, str], requested_model: str) -> None:
    stored = meta.get("embedding_model")
    if stored and stored != requested_model:
        raise BackendUnavailableError(
            f"index was built with embedding model {stored!r}, but the current request "
            f"uses {requested_model!r}. Pass --force to rebuild from scratch, or use the "
            f"original model."
        )
