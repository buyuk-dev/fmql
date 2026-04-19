from __future__ import annotations

from fmql.diagnostics import diagnose_resolver_mismatch
from fmql.resolvers import RelativePathResolver, UuidResolver


def test_all_populated_and_resolved_returns_none(paths_refs_ws):
    ws = paths_refs_ws
    hint = diagnose_resolver_mismatch(ws, "depends_on", RelativePathResolver())
    assert hint is None


def test_all_populated_none_resolve_returns_hint(cycles_ws):
    ws = cycles_ws
    hint = diagnose_resolver_mismatch(ws, "blocked_by", RelativePathResolver())
    assert hint is not None
    assert "blocked_by" in hint
    assert "3 packet(s)" in hint
    assert "resolver mismatch" in hint


def test_field_absent_returns_none(paths_refs_ws):
    ws = paths_refs_ws
    hint = diagnose_resolver_mismatch(ws, "nonexistent_field", RelativePathResolver())
    assert hint is None


def test_uuid_resolver_resolves_cycles_ws(cycles_ws):
    ws = cycles_ws
    hint = diagnose_resolver_mismatch(ws, "blocked_by", UuidResolver())
    assert hint is None


def test_partial_resolve_returns_none(make_workspace):
    spec = {
        "a.md": {
            "frontmatter": {"uuid": "a", "refs": ["b.md", "nope.md"]},
            "body": "a\n",
        },
        "b.md": {
            "frontmatter": {"uuid": "b"},
            "body": "b\n",
        },
    }
    ws = make_workspace(spec)
    hint = diagnose_resolver_mismatch(ws, "refs", RelativePathResolver())
    assert hint is None
