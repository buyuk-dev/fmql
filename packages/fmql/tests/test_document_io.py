from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from fmql.document_io import (
    SerializeFormat,
    deserialize_to_markdown,
    from_json,
    from_obj,
    from_yaml,
    to_json,
    to_obj,
    to_yaml,
)
from fmql.errors import FmqlError, ParseError
from fmql.parser import parse, parse_file, serialize_packet


def _parse(text: str):
    return parse(text, abspath=Path("/tmp/x.md"))


def test_to_obj_basic_shape():
    pkt = _parse("---\ntitle: x\n---\nbody\n")
    assert to_obj(pkt) == {"header": {"title": "x"}, "body": "body\n"}


def test_to_obj_no_frontmatter_omits_header():
    pkt = _parse("just a body\n")
    assert to_obj(pkt) == {"body": "just a body\n"}


def test_to_obj_empty_frontmatter_keeps_empty_header():
    pkt = _parse("---\n---\nbody\n")
    assert to_obj(pkt) == {"header": {}, "body": "body\n"}


def test_to_json_pretty_with_trailing_newline():
    pkt = _parse("---\ntitle: x\n---\nbody\n")
    out = to_json(pkt)
    assert out.endswith("\n")
    assert '"title": "x"' in out
    assert '"body": "body\\n"' in out


def test_to_json_dates_render_as_iso_strings():
    pkt = _parse("---\ndue: 2026-04-10\n---\nbody\n")
    out = to_json(pkt)
    assert '"due": "2026-04-10"' in out


def test_to_yaml_emits_block_scalar_for_multiline_body():
    pkt = _parse("---\ntitle: x\n---\nline 1\nline 2\n")
    out = to_yaml(pkt)
    assert "body: |\n" in out
    assert "  line 1\n" in out
    assert "  line 2\n" in out


def test_to_yaml_preserves_native_dates():
    pkt = _parse("---\ndue: 2026-04-10\n---\nbody\n")
    out = to_yaml(pkt)
    # Bare YAML date — no quotes.
    assert "due: 2026-04-10" in out


def test_from_obj_round_trip_basic():
    obj = {"header": {"title": "x"}, "body": "body\n"}
    pkt = from_obj(obj)
    assert pkt.frontmatter["title"] == "x"
    assert pkt.body == "body\n"
    assert serialize_packet(pkt) == "---\ntitle: x\n---\nbody\n"


def test_from_obj_no_header_means_no_fence():
    pkt = from_obj({"body": "plain markdown\n"})
    assert not pkt.has_frontmatter
    assert serialize_packet(pkt) == "plain markdown\n"


def test_from_obj_null_header_means_no_fence():
    pkt = from_obj({"header": None, "body": "plain\n"})
    assert not pkt.has_frontmatter
    assert serialize_packet(pkt) == "plain\n"


def test_from_obj_empty_header_emits_fence_pair():
    pkt = from_obj({"header": {}, "body": "body\n"})
    assert pkt.has_frontmatter
    assert serialize_packet(pkt) == "---\n---\nbody\n"


def test_from_obj_default_body_is_empty_string():
    pkt = from_obj({"header": {"x": 1}})
    assert pkt.body == ""
    assert serialize_packet(pkt) == "---\nx: 1\n---\n"


def test_from_obj_rejects_non_mapping_root():
    with pytest.raises(FmqlError):
        from_obj([1, 2, 3])


def test_from_obj_rejects_non_mapping_header():
    with pytest.raises(FmqlError):
        from_obj({"header": "oops", "body": ""})


def test_from_obj_rejects_non_string_body():
    with pytest.raises(FmqlError):
        from_obj({"header": {}, "body": 42})


def test_from_obj_rejects_unknown_keys():
    with pytest.raises(FmqlError):
        from_obj({"header": {}, "body": "", "extra": True})


def test_from_obj_nested_structures_serialize():
    obj = {
        "header": {
            "title": "x",
            "tags": ["a", "b"],
            "meta": {"owner": "alice", "level": 2},
        },
        "body": "hi\n",
    }
    pkt = from_obj(obj)
    out = serialize_packet(pkt)
    assert "title: x" in out
    assert "tags:" in out
    assert "  - a" in out
    assert "  - b" in out
    assert "meta:" in out
    assert "owner: alice" in out


