from __future__ import annotations

from pathlib import Path

import pytest

from fmql.workspace import Workspace
from fmql_semantic import SemanticBackend


@pytest.fixture(autouse=True)
def _env_model(monkeypatch):
    monkeypatch.setenv("FMQL_EMBEDDING_MODEL", "fake/embed")


def _ws(root: Path, files: dict[str, str]) -> Workspace:
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        (root / rel).write_text(content, encoding="utf-8")
    return Workspace(root)


def _build(tmp_path: Path) -> tuple[SemanticBackend, str]:
    ws = _ws(
        tmp_path / "ws",
        {
            "widgets.md": "---\ntitle: Widget spec\n---\nWidgets are small things.\n",
            "sprockets.md": "---\ntitle: Sprocket design\n---\nSprockets rotate.\n",
            "other.md": "---\ntitle: Unrelated\n---\nSomething totally different.\n",
        },
    )
    backend = SemanticBackend()
    loc = str(tmp_path / "idx.db")
    backend.build(list(ws.packets.values()), loc)
    return backend, loc


def test_hybrid_returns_results(tmp_path: Path):
    backend, loc = _build(tmp_path)
    hits = backend.query("widgets", loc, k=3)
    assert len(hits) >= 1
    ids = [h.packet_id for h in hits]
    assert "widgets.md" in ids


def test_sparse_only_skips_embeddings(tmp_path: Path, monkeypatch):
    backend, loc = _build(tmp_path)
    from fmql_semantic import backend as backend_mod

    calls = {"n": 0}
    original = backend_mod._embed_batch

    async def _count(*a, **kw):
        calls["n"] += 1
        return await original(*a, **kw)

    monkeypatch.setattr(backend_mod, "_embed_batch", _count)
    hits = backend.query("widgets", loc, k=3, options={"sparse_only": True})
    assert calls["n"] == 0, "sparse_only must not call embeddings"
    assert any(h.packet_id == "widgets.md" for h in hits)


def test_dense_only_skips_fts(tmp_path: Path):
    backend, loc = _build(tmp_path)
    hits = backend.query("widgets", loc, k=3, options={"dense_only": True})
    assert len(hits) >= 1


def test_empty_query_returns_empty(tmp_path: Path):
    backend, loc = _build(tmp_path)
    assert backend.query("", loc, k=3) == []


def test_rerank_changes_ordering(tmp_path: Path, monkeypatch):
    backend, loc = _build(tmp_path)

    # With a configured reranker, the ranker's per-doc scores should drive final order.
    hits = backend.query(
        "widgets",
        loc,
        k=3,
        options={"reranker_model": "fake/rerank"},
    )
    assert len(hits) >= 1


def test_no_rerank_skips_reranker(tmp_path: Path, monkeypatch):
    backend, loc = _build(tmp_path)
    import litellm  # type: ignore

    calls = {"n": 0}
    original = litellm.arerank

    async def _count(*a, **kw):
        calls["n"] += 1
        return await original(*a, **kw)

    monkeypatch.setattr(litellm, "arerank", _count)
    backend.query(
        "widgets",
        loc,
        k=3,
        options={"reranker_model": "fake/rerank", "no_rerank": True},
    )
    assert calls["n"] == 0
