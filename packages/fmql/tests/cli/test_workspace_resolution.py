from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app


def test_query_w_missing_path_errors_cleanly(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(app, ["query", "MATCH (t) RETURN t", "-w", str(tmp_path / "nope")])
    assert result.exit_code == 2
    assert "workspace not found" in result.stderr or "workspace not found" in result.output


def test_query_w_file_errors_cleanly(tmp_path: Path):
    f = tmp_path / "x.md"
    f.write_text("---\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["query", "MATCH (t) RETURN t", "-w", str(f)])
    assert result.exit_code == 2
    msg = result.stderr or result.output
    assert "expected directory" in msg or "got file" in msg


def test_query_w_omitted_uses_cwd(tmp_path: Path, monkeypatch):
    (tmp_path / "a.md").write_text("---\nstatus: todo\n---\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", "MATCH (t) RETURN t"])
    assert result.exit_code == 0, result.output
    assert "a.md" in result.stdout


def test_describe_w_file_errors_cleanly(tmp_path: Path):
    f = tmp_path / "x.md"
    f.write_text("---\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["describe", "-w", str(f)])
    assert result.exit_code == 2


def test_update_w_missing_path_errors_cleanly(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "update",
            'MATCH (t) SET t.x = "y"',
            "-w",
            str(tmp_path / "nope"),
            "--yes",
        ],
    )
    assert result.exit_code == 2


def test_legacy_set_command_no_longer_exists(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(app, ["set", "foo.md", "status=done"])
    assert result.exit_code != 0
    msg = result.stderr or result.output
    assert "No such command" in msg or "no such command" in msg.lower()


def test_legacy_append_command_no_longer_exists():
    runner = CliRunner()
    result = runner.invoke(app, ["append", "foo.md", "tags=x"])
    assert result.exit_code != 0


def test_legacy_remove_command_no_longer_exists():
    runner = CliRunner()
    result = runner.invoke(app, ["remove", "foo.md", "field=x"])
    assert result.exit_code != 0


def test_legacy_rename_command_no_longer_exists():
    runner = CliRunner()
    result = runner.invoke(app, ["rename", "foo.md", "old=new"])
    assert result.exit_code != 0


def test_legacy_toggle_command_no_longer_exists():
    runner = CliRunner()
    result = runner.invoke(app, ["toggle", "foo.md", "done"])
    assert result.exit_code != 0
