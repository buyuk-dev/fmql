from __future__ import annotations

from pathlib import Path

import pytest

from fmql.query import Query
from fmql.search import (
    BackendKindError,
    BackendNotFoundError,
    SearchHit,
    get_backend,
)
from fmql.search.backends.grep import GrepBackend
from fmql.workspace import Workspace


def _make_ws(tmp_path: Path) -> Workspace:
    (tmp_path / "a.md").write_text(
        "---\ntags: [urgent]\nowner: alice\n---\nPlease review the spec.\n",
        encoding="utf-8",
    )
    (tmp_path / "b.md").write_text(
        "---\ntags: [normal]\nowner: bob\n---\nSecond body text.\n",
        encoding="utf-8",
    )
    (tmp_path / "c.md").write_text(
        "---\ntags: [backend]\nowner: charlie\n---\nPrivate notes.\n",
        encoding="utf-8",
    )
    return Workspace(tmp_path)


def test_grep_matches_body(tmp_path: Path):
    ws = _make_ws(tmp_path)
    be = GrepBackend()
    hits = be.query("spec", ws)
    assert [h.packet_id for h in hits] == ["a.md"]
    hits = be.query("Body", ws)
    assert [h.packet_id for h in hits] == ["b.md"]  # case-insensitive by default


def test_grep_matches_frontmatter(tmp_path: Path):
    ws = _make_ws(tmp_path)
    be = GrepBackend()
    assert [h.packet_id for h in be.query("alice", ws)] == ["a.md"]
    assert [h.packet_id for h in be.query("backend", ws)] == ["c.md"]


def test_grep_no_match(tmp_path: Path):
    ws = _make_ws(tmp_path)
    assert GrepBackend().query("zzzzz", ws) == []


def test_grep_empty_query(tmp_path: Path):
    ws = _make_ws(tmp_path)
    assert GrepBackend().query("", ws) == []


def test_grep_hit_is_searchhit(tmp_path: Path):
    ws = _make_ws(tmp_path)
    hits = GrepBackend().query("spec", ws)
    assert all(isinstance(h, SearchHit) for h in hits)
    assert hits[0].score == 1.0
    assert hits[0].snippet is None


def test_registry_resolves_grep():
    be = get_backend("grep")
    assert be.name == "grep"


def test_registry_raises_on_unknown():
    with pytest.raises(BackendNotFoundError):
        get_backend("does-not-exist")


def test_query_search_uses_grep_by_default(tmp_path: Path):
    ws = _make_ws(tmp_path)
    ids = Query(ws).search("alice").ids()
    assert ids == ["a.md"]


def test_query_search_composes_with_where(tmp_path: Path):
    ws = _make_ws(tmp_path)
    assert Query(ws).where(owner="alice").search("spec").ids() == ["a.md"]
    assert Query(ws).where(owner="bob").search("spec").ids() == []


def test_query_search_unknown_backend_raises(tmp_path: Path):
    ws = _make_ws(tmp_path)
    with pytest.raises(BackendNotFoundError):
        Query(ws).search("foo", index="nope").ids()


def test_query_search_indexed_without_location_raises(tmp_path: Path, monkeypatch):
    ws = _make_ws(tmp_path)

    class _FakeIndexed:
        name = "fake-indexed"

        def parse_location(self, location):
            return location

        def default_location(self, workspace):
            return None

        def build(self, packets, location, *, options=None):
            raise AssertionError("unexpected")

        def query(self, text, location, *, k=10, options=None):
            raise AssertionError("unexpected")

        def info(self, location=None):
            from fmql.search import BackendInfo

            return BackendInfo(name=self.name, version="0", kind="indexed")

    from fmql.search import registry

    monkeypatch.setattr(registry, "_cache", {"fake-indexed": _FakeIndexed})
    with pytest.raises(BackendKindError):
        Query(ws).search("x", index="fake-indexed").ids()
    registry.clear_cache()


def test_query_search_indexed_with_default_location(tmp_path: Path, monkeypatch):
    ws = _make_ws(tmp_path)
    seen: dict = {}

    class _FakeIndexed:
        name = "fake-indexed"

        def parse_location(self, location):
            return location

        def default_location(self, workspace):
            return str(workspace.root / ".fmql/fake")

        def build(self, packets, location, *, options=None):
            raise AssertionError("unexpected")

        def query(self, text, location, *, k=10, options=None):
            seen["location"] = location
            seen["k"] = k
            return [SearchHit(packet_id="a.md", score=0.5)]

        def info(self, location=None):
            from fmql.search import BackendInfo

            return BackendInfo(name=self.name, version="0", kind="indexed")

    from fmql.search import registry

    monkeypatch.setattr(registry, "_cache", {"fake-indexed": _FakeIndexed})
    ids = Query(ws).search("x", index="fake-indexed").ids()
    assert ids == ["a.md"]
    assert seen["location"].endswith(".fmql/fake")
    registry.clear_cache()
