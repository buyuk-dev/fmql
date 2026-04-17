from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fmql.search.errors import IndexVersionError
from fmql_semantic.storage import meta as meta_mod
from fmql_semantic.storage.connection import open_db
from fmql_semantic.storage.schema import FORMAT_VERSION
from fmql_semantic.storage.writer import open_for_build


def test_open_for_build_creates_all_tables(tmp_path: Path):
    location = str(tmp_path / "idx.db")
    conn = open_for_build(
        location,
        embedding_model="fake/embed",
        embedding_dim=8,
        fields=("title",),
        force=False,
        fmql_version="0.2.0",
    )
    try:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type in ('table','virtual')"
            )
        }
        # packets_fts shadow tables exist too; we care about the logical ones.
        assert {"meta", "packets"}.issubset(names)
        # Virtual tables appear as type='table' with a non-empty sql referencing USING.
        sqls = [
            row[0]
            for row in conn.execute(
                "SELECT sql FROM sqlite_master WHERE name IN ('vectors','packets_fts')"
            )
            if row[0]
        ]
        assert any("vec0" in (s or "") for s in sqls)
        assert any("fts5" in (s or "") for s in sqls)

        meta = meta_mod.read_all(conn)
        assert meta["format_version"] == str(FORMAT_VERSION)
        assert meta["embedding_model"] == "fake/embed"
        assert meta["embedding_dim"] == "8"
        assert meta["fields"] == "title"
    finally:
        conn.close()


def test_format_version_mismatch_raises_on_read(tmp_path: Path):
    location = str(tmp_path / "idx.db")
    conn = open_for_build(
        location,
        embedding_model="fake/embed",
        embedding_dim=8,
        fields=("title",),
        force=False,
        fmql_version="0.2.0",
    )
    conn.close()

    raw = sqlite3.connect(location)
    raw.execute("UPDATE meta SET value='99' WHERE key='format_version'")
    raw.commit()
    raw.close()

    conn = open_db(location, readonly=True, load_vec=False)
    try:
        meta = meta_mod.read_all(conn)
        with pytest.raises(IndexVersionError):
            meta_mod.check_format_version(meta)
    finally:
        conn.close()


def test_force_rebuild_drops_tables(tmp_path: Path):
    location = str(tmp_path / "idx.db")
    # First build with dim=8
    conn = open_for_build(
        location,
        embedding_model="fake/embed",
        embedding_dim=8,
        fields=("title",),
        force=False,
        fmql_version="0.2.0",
    )
    conn.close()
    # Second build with different model + force=True should succeed.
    conn = open_for_build(
        location,
        embedding_model="other/embed",
        embedding_dim=16,
        fields=("title",),
        force=True,
        fmql_version="0.2.0",
    )
    try:
        meta = meta_mod.read_all(conn)
        assert meta["embedding_model"] == "other/embed"
        assert meta["embedding_dim"] == "16"
    finally:
        conn.close()


def test_model_pin_refuses_without_force(tmp_path: Path):
    from fmql.search.errors import BackendUnavailableError

    location = str(tmp_path / "idx.db")
    conn = open_for_build(
        location,
        embedding_model="fake/embed",
        embedding_dim=8,
        fields=("title",),
        force=False,
        fmql_version="0.2.0",
    )
    conn.close()
    with pytest.raises(BackendUnavailableError, match="fake/embed"):
        open_for_build(
            location,
            embedding_model="other/embed",
            embedding_dim=8,
            fields=("title",),
            force=False,
            fmql_version="0.2.0",
        )
