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


def test_describe_text_default(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["describe", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "packets: 3" in result.stdout
    assert "no-frontmatter: 0" in result.stdout
    assert "status" in result.stdout
    assert "priority" in result.stdout


def test_describe_json_format(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["describe", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["packet_count"] == 3
    assert payload["files_without_frontmatter"] == 0
    names = {f["name"] for f in payload["fields"]}
    assert {"status", "priority"} <= names


def test_describe_top_n(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["describe", str(tmp_path), "--format", "json", "--top", "1"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    status = next(f for f in payload["fields"] if f["name"] == "status")
    assert len(status["top_values"]) == 1
    assert status["top_values"][0]["value"] == "active"


def test_describe_invalid_path(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(app, ["describe", str(tmp_path / "nope")])
    assert result.exit_code != 0
