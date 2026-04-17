from __future__ import annotations

from pathlib import Path

import pytest

from fmql.errors import QueryError
from fmql.query import Query
from fmql.search import TextScanIndex, get_or_create_text_index
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


def test_text_index_matches_body(tmp_path: Path):
    ws = _make_ws(tmp_path)
    idx = TextScanIndex(ws)
    assert list(idx.search("spec")) == ["a.md"]
    assert list(idx.search("Body")) == ["b.md"]  # case-insensitive


def test_text_index_matches_frontmatter(tmp_path: Path):
    ws = _make_ws(tmp_path)
    idx = TextScanIndex(ws)
    # 'alice' appears only in a.md's frontmatter owner field
    assert list(idx.search("alice")) == ["a.md"]
    assert list(idx.search("backend")) == ["c.md"]


def test_text_index_no_match(tmp_path: Path):
    ws = _make_ws(tmp_path)
    idx = TextScanIndex(ws)
    assert list(idx.search("zzzzz")) == []


def test_text_index_empty_query(tmp_path: Path):
    ws = _make_ws(tmp_path)
    idx = TextScanIndex(ws)
    assert list(idx.search("")) == []


def test_workspace_autoregisters_text(tmp_path: Path):
    ws = _make_ws(tmp_path)
    assert "text" not in ws.search_indexes
    ids = Query(ws).search("alice").ids()
    assert ids == ["a.md"]
    assert "text" in ws.search_indexes


def test_user_supplied_index_wins(tmp_path: Path):
    class FakeIndex:
        name = "text"

        def search(self, q):
            return ["b.md"]

    ws = Workspace(tmp_path, search_indexes={"text": FakeIndex()})
    (tmp_path / "a.md").write_text("---\nx: 1\n---\nbody\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("---\nx: 2\n---\nbody\n", encoding="utf-8")
    ws.rescan()
    ids = Query(ws).search("anything").ids()
    assert ids == ["b.md"]


def test_unknown_index_raises(tmp_path: Path):
    ws = _make_ws(tmp_path)
    q = Query(ws).search("foo", index="nope")
    with pytest.raises(QueryError):
        q.ids()


def test_search_composes_with_where(tmp_path: Path):
    ws = _make_ws(tmp_path)
    # a.md has owner=alice and body "Please review the spec."
    ids = Query(ws).where(owner="alice").search("spec").ids()
    assert ids == ["a.md"]
    ids2 = Query(ws).where(owner="bob").search("spec").ids()
    assert ids2 == []


def test_get_or_create_text_index_is_idempotent(tmp_path: Path):
    ws = _make_ws(tmp_path)
    a = get_or_create_text_index(ws)
    b = get_or_create_text_index(ws)
    assert a is b
