from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fmql.search.conformance import (
    assert_indexed_build_is_idempotent,
    assert_indexed_build_then_query,
    assert_indexed_handles_deletion,
    assert_indexed_info_tolerates_missing,
    assert_indexed_version_mismatch_raises,
    default_workspace_factory,
)
from fmql_semantic import SemanticBackend


@pytest.fixture(autouse=True)
def _env_model(monkeypatch):
    monkeypatch.setenv("FMQL_EMBEDDING_MODEL", "fake/embed")


def _fresh_ws(tmp_path: Path) -> Path:
    d = tmp_path / "ws"
    d.mkdir()
    return d


def test_build_then_query(tmp_path: Path):
    ws = _fresh_ws(tmp_path)
    assert_indexed_build_then_query(
        SemanticBackend(),
        default_workspace_factory(ws),
        location=str(tmp_path / "idx.db"),
    )


def test_build_is_idempotent(tmp_path: Path):
    ws = _fresh_ws(tmp_path)
    assert_indexed_build_is_idempotent(
        SemanticBackend(),
        default_workspace_factory(ws),
        location=str(tmp_path / "idx.db"),
    )


def test_handles_deletion(tmp_path: Path):
    ws = _fresh_ws(tmp_path)
    assert_indexed_handles_deletion(
        SemanticBackend(),
        default_workspace_factory(ws),
        location=str(tmp_path / "idx.db"),
    )


def test_info_tolerates_missing(tmp_path: Path):
    assert_indexed_info_tolerates_missing(
        SemanticBackend(),
        missing_location=str(tmp_path / "does-not-exist.db"),
    )


def test_version_mismatch_raises(tmp_path: Path):
    def _corrupt(location: str) -> None:
        conn = sqlite3.connect(location)
        try:
            conn.execute("UPDATE meta SET value='99' WHERE key='format_version'")
            conn.commit()
        finally:
            conn.close()

    ws = _fresh_ws(tmp_path)
    backend = SemanticBackend()
    location = str(tmp_path / "idx.db")
    # Build first so there's something to corrupt.
    factory = default_workspace_factory(ws)
    workspace = factory({"a.md": "---\n---\nalpha\n"})
    backend.build(list(workspace.packets.values()), location)
    assert_indexed_version_mismatch_raises(backend, _corrupt, location)
