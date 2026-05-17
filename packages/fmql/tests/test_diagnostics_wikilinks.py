from __future__ import annotations

import io

import typer

from fmql.diagnostics import (
    WikilinkDiagnostic,
    diagnose_wikilinks,
    emit_resolver_warnings,
    format_wikilink_warning,
    maybe_emit_warnings,
)
from fmql.resolvers import RelativePathResolver


def test_diagnose_wikilinks_unresolved(obsidian_vault_ws):
    diags = diagnose_wikilinks(obsidian_vault_ws, ["mentions"])
    unresolved = [d for d in diags if d.kind == "unresolved"]
    assert unresolved == [
        WikilinkDiagnostic(
            kind="unresolved",
            source="Index.md",
            field="mentions",
            raw="Ghost",
            candidates=(),
        )
    ]


def test_diagnose_wikilinks_ambiguous(obsidian_vault_ws):
    # Index.md body has [[Strategy]] AND [[Strategy#vision]] — both ambiguous.
    diags = diagnose_wikilinks(obsidian_vault_ws, ["mentions"])
    ambiguous = [d for d in diags if d.kind == "ambiguous"]
    raws = [d.raw for d in ambiguous]
    assert "Strategy" in raws
    for d in ambiguous:
        assert d.candidates == ("Strategy.md", "alt/Strategy.md")


def test_diagnose_wikilinks_frontmatter_property(make_workspace):
    # related: ["[[Ghost]]"] — dangling wikilink in frontmatter list.
    ws = make_workspace(
        {
            "Hub.md": {"frontmatter": {"related": ["[[Ghost]]"]}, "body": ""},
            "Other.md": {"frontmatter": None, "body": "other\n"},
        }
    )
    diags = diagnose_wikilinks(ws, ["related"])
    assert diags == [WikilinkDiagnostic("unresolved", "Hub.md", "related", "Ghost", ())]


def test_diagnose_wikilinks_no_overlap_for_clean_workspace(paths_refs_ws):
    # paths_refs_ws has no [[]] anywhere; no wikilink diagnostics.
    assert diagnose_wikilinks(paths_refs_ws, ["depends_on", "mentions"]) == []


def test_format_wikilink_warning_unresolved():
    d = WikilinkDiagnostic("unresolved", "Hub.md", "mentions", "Ghost", ())
    text = format_wikilink_warning(d)
    assert "warning:" in text
    assert "[[Ghost]]" in text
    assert "Hub.md" in text
    assert "matches no packet" in text


def test_format_wikilink_warning_ambiguous():
    d = WikilinkDiagnostic(
        "ambiguous",
        "Index.md",
        "mentions",
        "Strategy",
        ("Strategy.md", "alt/Strategy.md"),
    )
    text = format_wikilink_warning(d)
    assert "warning:" in text
    assert "[[Strategy]]" in text
    assert "picked Strategy.md" in text
    assert "alt/Strategy.md" in text


def test_emit_resolver_warnings_includes_wikilink_diagnostics(obsidian_vault_ws, monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(typer, "echo", lambda msg, err=False: buf.write(msg + "\n"))
    emit_resolver_warnings(obsidian_vault_ws, ["mentions"])
    out = buf.getvalue()
    assert "[[Ghost]]" in out
    assert "ambiguous" in out


def test_maybe_emit_warnings_silent_without_diagnose_flag(obsidian_vault_ws, monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(typer, "echo", lambda msg, err=False: buf.write(msg + "\n"))
    maybe_emit_warnings(obsidian_vault_ws, ["mentions"], diagnose=False)
    assert buf.getvalue() == ""


def test_maybe_emit_warnings_fires_with_diagnose(obsidian_vault_ws, monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(typer, "echo", lambda msg, err=False: buf.write(msg + "\n"))
    maybe_emit_warnings(obsidian_vault_ws, ["mentions"], diagnose=True)
    assert "[[Ghost]]" in buf.getvalue()


def test_wikilink_items_skipped_in_field_diagnose(make_workspace):
    # related: ["[[Playbook]]"] should NOT count as "unresolved" against
    # the configured resolver — the wikilink path handles it. Without this
    # skip, diagnose_field would flag "[[Playbook]]" as an unresolved string.
    from fmql.diagnostics import diagnose_field

    ws = make_workspace(
        {
            "Playbook.md": {"frontmatter": None, "body": "playbook\n"},
            "Hub.md": {"frontmatter": {"related": ["[[Playbook]]"]}, "body": ""},
        }
    )
    assert diagnose_field(ws, "related", RelativePathResolver()) is None
