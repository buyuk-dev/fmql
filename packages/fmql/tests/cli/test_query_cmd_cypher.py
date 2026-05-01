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
        ["query", "MATCH (a)-[:next]->(b) RETURN a, b", "-w", str(tmp_path)],
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
        ["query", "MATCH (a)-[:next*]->(a) RETURN a", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    lines = sorted(ln for ln in result.stdout.splitlines() if ln.strip())
    assert lines == ["a.md", "b.md", "c.md"]


def test_cypher_count_scalar(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (a)-[:next]->(b) RETURN count(a)", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "3"


def test_cypher_defaults_workspace_to_cwd(tmp_path: Path, monkeypatch):
    _write_cycle_by_path(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", "MATCH (a)-[:next]->(b) RETURN count(a)"])
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "3"


def test_cypher_json_format(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (a)-[:next]->(b) RETURN a, b",
            "-w",
            str(tmp_path),
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
            "query",
            "MATCH (a)-[:next]->(b) RETURN count(a)",
            "-w",
            str(tmp_path),
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
    result = runner.invoke(app, ["query", "not valid cypher", "-w", str(tmp_path)])
    assert result.exit_code == 2


def test_cypher_unsupported_exits_2(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "CREATE (a) RETURN a", "-w", str(tmp_path)],
    )
    assert result.exit_code == 2


def test_cypher_reverse_edge_exits_2(tmp_path: Path):
    _write_cycle_by_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (a)<-[:next]-(b) RETURN a", "-w", str(tmp_path)],
    )
    assert result.exit_code == 2


def test_cypher_zero_rows_emits_resolver_warning(tmp_path: Path):
    _write_uuid_refs(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (a)-[:blocked_by]->(b) RETURN a, b",
            "-w",
            str(tmp_path),
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "warning:" in result.stderr
    assert "blocked_by" in result.stderr


def test_cypher_warning_suppressed_with_matching_resolver(tmp_path: Path):
    _write_uuid_refs(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (a)-[:blocked_by]->(b) RETURN a, b",
            "-w",
            str(tmp_path),
            "--resolver",
            "uuid",
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.stderr


def test_cypher_no_diagnose_flag_is_silent(tmp_path: Path):
    _write_uuid_refs(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (a)-[:blocked_by]->(b) RETURN a, b",
            "-w",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.stderr


def test_cypher_diagnose_via_workspace_md(tmp_path: Path):
    _write_uuid_refs(tmp_path)
    (tmp_path / "WORKSPACE.md").write_text("---\nfmql:\n  diagnose: true\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (a)-[:blocked_by]->(b) RETURN a, b",
            "-w",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" in result.stderr


def _write_status_packets(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nuuid: a\nstatus: old\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nuuid: b\nstatus: old\n---\n", encoding="utf-8")
    (root / "c.md").write_text("---\nuuid: c\nstatus: new\n---\n", encoding="utf-8")


def test_cypher_with_set_writes_files(tmp_path: Path):
    _write_status_packets(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.status = "old" SET t.status = "archived"',
            "-w",
            str(tmp_path),
            "--yes",
        ],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "archived" in (tmp_path / "a.md").read_text(encoding="utf-8")
    assert "archived" in (tmp_path / "b.md").read_text(encoding="utf-8")
    assert "new" in (tmp_path / "c.md").read_text(encoding="utf-8")


def test_cypher_with_set_dry_run_does_not_write(tmp_path: Path):
    _write_status_packets(tmp_path)
    before = (tmp_path / "a.md").read_text(encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.status = "old" SET t.status = "archived"',
            "-w",
            str(tmp_path),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "a.md").read_text(encoding="utf-8") == before


def test_cypher_set_with_return_runs_both(tmp_path: Path):
    _write_status_packets(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.status = "old" SET t.status = "archived" RETURN t',
            "-w",
            str(tmp_path),
            "--yes",
        ],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    pids = sorted(ln for ln in result.stdout.splitlines() if ln.strip())
    assert pids == ["a.md", "b.md"]
    assert "archived" in (tmp_path / "a.md").read_text(encoding="utf-8")
