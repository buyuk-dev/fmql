from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app


def test_list_backends_text():
    runner = CliRunner()
    result = runner.invoke(app, ["list-backends"])
    assert result.exit_code == 0, result.output
    assert "grep" in result.stdout
    assert "scan" in result.stdout


def test_list_backends_json():
    runner = CliRunner()
    result = runner.invoke(app, ["list-backends", "--format", "json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)
    names = [r["name"] for r in rows]
    assert "grep" in names
    grep_row = next(r for r in rows if r["name"] == "grep")
    assert grep_row["loaded"] is True
    assert grep_row["kind"] == "scan"


def test_index_rejects_scan_backend(tmp_path: Path):
    (tmp_path / "a.md").write_text("---\n---\nbody\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["index", str(tmp_path), "--backend", "grep"])
    assert result.exit_code == 2
    err = result.stderr if result.stderr else result.output
    assert "scan" in err.lower() or "grep" in err.lower()


def test_index_unknown_backend(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(app, ["index", str(tmp_path), "--backend", "nope"])
    assert result.exit_code == 2
