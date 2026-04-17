from __future__ import annotations

import sqlite3
from pathlib import Path

from fmql.search.errors import BackendUnavailableError


def open_db(
    path: str | Path, *, readonly: bool = False, load_vec: bool = True
) -> sqlite3.Connection:
    p = Path(path)
    if readonly:
        if not p.exists():
            raise FileNotFoundError(f"index not found: {p}")
        uri = f"file:{p.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(p))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

    if load_vec:
        try:
            conn.enable_load_extension(True)
        except (AttributeError, sqlite3.NotSupportedError) as e:
            conn.close()
            raise BackendUnavailableError(
                "this Python build's sqlite3 module does not support loadable extensions, "
                "which sqlite-vec requires. Install Python via uv/pyenv/python.org "
                "(not the macOS system Python or a distro build compiled without "
                "--enable-loadable-sqlite-extensions)."
            ) from e
        try:
            import sqlite_vec  # type: ignore

            sqlite_vec.load(conn)
        except ImportError as e:
            conn.close()
            raise BackendUnavailableError(
                "sqlite-vec is not installed. Install it with `pip install sqlite-vec`."
            ) from e
        finally:
            try:
                conn.enable_load_extension(False)
            except Exception:
                pass
    return conn


def probe_extension_support() -> bool:
    """True iff this Python can load sqlite extensions AND sqlite-vec is importable."""
    try:
        conn = sqlite3.connect(":memory:")
    except sqlite3.Error:
        return False
    try:
        try:
            conn.enable_load_extension(True)
        except (AttributeError, sqlite3.NotSupportedError):
            return False
        try:
            import sqlite_vec  # type: ignore

            sqlite_vec.load(conn)
        except ImportError:
            return False
        except sqlite3.Error:
            return False
        return True
    finally:
        conn.close()
