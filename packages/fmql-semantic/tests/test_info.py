from __future__ import annotations

from pathlib import Path

import pytest

from fmql.workspace import Workspace
from fmql_semantic import SemanticBackend


@pytest.fixture(autouse=True)
def _env_model(monkeypatch):
    monkeypatch.setenv("FMQL_EMBEDDING_MODEL", "fake/embed")


def test_info_without_location():
    info = SemanticBackend().info()
    assert info.kind == "indexed"
    assert info.name == "semantic"
    assert info.version


def test_info_missing_file_reports_error(tmp_path: Path):
    info = SemanticBackend().info(str(tmp_path / "missing.db"))
    assert info.kind == "indexed"
    assert info.metadata.get("error")


def test_info_reads_meta_from_real_index(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "a.md").write_text("---\n---\nalpha\n", encoding="utf-8")
    ws = Workspace(root)
    backend = SemanticBackend()
    loc = str(tmp_path / "idx.db")
    backend.build(list(ws.packets.values()), loc)
    info = backend.info(loc)
    assert info.metadata["embedding_model"] == "fake/embed"
    assert info.metadata["embedding_dim"] == "8"


def test_default_location_uses_workspace_root(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    ws = Workspace(root)
    be = SemanticBackend()
    assert be.default_location(ws).endswith(".fmql/semantic.db")


def test_parse_location_rejects_empty():
    with pytest.raises(ValueError):
        SemanticBackend().parse_location("")
