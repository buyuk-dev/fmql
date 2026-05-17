from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app


def _write_vault(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "Strategy.md").write_text("strategy body\n", encoding="utf-8")
    (root / "Playbook.md").write_text("playbook body\n", encoding="utf-8")
    (root / "Index.md").write_text(
        "see [[Strategy]] and [[Playbook|the playbook]]\nghost: [[Ghost]]\n",
        encoding="utf-8",
    )
    (root / "ScalarRef.md").write_text(
        "---\nprimary: '[[Playbook]]'\n---\n",
        encoding="utf-8",
    )


def test_cli_match_mentions(tmp_path: Path):
    _write_vault(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (a)-[:mentions]->(b) RETURN a, b", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    rows = sorted(tuple(ln.split("\t")) for ln in result.stdout.splitlines() if ln.strip())
    assert rows == [
        ("Index.md", "Playbook.md"),
        ("Index.md", "Strategy.md"),
    ]


def test_cli_follow_mentions(tmp_path: Path):
    _write_vault(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (n) WHERE n._id = "Index.md" RETURN n',
            "--follow",
            "mentions",
            "--depth",
            "1",
            "-w",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    lines = sorted(ln for ln in result.stdout.splitlines() if ln.strip())
    assert lines == ["Playbook.md", "Strategy.md"]


def test_cli_match_property_name(tmp_path: Path):
    _write_vault(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (a)-[:primary]->(b) RETURN a, b", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    rows = sorted(tuple(ln.split("\t")) for ln in result.stdout.splitlines() if ln.strip())
    assert rows == [("ScalarRef.md", "Playbook.md")]


def test_cli_diagnose_emits_wikilink_warning(tmp_path: Path):
    _write_vault(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (a)-[:mentions]->(b) RETURN a",
            "--diagnose",
            "-w",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "[[Ghost]]" in (result.stderr or result.output)


def test_cli_no_diagnose_no_warning(tmp_path: Path):
    _write_vault(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (a)-[:mentions]->(b) RETURN a", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "[[Ghost]]" not in (result.stderr or result.output)
