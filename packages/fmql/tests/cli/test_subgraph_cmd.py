from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app


def _write_blocked_ws(root: Path) -> None:
    """a (uuid=a) → b (uuid=b, blocked_by=a) → c (uuid=c, blocked_by=b)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nuuid: a\n---\nA\n", encoding="utf-8")
    (root / "b.md").write_text("---\nuuid: b\nblocked_by: a\n---\nB\n", encoding="utf-8")
    (root / "c.md").write_text("---\nuuid: c\nblocked_by: b\n---\nC\n", encoding="utf-8")


def test_subgraph_forward_single_hop(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--direction",
            "reverse",
            "--depth",
            "1",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert sorted(n["id"] for n in payload["nodes"]) == ["c.md"]
    assert payload["edges"] == []


def test_subgraph_forward_depth_star_full_closure(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    ids = sorted(n["id"] for n in payload["nodes"])
    assert ids == ["a.md", "b.md", "c.md"]
    edges = [(e["source"], e["target"], e["field"]) for e in payload["edges"]]
    assert ("c.md", "b.md", "blocked_by") in edges
    assert ("b.md", "a.md", "blocked_by") in edges


def test_subgraph_reverse_direction(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "a"',
            "--follow",
            "blocked_by",
            "--direction",
            "reverse",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    ids = sorted(n["id"] for n in payload["nodes"])
    assert ids == ["a.md", "b.md", "c.md"]
    edges = [(e["source"], e["target"], e["field"]) for e in payload["edges"]]
    assert ("b.md", "a.md", "blocked_by") in edges
    assert ("c.md", "b.md", "blocked_by") in edges


def test_subgraph_ids_only(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--ids-only",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    for node in payload["nodes"]:
        assert set(node.keys()) == {"id"}


def test_subgraph_no_include_origin(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--no-include-origin",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    ids = sorted(n["id"] for n in payload["nodes"])
    assert ids == ["a.md", "b.md"]


def test_subgraph_resolver_mismatch_emits_hint(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert payload["edges"] == []
    assert "hint:" in result.stderr
    assert "blocked_by" in result.stderr


def test_subgraph_invalid_depth_exits_2(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--depth",
            "foo",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 2
