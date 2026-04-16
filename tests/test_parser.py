from __future__ import annotations

from pathlib import Path

import pytest

from fmq.errors import ParseError
from fmq.parser import parse, parse_file


def _fake_path() -> Path:
    return Path("/tmp/fake.md")


def test_parses_simple_frontmatter():
    text = "---\nstatus: active\npriority: 3\n---\nhello\n"
    p = parse(text, pid="x.md", abspath=_fake_path())
    assert p.has_frontmatter is True
    assert p.frontmatter["status"] == "active"
    assert p.frontmatter["priority"] == 3
    assert p.body == "hello\n"
    assert p.eol == "\n"
    assert p.newline_at_eof is True


def test_no_frontmatter():
    text = "just a body\nwith two lines\n"
    p = parse(text, pid="x.md", abspath=_fake_path())
    assert p.has_frontmatter is False
    assert dict(p.frontmatter) == {}
    assert p.body == text


def test_crlf_line_endings():
    text = "---\r\nstatus: active\r\n---\r\nbody\r\n"
    p = parse(text, pid="x.md", abspath=_fake_path())
    assert p.has_frontmatter is True
    assert p.eol == "\r\n"
    assert p.body == "body\r\n"
    assert p.frontmatter["status"] == "active"


def test_bom_prefix_preserved():
    text = "\ufeff---\nstatus: a\n---\nbody\n"
    p = parse(text, pid="x.md", abspath=_fake_path())
    assert p.raw_prefix == "\ufeff"
    assert p.has_frontmatter is True
    assert p.frontmatter["status"] == "a"


def test_empty_frontmatter_block():
    text = "---\n---\nbody\n"
    p = parse(text, pid="x.md", abspath=_fake_path())
    assert p.has_frontmatter is True
    assert dict(p.frontmatter) == {}
    assert p.body == "body\n"


def test_invalid_yaml_raises():
    text = "---\nstatus: : : bad\n---\nbody\n"
    with pytest.raises(ParseError):
        parse(text, pid="x.md", abspath=_fake_path())


def test_parse_file_round_trip(tmp_path: Path):
    p = tmp_path / "a.md"
    p.write_text("---\nx: 1\n---\nbody\n", encoding="utf-8")
    packet = parse_file(p, pid="a.md")
    assert packet.frontmatter["x"] == 1
    assert packet.body == "body\n"


def test_no_closing_fence_treated_as_body():
    text = "---\nstatus: active\nbody without close\n"
    p = parse(text, pid="x.md", abspath=_fake_path())
    assert p.has_frontmatter is False
    assert p.body == text


def test_body_preserved_with_trailing_content():
    text = "---\nx: 1\n---\nline one\n\nline three\n"
    p = parse(text, pid="x.md", abspath=_fake_path())
    assert p.body == "line one\n\nline three\n"
