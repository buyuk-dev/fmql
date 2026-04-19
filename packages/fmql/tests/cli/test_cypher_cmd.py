from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app


def _write_uuid_refs(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nuuid: a\nblocked_by: b\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nuuid: b\nblocked_by: c\n---\n", encoding="utf-8")
    (root / "c.md").write_text("---\nuuid: c\n---\n", encoding="utf-8")


def _write_cycle_by_path(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nnext: b.md\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nnext: c.md\n---\n", encoding="utf-8")
    (root / "c.md").write_text("---\nnext: a.md\n---\n", encoding="utf-8")


def test_cypher_rows_single_hop(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cypher",
            str(tmp_path),
            "MATCH (a)-[:next]->(b) RETURN a, b",
        ],
    )
    assert result.exit_code == 0, result.output
    rows = sorted(tuple(ln.split("\t")) for ln in result.stdout.splitlines() if ln.strip())
    assert rows == [
        ("a.md", "b.md"),
        ("b.md", "c.md"),
        ("c.md", "a.md"),
    ]


def test_cypher_self_cycle(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cypher",
            str(tmp_path),
            "MATCH (a)-[:next*]->(a) RETURN a",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = sorted(ln for ln in result.stdout.splitlines() if ln.strip())
    assert lines == ["a.md", "b.md", "c.md"]


def test_cypher_count_scalar(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cypher",
            str(tmp_path),
            "MATCH (a)-[:next]->(b) RETURN count(a)",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "3"


def test_cypher_json_format(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cypher",
            str(tmp_path),
            "MATCH (a)-[:next]->(b) RETURN a, b",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    rows = [json.loads(ln) for ln in result.stdout.splitlines() if ln.strip()]
    assert len(rows) == 3
    for row in rows:
        assert row["columns"] == ["a", "b"]
        assert len(row["row"]) == 2


def test_cypher_json_count(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cypher",
            str(tmp_path),
            "MATCH (a)-[:next]->(b) RETURN count(a)",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert payload == {"count": 3}


def test_cypher_parse_error_exits_2(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["cypher", str(tmp_path), "not valid cypher"])
    assert result.exit_code == 2


def test_cypher_unsupported_exits_2(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["cypher", str(tmp_path), "CREATE (a) RETURN a"],
    )
    assert result.exit_code == 2


def test_cypher_reverse_edge_exits_2(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["cypher", str(tmp_path), "MATCH (a)<-[:next]-(b) RETURN a"],
    )
    assert result.exit_code == 2


def test_cypher_zero_rows_emits_resolver_mismatch_hint(tmp_path: Path):
    _write_uuid_refs(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cypher",
            str(tmp_path),
            "MATCH (a)-[:blocked_by]->(b) RETURN a, b",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "hint:" in result.stderr
    assert "blocked_by" in result.stderr
    assert "resolver mismatch" in result.stderr


def test_cypher_zero_rows_hint_suppressed_with_matching_resolver(tmp_path: Path):
    _write_uuid_refs(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cypher",
            str(tmp_path),
            "MATCH (a)-[:blocked_by]->(b) RETURN a, b",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "hint:" not in result.stderr
