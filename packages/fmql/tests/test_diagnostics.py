from __future__ import annotations

import io

import typer

from fmql.diagnostics import (
    diagnose_field,
    emit_resolver_warnings,
    format_warning,
)
from fmql.resolvers import IdResolver, RelativePathResolver, UuidResolver


def test_all_resolved_returns_none(paths_refs_ws):
    ws = paths_refs_ws
    assert diagnose_field(ws, "depends_on", RelativePathResolver()) is None


def test_field_absent_returns_none(paths_refs_ws):
    ws = paths_refs_ws
    assert diagnose_field(ws, "nonexistent_field", RelativePathResolver()) is None


def test_all_unresolved_returns_mismatch(cycles_ws):
    ws = cycles_ws
    mismatch = diagnose_field(ws, "blocked_by", RelativePathResolver())
    assert mismatch is not None
    assert mismatch.field == "blocked_by"
    assert mismatch.populated_packets == 3
    assert mismatch.total_values == 3
    assert mismatch.resolved_values == 0


def test_uuid_resolver_resolves_cycles_ws(cycles_ws):
    ws = cycles_ws
    assert diagnose_field(ws, "blocked_by", UuidResolver()) is None


def test_partial_resolve_triggers_mismatch(make_workspace):
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
    mismatch = diagnose_field(ws, "refs", RelativePathResolver())
    assert mismatch is not None
    assert mismatch.populated_packets == 1
    assert mismatch.total_values == 2
    assert mismatch.resolved_values == 1
    assert "nope.md" in mismatch.sample_unresolved


def test_int_only_field_suggests_id_resolver(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"uuid": "a"}, "body": ""},
        "b.md": {"frontmatter": {"uuid": "b", "depends_on": [1, 2, 3]}, "body": ""},
    }
    ws = make_workspace(spec)
    mismatch = diagnose_field(ws, "depends_on", UuidResolver())
    assert mismatch is not None
    assert mismatch.suggested_resolver == "id"
    assert mismatch.resolver_name == "uuid"


def test_format_warning_includes_sample_and_fix(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"id": "1"}, "body": ""},
        "b.md": {"frontmatter": {"id": "2", "depends_on": [1, 17]}, "body": ""},
    }
    ws = make_workspace(spec)
    mismatch = diagnose_field(ws, "depends_on", UuidResolver())
    assert mismatch is not None
    text = format_warning(mismatch)
    assert text.startswith("warning:")
    assert "depends_on" in text
    assert "sample:" in text
    assert "fmql:" in text
    assert "depends_on: id" in text


def test_no_fix_block_when_already_using_suggested_resolver(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"uuid": "a"}, "body": ""},
        "b.md": {
            "frontmatter": {"uuid": "b", "refs": ["nope-a", "nope-b"]},
            "body": "",
        },
    }
    ws = make_workspace(spec)
    mismatch = diagnose_field(ws, "refs", UuidResolver())
    assert mismatch is not None
    assert mismatch.suggested_resolver == "uuid"
    text = format_warning(mismatch)
    assert "fix:" not in text


def test_emit_resolver_warnings_dedups(make_workspace, monkeypatch):
    spec = {
        "a.md": {"frontmatter": {"uuid": "a", "refs": ["nope"]}, "body": ""},
    }
    ws = make_workspace(spec)
    buf = io.StringIO()
    monkeypatch.setattr(typer, "echo", lambda msg, err=False: buf.write(msg + "\n"))
    emit_resolver_warnings(ws, ["refs", "refs"], resolver=UuidResolver())
    assert buf.getvalue().count("warning:") == 1


def test_emit_resolver_warnings_no_output_when_clean(paths_refs_ws, monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(typer, "echo", lambda msg, err=False: buf.write(msg + "\n"))
    emit_resolver_warnings(paths_refs_ws, ["depends_on"], resolver=RelativePathResolver())
    assert buf.getvalue() == ""


def test_id_resolver_resolves_int_values(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"id": 1}, "body": ""},
        "b.md": {"frontmatter": {"id": 17}, "body": ""},
        "c.md": {"frontmatter": {"id": 3, "depends_on": [1, 17]}, "body": ""},
    }
    ws = make_workspace(spec)
    assert diagnose_field(ws, "depends_on", IdResolver()) is None
