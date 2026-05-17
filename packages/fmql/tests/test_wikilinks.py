from __future__ import annotations

from fmql.wikilinks import (
    WikilinkResolution,
    WikilinkTarget,
    match_whole_value_wikilink,
    parse_body_wikilinks,
    resolve_wikilink,
)


def test_parse_single_body_wikilink():
    links = parse_body_wikilinks("see [[Strategy]] for details")
    assert links == [WikilinkTarget(raw="Strategy", target="Strategy")]


def test_parse_multiple_body_wikilinks():
    body = "first [[A]] then [[B]] and finally [[C]]"
    targets = [link.target for link in parse_body_wikilinks(body)]
    assert targets == ["A", "B", "C"]


def test_parse_alias_form_keeps_target_drops_alias():
    [link] = parse_body_wikilinks("see [[Strategy|the playbook]]")
    assert link.target == "Strategy"


def test_parse_ignores_embedded_wikilink():
    # Obsidian embed syntax is out of scope for graph edges in v1.
    assert parse_body_wikilinks("look here: ![[Diagram.png]]") == []


def test_parse_strips_heading_fragment():
    [link] = parse_body_wikilinks("[[Strategy#Roadmap]]")
    assert link.target == "Strategy"
    assert link.raw == "Strategy#Roadmap"


def test_parse_strips_block_fragment():
    [link] = parse_body_wikilinks("[[Strategy^block-7]]")
    assert link.target == "Strategy"


def test_parse_path_form_preserves_slash():
    [link] = parse_body_wikilinks("[[business/notes/Strategy]]")
    assert link.target == "business/notes/Strategy"


def test_parse_ignores_empty_target():
    assert parse_body_wikilinks("ghost [[]] link") == []


def test_match_whole_value_scalar():
    assert match_whole_value_wikilink("[[Strategy]]") == WikilinkTarget(
        raw="Strategy", target="Strategy"
    )


def test_match_whole_value_with_surrounding_whitespace():
    assert match_whole_value_wikilink("  [[Strategy]]\n") == WikilinkTarget(
        raw="Strategy", target="Strategy"
    )


def test_match_whole_value_rejects_partial():
    assert match_whole_value_wikilink("prefix [[Strategy]] suffix") is None


def test_match_whole_value_rejects_non_string():
    assert match_whole_value_wikilink(None) is None
    assert match_whole_value_wikilink(42) is None
    assert match_whole_value_wikilink(["[[X]]"]) is None


def test_match_whole_value_alias_form():
    [hit] = [match_whole_value_wikilink("[[Strategy|the playbook]]")]
    assert hit is not None
    assert hit.target == "Strategy"


def test_resolve_basename_single_hit(make_workspace):
    ws = make_workspace(
        {
            "notes/Strategy.md": {"frontmatter": None, "body": "strategy body\n"},
            "notes/Other.md": {"frontmatter": None, "body": "other body\n"},
        }
    )
    resolution = resolve_wikilink(WikilinkTarget("Strategy", "Strategy"), ws)
    assert resolution == WikilinkResolution(
        target="notes/Strategy.md", candidates=("notes/Strategy.md",)
    )


def test_resolve_basename_ambiguous_alphabetical_pick(make_workspace):
    ws = make_workspace(
        {
            "b/Strategy.md": {"frontmatter": None, "body": "b strategy\n"},
            "a/Strategy.md": {"frontmatter": None, "body": "a strategy\n"},
        }
    )
    resolution = resolve_wikilink(WikilinkTarget("Strategy", "Strategy"), ws)
    assert resolution.target == "a/Strategy.md"
    assert resolution.candidates == ("a/Strategy.md", "b/Strategy.md")


def test_resolve_path_form_with_md(make_workspace):
    ws = make_workspace(
        {
            "business/notes/Strategy.md": {"frontmatter": None, "body": "strategy\n"},
        }
    )
    resolution = resolve_wikilink(
        WikilinkTarget("business/notes/Strategy", "business/notes/Strategy"), ws
    )
    assert resolution.target == "business/notes/Strategy.md"


def test_resolve_path_form_with_explicit_md_suffix(make_workspace):
    ws = make_workspace(
        {
            "business/notes/Strategy.md": {"frontmatter": None, "body": "strategy\n"},
        }
    )
    resolution = resolve_wikilink(
        WikilinkTarget("business/notes/Strategy.md", "business/notes/Strategy.md"), ws
    )
    assert resolution.target == "business/notes/Strategy.md"


def test_resolve_missing_basename(make_workspace):
    ws = make_workspace(
        {
            "Strategy.md": {"frontmatter": None, "body": "strategy\n"},
        }
    )
    resolution = resolve_wikilink(WikilinkTarget("Ghost", "Ghost"), ws)
    assert resolution == WikilinkResolution(target=None, candidates=())


def test_resolve_missing_path_form(make_workspace):
    ws = make_workspace(
        {
            "Strategy.md": {"frontmatter": None, "body": "strategy\n"},
        }
    )
    resolution = resolve_wikilink(WikilinkTarget("notes/Ghost", "notes/Ghost"), ws)
    assert resolution == WikilinkResolution(target=None, candidates=())
