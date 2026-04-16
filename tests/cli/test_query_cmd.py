from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fmq.cli.main import app


def _write_ws(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "tasks").mkdir()
    (root / "tasks/a.md").write_text(
        "---\nstatus: active\npriority: 3\n---\nbody\n", encoding="utf-8"
    )
    (root / "tasks/b.md").write_text(
        "---\nstatus: done\npriority: 1\n---\nbody\n", encoding="utf-8"
    )
    (root / "tasks/c.md").write_text(
        "---\nstatus: active\npriority: 1\n---\nbody\n", encoding="utf-8"
    )


def test_query_paths_format(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app, ["query", str(tmp_path), 'status = "active" AND priority > 2']
    )
    assert result.exit_code == 0, result.output
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert lines == ["tasks/a.md"]


def test_query_json_format(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app, ["query", str(tmp_path), "*", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    rows = [json.loads(l) for l in result.stdout.splitlines() if l.strip()]
    assert len(rows) == 3
    ids = sorted(r["id"] for r in rows)
    assert ids == ["tasks/a.md", "tasks/b.md", "tasks/c.md"]
    for r in rows:
        assert "status" in r["frontmatter"]


def test_query_star_prints_all(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", str(tmp_path), "*"])
    assert result.exit_code == 0
    lines = sorted(l for l in result.stdout.splitlines() if l.strip())
    assert lines == ["tasks/a.md", "tasks/b.md", "tasks/c.md"]


def test_query_bad_syntax_exits_nonzero(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", str(tmp_path), "this is not valid"])
    assert result.exit_code == 2


def test_version_cmd():
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"
