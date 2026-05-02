from __future__ import annotations

from pathlib import Path

import fmql
from fmql import parse, parse_file, serialize
from fmql.parser import serialize_packet

FIXTURE = Path(__file__).parent / "fixtures" / "project_pm" / "tasks" / "task-1.md"


def test_parser_api_exposed_at_top_level() -> None:
    assert "parse" in fmql.__all__
    assert "parse_file" in fmql.__all__
    assert "serialize" in fmql.__all__


def test_serialize_is_alias_for_serialize_packet() -> None:
    assert serialize is serialize_packet


def test_parse_file_defaults_pid_from_path() -> None:
    pkt = parse_file(FIXTURE)
    assert pkt.id == FIXTURE.as_posix()


def test_parse_file_explicit_pid_still_wins() -> None:
    pkt = parse_file(FIXTURE, pid="custom/id.md")
    assert pkt.id == "custom/id.md"


def test_parse_defaults_pid_from_abspath() -> None:
    text = "---\nstatus: active\n---\nbody\n"
    pkt = parse(text, abspath=Path("/notes/a.md"))
    assert pkt.id == "/notes/a.md"


def test_parse_explicit_pid_still_wins() -> None:
    text = "---\nstatus: active\n---\nbody\n"
    pkt = parse(text, abspath=Path("/notes/a.md"), pid="x")
    assert pkt.id == "x"


def test_top_level_serialize_round_trips_byte_exact() -> None:
    pkt = parse_file(FIXTURE)
    assert serialize(pkt) == FIXTURE.read_text(encoding="utf-8")


def test_standalone_parse_mutate_serialize_flow() -> None:
    text = "---\nstatus: todo\n---\nhello\n"
    pkt = parse(text, abspath=Path("/notes/a.md"))
    pkt.frontmatter["status"] = "done"
    out = serialize(pkt)
    assert "status: done" in out
    assert out.endswith("hello\n")
