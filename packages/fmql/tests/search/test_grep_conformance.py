from __future__ import annotations

from pathlib import Path

from fmql.search.backends.grep import GrepBackend
from fmql.search.conformance import (
    assert_scan_empty_query,
    assert_scan_info,
    assert_scan_query_roundtrip,
    assert_scan_respects_k,
    default_workspace_factory,
)


def test_grep_conformance_roundtrip(tmp_path: Path):
    assert_scan_query_roundtrip(GrepBackend(), default_workspace_factory(tmp_path))


def test_grep_conformance_respects_k(tmp_path: Path):
    assert_scan_respects_k(GrepBackend(), default_workspace_factory(tmp_path))


def test_grep_conformance_empty_query(tmp_path: Path):
    assert_scan_empty_query(GrepBackend(), default_workspace_factory(tmp_path))


def test_grep_conformance_info():
    assert_scan_info(GrepBackend())
