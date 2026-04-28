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
            str(tmp_path),
            'MATCH (t) SET t.depends_on = field(resolve(t.depends_on, "id"), "slug")',
            "--yes",
        ],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    contents = (tmp_path / "c.md").read_text(encoding="utf-8")
    assert "alpha" in contents
    assert "bravo" in contents
    # Original ints should not appear in the depends_on block.
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
            str(tmp_path),
            'MATCH (t) WHERE t.id = 17 SET t.label = "C"',
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "c.md").read_text(encoding="utf-8") == before


def test_update_without_set_errors(tmp_path: Path):
    _write_id_refs(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["update", str(tmp_path), "MATCH (t) RETURN t"],
    )
    assert result.exit_code == 2
    assert "SET" in result.stderr or "SET" in result.output


def test_update_with_return_errors(tmp_path: Path):
    _write_id_refs(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["update", str(tmp_path), "MATCH (t) SET t.x = 1 RETURN t"],
    )
    assert result.exit_code == 2


def test_update_workspace_flag_honored(tmp_path: Path):
    _write_id_refs(tmp_path)
    sub = tmp_path / "subset"
    sub.mkdir()
    runner = CliRunner()
    # Pass `path` arg as the subset dir but `--workspace` overrides.
    result = runner.invoke(
        app,
        [
            "update",
            str(sub),
            "--workspace",
            str(tmp_path),
            'MATCH (t) WHERE t.id = 1 SET t.label = "first"',
            "--yes",
        ],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "first" in (tmp_path / "a.md").read_text(encoding="utf-8")
