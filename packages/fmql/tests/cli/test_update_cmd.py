from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app


def _write_id_refs(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "WORKSPACE.md").write_text(
        "---\nfmql:\n  resolvers:\n    depends_on: id\n---\n", encoding="utf-8"
    )
    (root / "a.md").write_text("---\nid: 1\nslug: alpha\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nid: 8\nslug: bravo\n---\n", encoding="utf-8")
    (root / "c.md").write_text(
        "---\nid: 17\nslug: charlie\ndepends_on:\n  - 1\n  - 8\n---\n", encoding="utf-8"
    )


def test_update_migrates_ids_to_slugs(tmp_path: Path):
    _write_id_refs(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "update",
            'MATCH (t) SET t.depends_on = field(resolve(t.depends_on, "id"), "slug")',
            "-w",
            str(tmp_path),
            "--yes",
        ],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    contents = (tmp_path / "c.md").read_text(encoding="utf-8")
    assert "alpha" in contents
    assert "bravo" in contents
    assert "- 1\n" not in contents
    assert "- 8\n" not in contents


def test_update_dry_run_does_not_write(tmp_path: Path):
    _write_id_refs(tmp_path)
    before = (tmp_path / "c.md").read_text(encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "update",
            'MATCH (t) WHERE t.id = 17 SET t.label = "C"',
            "-w",
            str(tmp_path),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "c.md").read_text(encoding="utf-8") == before


def test_update_without_set_or_remove_errors(tmp_path: Path):
    _write_id_refs(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["update", "MATCH (t) RETURN t", "-w", str(tmp_path)],
    )
    assert result.exit_code == 2
    assert "SET" in result.stderr or "SET" in result.output


def test_update_with_return_errors(tmp_path: Path):
    _write_id_refs(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["update", "MATCH (t) SET t.x = 1 RETURN t", "-w", str(tmp_path)],
    )
    assert result.exit_code == 2


def test_update_defaults_workspace_to_cwd(tmp_path: Path, monkeypatch):
    _write_id_refs(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["update", 'MATCH (t) WHERE t.id = 1 SET t.label = "first"', "--yes"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "first" in (tmp_path / "a.md").read_text(encoding="utf-8")


def test_update_append_operator(tmp_path: Path):
    (tmp_path / "x.md").write_text("---\ntags:\n  - a\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["update", 'MATCH (t) SET t.tags += "b"', "-w", str(tmp_path), "--yes"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    text = (tmp_path / "x.md").read_text(encoding="utf-8")
    assert "- a" in text
    assert "- b" in text


def test_update_remove_clause(tmp_path: Path):
    (tmp_path / "x.md").write_text("---\nstatus: todo\ntags:\n  - a\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["update", "MATCH (t) REMOVE t.status", "-w", str(tmp_path), "--yes"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    text = (tmp_path / "x.md").read_text(encoding="utf-8")
    assert "status:" not in text
    assert "tags:" in text


def test_update_not_operator_toggle(tmp_path: Path):
    (tmp_path / "x.md").write_text("---\ndone: false\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["update", "MATCH (t) SET t.done = NOT t.done", "-w", str(tmp_path), "--yes"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "done: true" in (tmp_path / "x.md").read_text(encoding="utf-8")


def test_update_list_comprehension_filter(tmp_path: Path):
    (tmp_path / "x.md").write_text(
        "---\ntags:\n  - keep\n  - drop\n  - keep2\n---\n", encoding="utf-8"
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "update",
            'MATCH (t) SET t.tags = [x IN t.tags WHERE x <> "drop"]',
            "-w",
            str(tmp_path),
            "--yes",
        ],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    text = (tmp_path / "x.md").read_text(encoding="utf-8")
    assert "drop" not in text
    assert "keep" in text


def test_update_filter_by_virtual_path(tmp_path: Path):
    (tmp_path / "a.md").write_text("---\nstatus: todo\n---\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("---\nstatus: todo\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "update",
            'MATCH (t) WHERE t.path = "a.md" SET t.status = "done"',
            "-w",
            str(tmp_path),
            "--yes",
        ],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "status: done" in (tmp_path / "a.md").read_text(encoding="utf-8")
    assert "status: todo" in (tmp_path / "b.md").read_text(encoding="utf-8")


def test_update_filter_by_virtual_slug(tmp_path: Path):
    (tmp_path / "alpha.md").write_text("---\nstatus: todo\n---\n", encoding="utf-8")
    (tmp_path / "bravo.md").write_text("---\nstatus: todo\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "update",
            'MATCH (t) WHERE t.slug = "alpha" SET t.status = "done"',
            "-w",
            str(tmp_path),
            "--yes",
        ],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "status: done" in (tmp_path / "alpha.md").read_text(encoding="utf-8")
    assert "status: todo" in (tmp_path / "bravo.md").read_text(encoding="utf-8")
