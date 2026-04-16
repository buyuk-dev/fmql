from __future__ import annotations

from pathlib import Path

import pytest

from fm.parser import parse, parse_file, serialize_packet

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "project_pm"


def _fixture_files() -> list[Path]:
    return sorted(FIXTURE_ROOT.rglob("*.md"))


@pytest.mark.parametrize(
    "path", _fixture_files(), ids=lambda p: p.relative_to(FIXTURE_ROOT).as_posix()
)
def test_roundtrip_byte_exact_fixture(path: Path) -> None:
    with open(path, "r", encoding="utf-8", newline="") as f:
        original = f.read()
    pkt = parse_file(path, pid=path.relative_to(FIXTURE_ROOT).as_posix())
    assert serialize_packet(pkt) == original


def test_crlf_preserved() -> None:
    text = "---\r\ntitle: x\r\ntags:\r\n  - a\r\n---\r\nbody line 1\r\nbody line 2\r\n"
    pkt = parse(text, pid="x.md", abspath=Path("/x.md"))
    assert pkt.eol == "\r\n"
    assert serialize_packet(pkt) == text


def test_bom_preserved() -> None:
    text = "\ufeff---\ntitle: x\n---\nbody\n"
    pkt = parse(text, pid="x.md", abspath=Path("/x.md"))
    assert pkt.raw_prefix == "\ufeff"
    assert serialize_packet(pkt) == text


def test_no_eof_newline_preserved() -> None:
    text = "---\ntitle: x\n---\nbody"
    pkt = parse(text, pid="x.md", abspath=Path("/x.md"))
    assert not pkt.newline_at_eof
    assert serialize_packet(pkt) == text


def test_empty_frontmatter_block_preserved() -> None:
    text = "---\n---\nbody\n"
    pkt = parse(text, pid="x.md", abspath=Path("/x.md"))
    assert pkt.has_frontmatter
    assert len(pkt.frontmatter) == 0
    assert serialize_packet(pkt) == text


def test_no_frontmatter_file_preserved() -> None:
    text = "plain markdown only\n"
    pkt = parse(text, pid="x.md", abspath=Path("/x.md"))
    assert not pkt.has_frontmatter
    assert serialize_packet(pkt) == text


def test_synthesize_frontmatter_on_no_fm_file() -> None:
    from ruamel.yaml.comments import CommentedMap

    text = "plain body\n"
    pkt = parse(text, pid="x.md", abspath=Path("/x.md"))
    new_fm = CommentedMap()
    new_fm["status"] = "new"
    out = serialize_packet(pkt, frontmatter=new_fm)
    assert out == "---\nstatus: new\n---\nplain body\n"


def test_synthesize_frontmatter_guards_body_starting_with_fence() -> None:
    from ruamel.yaml.comments import CommentedMap

    text = "---\nhorizontal rule markdown\n"
    pkt = parse(text, pid="x.md", abspath=Path("/x.md"))
    assert not pkt.has_frontmatter
    new_fm = CommentedMap()
    new_fm["status"] = "new"
    out = serialize_packet(pkt, frontmatter=new_fm)
    assert out.startswith("---\nstatus: new\n---\n\n---\n")


def test_empty_map_after_mutation_emits_empty_fence_pair() -> None:
    from ruamel.yaml.comments import CommentedMap

    text = "---\nstatus: active\n---\nbody\n"
    pkt = parse(text, pid="x.md", abspath=Path("/x.md"))
    empty = CommentedMap()
    out = serialize_packet(pkt, frontmatter=empty, force_frontmatter=True)
    assert out == "---\n---\nbody\n"
