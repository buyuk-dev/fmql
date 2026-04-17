"""Reusable conformance tests for third-party search backends.

Import the relevant `assert_*` helpers in your test module and drive them with
your backend instance and a workspace factory. Each helper encapsulates one
invariant from `docs/plugins_arch.md` so plugin authors don't need to rewrite
the same tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from fmql.search.errors import IndexVersionError
from fmql.search.protocol import IndexedSearch, ScanSearch
from fmql.search.types import BackendInfo, SearchHit
from fmql.workspace import Workspace

WorkspaceFactory = Callable[[dict[str, str]], Workspace]
"""Build a Workspace from {relative_path: full_markdown_content}."""


def default_workspace_factory(tmp_path: Path) -> WorkspaceFactory:
    """Return a factory that materialises files under tmp_path and builds a Workspace."""

    def _make(files: dict[str, str]) -> Workspace:
        for path in list(tmp_path.iterdir()):
            if path.is_file():
                path.unlink()
        for rel, content in files.items():
            f = tmp_path / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")
        return Workspace(tmp_path)

    return _make


# ---------------------------------------------------------------------------
# Scan-backend conformance
# ---------------------------------------------------------------------------


def assert_scan_query_roundtrip(backend: ScanSearch, make_ws: WorkspaceFactory) -> None:
    ws = make_ws(
        {
            "a.md": "---\nowner: alice\n---\nSpec review.\n",
            "b.md": "---\nowner: bob\n---\nSecond body.\n",
        }
    )
    hits = backend.query("Spec", ws, k=10)
    assert all(isinstance(h, SearchHit) for h in hits), "query() must return SearchHit instances"
    assert [h.packet_id for h in hits] == ["a.md"]


def assert_scan_respects_k(backend: ScanSearch, make_ws: WorkspaceFactory) -> None:
    ws = make_ws(
        {
            "a.md": "---\n---\nmatch\n",
            "b.md": "---\n---\nmatch\n",
            "c.md": "---\n---\nmatch\n",
        }
    )
    hits = backend.query("match", ws, k=2)
    assert len(hits) <= 2


def assert_scan_empty_query(backend: ScanSearch, make_ws: WorkspaceFactory) -> None:
    ws = make_ws({"a.md": "---\n---\nbody\n"})
    assert backend.query("", ws) == []


def assert_scan_info(backend: ScanSearch) -> None:
    info = backend.info()
    assert isinstance(info, BackendInfo)
    assert info.kind == "scan"
    assert info.name == backend.name


# ---------------------------------------------------------------------------
# Indexed-backend conformance
# ---------------------------------------------------------------------------


def assert_indexed_build_then_query(
    backend: IndexedSearch, make_ws: WorkspaceFactory, location: str
) -> None:
    ws = make_ws(
        {
            "a.md": "---\nowner: alice\n---\nSpec review.\n",
            "b.md": "---\nowner: bob\n---\nSecond body.\n",
        }
    )
    backend.parse_location(location)
    stats = backend.build(list(ws.packets.values()), location)
    assert stats.packets_indexed >= 1
    hits = backend.query("Spec", location, k=10)
    assert all(isinstance(h, SearchHit) for h in hits)


def assert_indexed_build_is_idempotent(
    backend: IndexedSearch, make_ws: WorkspaceFactory, location: str
) -> None:
    ws = make_ws({"a.md": "---\n---\nbody\n"})
    backend.build(list(ws.packets.values()), location)
    first_hits = backend.query("body", location)
    backend.build(list(ws.packets.values()), location)
    second_hits = backend.query("body", location)
    assert {h.packet_id for h in first_hits} == {h.packet_id for h in second_hits}


def assert_indexed_handles_deletion(
    backend: IndexedSearch, make_ws: WorkspaceFactory, location: str
) -> None:
    ws = make_ws({"a.md": "---\n---\nalpha\n", "b.md": "---\n---\nbeta\n"})
    backend.build(list(ws.packets.values()), location)
    ws2 = make_ws({"a.md": "---\n---\nalpha\n"})
    backend.build(list(ws2.packets.values()), location)
    hits = backend.query("beta", location)
    assert not any(h.packet_id == "b.md" for h in hits), "build() must reflect deletions on rebuild"


def assert_indexed_info_tolerates_missing(backend: IndexedSearch, missing_location: str) -> None:
    info = backend.info(missing_location)
    assert isinstance(info, BackendInfo)
    assert info.kind == "indexed"


def assert_indexed_version_mismatch_raises(
    backend: IndexedSearch, corrupt: Callable[[str], None], location: str
) -> None:
    """Fabricate an incompatible on-disk state (via `corrupt`) and expect IndexVersionError."""
    corrupt(location)
    import pytest

    with pytest.raises(IndexVersionError):
        backend.query("anything", location)