def test_from_json_invalid_raises_parse_error():
    with pytest.raises(ParseError):
        from_json("{not json")


def test_from_yaml_invalid_raises_parse_error():
    with pytest.raises(ParseError):
        from_yaml("a: : :")


def test_yaml_round_trip_byte_identical_for_canonical_doc():
    src = (
        "---\n"
        "title: Today\n"
        "tags:\n"
        "  - inbox\n"
        "  - urgent\n"
        "priority: 3\n"
        "draft: true\n"
        "due: 2026-05-01\n"
        "meta:\n"
        "  owner: alice\n"
        "---\n"
        "# Today\n"
        "\n"
        "first line\n"
        "second line\n"
    )
    pkt = parse(src, abspath=Path("/tmp/today.md"))
    structured = to_yaml(pkt)
    rebuilt = deserialize_to_markdown(structured, fmt=SerializeFormat.yaml)
    assert rebuilt == src


def test_json_round_trip_preserves_keys_and_body():
    src = "---\n" "title: Today\n" "tags:\n" "  - inbox\n" "priority: 3\n" "---\n" "# Today\n"
    pkt = parse(src, abspath=Path("/tmp/today.md"))
    structured = to_json(pkt)
    rebuilt_text = deserialize_to_markdown(structured, fmt=SerializeFormat.json)
    rebuilt = parse(rebuilt_text, abspath=Path("/tmp/today.md"))
    assert dict(rebuilt.frontmatter) == {"title": "Today", "tags": ["inbox"], "priority": 3}
    assert rebuilt.body == "# Today\n"
    assert list(rebuilt.frontmatter.keys()) == ["title", "tags", "priority"]


def test_json_round_trip_dates_become_strings():
    """Documented JSON limitation: date types do not survive JSON round-trip."""
    src = "---\ndue: 2026-04-10\n---\nbody\n"
    pkt = parse(src, abspath=Path("/tmp/x.md"))
    rebuilt_text = deserialize_to_markdown(to_json(pkt), fmt=SerializeFormat.json)
    rebuilt = parse(rebuilt_text, abspath=Path("/tmp/x.md"))
    assert rebuilt.frontmatter["due"] == "2026-04-10"  # string, not date
    assert not isinstance(rebuilt.frontmatter["due"], date)


def test_json_round_trip_no_frontmatter_doc():
    src = "plain markdown only\n"
    pkt = parse(src, abspath=Path("/tmp/x.md"))
    rebuilt = deserialize_to_markdown(to_json(pkt), fmt=SerializeFormat.json)
    assert rebuilt == src


def test_json_round_trip_empty_body():
    src = "---\nx: 1\n---\n"
    pkt = parse(src, abspath=Path("/tmp/x.md"))
    rebuilt = deserialize_to_markdown(to_json(pkt), fmt=SerializeFormat.json)
    # Round-trips with the same shape — header preserved, body empty.
    rebuilt_pkt = parse(rebuilt, abspath=Path("/tmp/x.md"))
    assert rebuilt_pkt.body == ""
    assert dict(rebuilt_pkt.frontmatter) == {"x": 1}


def test_json_round_trip_empty_frontmatter_block():
    src = "---\n---\nbody\n"
    pkt = parse(src, abspath=Path("/tmp/x.md"))
    rebuilt = deserialize_to_markdown(to_json(pkt), fmt=SerializeFormat.json)
    assert rebuilt == src


def test_round_trip_via_parse_file(tmp_path: Path):
    p = tmp_path / "note.md"
    p.write_text("---\ntitle: x\ntags:\n  - a\n  - b\n---\nbody\n", encoding="utf-8")
    pkt = parse_file(p)
    rebuilt = deserialize_to_markdown(to_yaml(pkt), fmt=SerializeFormat.yaml)
    assert rebuilt == p.read_text(encoding="utf-8")
