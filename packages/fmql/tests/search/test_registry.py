from __future__ import annotations

from importlib.metadata import EntryPoint

import pytest

from fmql.search import BackendNotFoundError, discover_backends, get_backend, registry


class _GoodBackend:
    name = "good"

    def query(self, text, workspace, *, k=10, options=None):
        return []

    def info(self):
        from fmql.search import BackendInfo

        return BackendInfo(name="good", version="0", kind="scan")


def _patch_entry_points(monkeypatch, eps: list[EntryPoint]) -> None:
    registry.clear_cache()

    def _fake_entry_points(*, group: str):
        if group == registry.ENTRY_POINT_GROUP:
            return eps
        return []

    monkeypatch.setattr(registry, "entry_points", _fake_entry_points)


def test_discover_loads_working_plugin(monkeypatch):
    ep = EntryPoint(
        name="good",
        value=f"{__name__}:_GoodBackend",
        group=registry.ENTRY_POINT_GROUP,
    )
    _patch_entry_points(monkeypatch, [ep])
    backends = discover_backends()
    assert "good" in backends
    assert backends["good"] is _GoodBackend


def test_discover_isolates_broken_plugin(monkeypatch, capsys):
    broken = EntryPoint(
        name="broken",
        value="nonexistent.module:Missing",
        group=registry.ENTRY_POINT_GROUP,
    )
    good = EntryPoint(
        name="good",
        value=f"{__name__}:_GoodBackend",
        group=registry.ENTRY_POINT_GROUP,
    )
    _patch_entry_points(monkeypatch, [broken, good])
    backends = discover_backends()
    assert "good" in backends
    assert "broken" not in backends
    stderr = capsys.readouterr().err
    assert "broken" in stderr


def test_get_backend_instantiates(monkeypatch):
    ep = EntryPoint(
        name="good",
        value=f"{__name__}:_GoodBackend",
        group=registry.ENTRY_POINT_GROUP,
    )
    _patch_entry_points(monkeypatch, [ep])
    be = get_backend("good")
    assert isinstance(be, _GoodBackend)


def test_get_backend_raises_with_available_list(monkeypatch):
    ep = EntryPoint(
        name="good",
        value=f"{__name__}:_GoodBackend",
        group=registry.ENTRY_POINT_GROUP,
    )
    _patch_entry_points(monkeypatch, [ep])
    with pytest.raises(BackendNotFoundError) as exc:
        get_backend("missing")
    assert "good" in str(exc.value)


def test_clear_cache_allows_reinspection(monkeypatch):
    _patch_entry_points(monkeypatch, [])
    assert discover_backends() == {}
    ep = EntryPoint(
        name="good",
        value=f"{__name__}:_GoodBackend",
        group=registry.ENTRY_POINT_GROUP,
    )
    _patch_entry_points(monkeypatch, [ep])
    assert "good" in discover_backends()
