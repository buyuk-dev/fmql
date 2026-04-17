from __future__ import annotations

from pathlib import Path

import pytest

from fmql.search.errors import BackendUnavailableError
from fmql.workspace import Workspace
from fmql_semantic import SemanticBackend


@pytest.fixture(autouse=True)
def _env_model(monkeypatch):
    monkeypatch.setenv("FMQL_EMBEDDING_MODEL", "fake/embed")


def _ws(root: Path, files: dict[str, str]) -> Workspace:
    root.mkdir(parents=True, exist_ok=True)
    for path in list(root.iterdir()):
        if path.is_file():
            path.unlink()
    for rel, content in files.items():
        (root / rel).write_text(content, encoding="utf-8")
    return Workspace(root)


def test_incremental_skip_when_nothing_changes(tmp_path: Path):
    ws = _ws(
        tmp_path / "ws",
        {
            "a.md": "---\ntitle: A\n---\nalpha text\n",
            "b.md": "---\ntitle: B\n---\nbeta text\n",
        },
    )
    backend = SemanticBackend()
    loc = str(tmp_path / "idx.db")
    stats1 = backend.build(list(ws.packets.values()), loc)
    assert stats1.packets_indexed == 2
    assert stats1.packets_skipped == 0
    stats2 = backend.build(list(ws.packets.values()), loc)
    assert stats2.packets_indexed == 0
    assert stats2.packets_skipped == 2


def test_incremental_only_edited_packet_reembeds(tmp_path: Path):
    root = tmp_path / "ws"
    ws1 = _ws(
        root,
        {
            "a.md": "---\ntitle: A\n---\nalpha\n",
            "b.md": "---\ntitle: B\n---\nbeta\n",
        },
    )
    backend = SemanticBackend()
    loc = str(tmp_path / "idx.db")
    backend.build(list(ws1.packets.values()), loc)
    ws2 = _ws(
        root,
        {
            "a.md": "---\ntitle: A\n---\nalpha edited\n",
            "b.md": "---\ntitle: B\n---\nbeta\n",
        },
    )
    stats = backend.build(list(ws2.packets.values()), loc)
    assert stats.packets_indexed == 1
    assert stats.packets_skipped == 1


def test_deletion_reflected_on_rebuild(tmp_path: Path):
    root = tmp_path / "ws"
    ws1 = _ws(
        root,
        {
            "a.md": "---\n---\nalpha\n",
            "b.md": "---\n---\nbeta\n",
        },
    )
    backend = SemanticBackend()
    loc = str(tmp_path / "idx.db")
    backend.build(list(ws1.packets.values()), loc)
    ws2 = _ws(root, {"a.md": "---\n---\nalpha\n"})
    stats = backend.build(list(ws2.packets.values()), loc)
    assert stats.packets_removed == 1
    hits = backend.query("beta", loc)
    assert not any(h.packet_id == "b.md" for h in hits)


def test_partial_failure_leaves_prior_batch_committed(tmp_path: Path, monkeypatch):
    import litellm  # type: ignore
    from fakes.provider import fake_aembedding

    ws = _ws(
        tmp_path / "ws",
        {f"f{i}.md": f"---\n---\nbody {i}\n" for i in range(6)},
    )
    backend = SemanticBackend()
    loc = str(tmp_path / "idx.db")

    call = {"n": 0}

    async def _maybe_fail(**kwargs):
        call["n"] += 1
        if call["n"] == 4:
            raise RuntimeError("simulated provider error")
        return await fake_aembedding(**kwargs)

    monkeypatch.setattr(litellm, "aembedding", _maybe_fail)

    with pytest.raises(BackendUnavailableError):
        backend.build(list(ws.packets.values()), loc, options={"batch_size": 1, "concurrency": 1})

    # Restore full provider; previously committed batches should have persisted.
    monkeypatch.setattr(litellm, "aembedding", fake_aembedding)
    stats = backend.build(list(ws.packets.values()), loc)
    total_after_resume = stats.packets_indexed + stats.packets_skipped
    assert total_after_resume == 6
    assert stats.packets_skipped >= 1, "at least one row should have survived the crash"


def test_force_rebuild_ignores_existing(tmp_path: Path):
    ws = _ws(tmp_path / "ws", {"a.md": "---\n---\nalpha\n"})
    backend = SemanticBackend()
    loc = str(tmp_path / "idx.db")
    backend.build(list(ws.packets.values()), loc)
    stats = backend.build(list(ws.packets.values()), loc, options={"force": True})
    assert stats.packets_indexed == 1
    assert stats.packets_skipped == 0
