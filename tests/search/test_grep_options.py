from __future__ import annotations

from pathlib import Path

import pytest

from fmql.search.backends.grep import GrepBackend
from fmql.workspace import Workspace


def _ws(tmp_path: Path) -> Workspace:
    (tmp_path / "a.md").write_text("---\n---\nHello World\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("---\n---\nhello there\n", encoding="utf-8")
    (tmp_path / "c.md").write_text("---\n---\nfoobar 42\n", encoding="utf-8")
    return Workspace(tmp_path)


def test_case_insensitive_by_default(tmp_path: Path):
    ws = _ws(tmp_path)
    hits = GrepBackend().query("hello", ws)
    assert {h.packet_id for h in hits} == {"a.md", "b.md"}


def test_case_sensitive_option(tmp_path: Path):
    ws = _ws(tmp_path)
    hits = GrepBackend().query("Hello", ws, options={"case_sensitive": True})
    assert {h.packet_id for h in hits} == {"a.md"}


def test_regex_option(tmp_path: Path):
    ws = _ws(tmp_path)
    hits = GrepBackend().query(r"\d+", ws, options={"regex": True})
    assert {h.packet_id for h in hits} == {"c.md"}


def test_regex_with_case_sensitive(tmp_path: Path):
    ws = _ws(tmp_path)
    hits = GrepBackend().query("^Hello", ws, options={"regex": True, "case_sensitive": True})
    assert {h.packet_id for h in hits} == {"a.md"}


def test_invalid_regex_raises(tmp_path: Path):
    ws = _ws(tmp_path)
    with pytest.raises(ValueError):
        GrepBackend().query("[unclosed", ws, options={"regex": True})


def test_unknown_option_raises(tmp_path: Path):
    ws = _ws(tmp_path)
    with pytest.raises(ValueError):
        GrepBackend().query("x", ws, options={"bogus": True})


def test_k_limits_results(tmp_path: Path):
    ws = _ws(tmp_path)
    hits = GrepBackend().query("hello", ws, k=1)
    assert len(hits) == 1
