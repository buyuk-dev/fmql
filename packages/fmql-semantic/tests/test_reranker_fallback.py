from __future__ import annotations

from pathlib import Path

import pytest
from fakes.provider import FailingReranker

from fmql.search.errors import BackendUnavailableError
from fmql.workspace import Workspace
from fmql_semantic import SemanticBackend


@pytest.fixture(autouse=True)
def _env_model(monkeypatch):
    monkeypatch.setenv("FMQL_EMBEDDING_MODEL", "fake/embed")


def _build(tmp_path: Path) -> tuple[SemanticBackend, str]:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "a.md").write_text("---\n---\nalpha\n", encoding="utf-8")
    (root / "b.md").write_text("---\n---\nbeta\n", encoding="utf-8")
    ws = Workspace(root)
    backend = SemanticBackend()
    loc = str(tmp_path / "idx.db")
    backend.build(list(ws.packets.values()), loc)
    return backend, loc


def test_rerank_soft_fail_returns_rrf(tmp_path: Path, monkeypatch):
    backend, loc = _build(tmp_path)
    import litellm  # type: ignore

    failing = FailingReranker(RuntimeError("provider down"))
    monkeypatch.setattr(litellm, "arerank", failing)

    hits = backend.query("alpha", loc, k=3, options={"reranker_model": "fake/rerank"})
    assert failing.calls == 1
    assert len(hits) >= 1  # still returns something via RRF


def test_rerank_required_hard_fails(tmp_path: Path, monkeypatch):
    backend, loc = _build(tmp_path)
    import litellm  # type: ignore

    failing = FailingReranker(RuntimeError("provider down"))
    monkeypatch.setattr(litellm, "arerank", failing)

    with pytest.raises(BackendUnavailableError):
        backend.query(
            "alpha",
            loc,
            k=3,
            options={"reranker_model": "fake/rerank", "rerank_required": True},
        )
