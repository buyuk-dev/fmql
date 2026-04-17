from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app


def _ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "a.md").write_text(
        "---\nstatus: active\npriority: 3\ntags:\n  - x\nflagged: false\n---\nbody a\n",
        encoding="utf-8",
    )
    (root / "b.md").write_text("---\nstatus: done\npriority: 1\n---\nbody b\n", encoding="utf-8")
    return root


# ---- set ----


def test_set_single_file_dry_run(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["set", str(root / "a.md"), "status=escalated", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "+status: escalated" in result.stdout
    # Not written.
    assert "status: active" in (root / "a.md").read_text()


def test_set_writes_with_yes(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["set", str(root / "a.md"), "status=escalated", "--yes"])
    assert result.exit_code == 0, result.output
    assert "status: escalated" in (root / "a.md").read_text()


def test_set_coerces_int_bool_date(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "set",
            str(root / "a.md"),
            "priority=7",
            "flagged=true",
            "due=2026-05-01",
            "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    text = (root / "a.md").read_text()
    assert "priority: 7" in text
    assert "flagged: true" in text
    assert "due: 2026-05-01" in text


def test_set_multiple_files(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["set", str(root / "a.md"), str(root / "b.md"), "status=reviewed", "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert "status: reviewed" in (root / "a.md").read_text()
    assert "status: reviewed" in (root / "b.md").read_text()


def test_set_on_no_frontmatter_creates_fence(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    (root / "c.md").write_text("plain body\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["set", str(root / "c.md"), "status=new", "--yes"])
    assert result.exit_code == 0, result.output
    text = (root / "c.md").read_text()
    assert text == "---\nstatus: new\n---\nplain body\n"


def test_set_requires_assignments(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["set", str(root / "a.md"), "--dry-run"])
    assert result.exit_code == 2


# ---- remove ----


def test_remove_field(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["remove", str(root / "a.md"), "tags", "--yes"])
    assert result.exit_code == 0, result.output
    assert "tags:" not in (root / "a.md").read_text()


def test_remove_absent_is_noop(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    before = (root / "a.md").read_text()
    runner = CliRunner()
    result = runner.invoke(app, ["remove", str(root / "a.md"), "missing", "--yes"])
    assert result.exit_code == 0, result.output
    assert (root / "a.md").read_text() == before


# ---- rename ----


def test_rename_field(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["rename", str(root / "a.md"), "status=state", "--yes"])
    assert result.exit_code == 0, result.output
    text = (root / "a.md").read_text()
    assert "state: active" in text
    assert "status:" not in text


def test_rename_collision_errors(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["rename", str(root / "a.md"), "status=priority", "--yes"])
    # Collision → plan applies the one that succeeds, errors reported, exit 1.
    assert result.exit_code == 1
    assert "already exists" in result.stderr


# ---- append ----


def test_append_to_list(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["append", str(root / "a.md"), "tags=y", "--yes"])
    assert result.exit_code == 0, result.output
    text = (root / "a.md").read_text()
    assert "  - x" in text
    assert "  - y" in text


def test_append_creates_list(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["append", str(root / "b.md"), "tags=first", "--yes"])
    assert result.exit_code == 0, result.output
    assert "  - first" in (root / "b.md").read_text()


def test_append_type_conflict_errors(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["append", str(root / "a.md"), "status=x", "--yes"])
    assert result.exit_code == 1
    assert "cannot append" in result.stderr


# ---- toggle ----


def test_toggle_bool(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["toggle", str(root / "a.md"), "flagged", "--yes"])
    assert result.exit_code == 0, result.output
    assert "flagged: true" in (root / "a.md").read_text()


def test_toggle_non_bool_errors(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["toggle", str(root / "a.md"), "status", "--yes"])
    assert result.exit_code == 1
    assert "non-bool" in result.stderr


def test_toggle_absent_errors(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["toggle", str(root / "a.md"), "missing", "--yes"])
    assert result.exit_code == 1
    assert "absent" in result.stderr


# ---- stdin / pipe ----


def test_set_via_stdin_path_mode(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["set", "status=reviewed", "--workspace", str(root), "--yes"],
        input="a.md\nb.md\n",
    )
    assert result.exit_code == 0, result.output
    assert "status: reviewed" in (root / "a.md").read_text()
    assert "status: reviewed" in (root / "b.md").read_text()


def test_set_via_stdin_jsonl_mode(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    inp = '{"id": "a.md"}\n{"id": "b.md"}\n'
    result = runner.invoke(
        app,
        ["set", "status=reviewed", "--workspace", str(root), "--yes"],
        input=inp,
    )
    assert result.exit_code == 0, result.output
    assert "status: reviewed" in (root / "a.md").read_text()
    assert "status: reviewed" in (root / "b.md").read_text()


def test_set_stdin_dash_token_explicit(tmp_path: Path) -> None:
    root = _ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["set", "-", "status=reviewed", "--workspace", str(root), "--yes"],
        input="a.md\n",
    )
    assert result.exit_code == 0, result.output
    assert "status: reviewed" in (root / "a.md").read_text()


def test_jsonl_without_workspace_errors(tmp_path: Path) -> None:
    _ws(tmp_path)
    runner = CliRunner()
    inp = '{"id": "a.md"}\n'
    result = runner.invoke(app, ["set", "status=x", "--yes"], input=inp)
    assert result.exit_code == 2
    assert "JSONL" in result.stderr or "workspace" in result.stderr
