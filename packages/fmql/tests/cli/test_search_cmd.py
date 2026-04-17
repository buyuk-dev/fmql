from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app


def _write_ws(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nowner: alice\n---\nSpec review.\n", encoding="utf-8")
    (root / "b.md").write_text("---\nowner: bob\n---\nSecond body.\n", encoding="utf-8")


def test_search_paths_default(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["search", "spec", "--workspace", str(tmp_path)])
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["a.md"]


def test_search_json_format(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app, ["search", "alice", "--workspace", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    rows = [json.loads(ln) for ln in result.stdout.splitlines() if ln.strip()]
    assert rows == [{"id": "a.md", "score": 1.0, "snippet": None}]


def test_search_rows_format(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app, ["search", "alice", "--workspace", str(tmp_path), "--format", "rows"]
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["a.md\t1.000000\t"]


def test_search_k_limits_results(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["search", "body", "--workspace", str(tmp_path), "-k", "1"])
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1


def test_search_scan_backend_requires_workspace(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["search", "spec"])
    assert result.exit_code == 2
    assert "workspace" in result.stderr.lower() or "workspace" in result.output.lower()


def test_search_unknown_backend_errors(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["search", "x", "--workspace", str(tmp_path), "--backend", "nope"])
    assert result.exit_code == 2


def test_search_option_parsing(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "search",
            "Spec",
            "--workspace",
            str(tmp_path),
            "--option",
            "case_sensitive=true",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["a.md"]


def test_search_option_invalid_format(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app, ["search", "x", "--workspace", str(tmp_path), "--option", "malformed"]
    )
    assert result.exit_code == 2
