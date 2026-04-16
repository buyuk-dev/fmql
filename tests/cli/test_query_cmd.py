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


# ---- follow ----


def _write_blocked_ws(root: Path) -> None:
    """a (uuid=a) → b (uuid=b, blocked_by=a) → c (uuid=c, blocked_by=b)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text(
        "---\nuuid: a\n---\nA\n", encoding="utf-8"
    )
    (root / "b.md").write_text(
        "---\nuuid: b\nblocked_by: a\n---\nB\n", encoding="utf-8"
    )
    (root / "c.md").write_text(
        "---\nuuid: c\nblocked_by: b\n---\nC\n", encoding="utf-8"
    )


def test_query_follow_depth_1(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query", str(tmp_path), 'uuid = "c"',
            "--follow", "blocked_by",
            "--depth", "1",
            "--resolver", "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert lines == ["b.md"]


def test_query_follow_depth_star(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query", str(tmp_path), 'uuid = "c"',
            "--follow", "blocked_by",
            "--depth", "*",
            "--resolver", "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = sorted(l for l in result.stdout.splitlines() if l.strip())
    assert lines == ["a.md", "b.md"]


def test_query_follow_reverse(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query", str(tmp_path), 'uuid = "a"',
            "--follow", "blocked_by",
            "--direction", "reverse",
            "--resolver", "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert lines == ["b.md"]


def test_query_follow_include_origin(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query", str(tmp_path), 'uuid = "c"',
            "--follow", "blocked_by",
            "--depth", "*",
            "--resolver", "uuid",
            "--include-origin",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = sorted(l for l in result.stdout.splitlines() if l.strip())
    assert lines == ["a.md", "b.md", "c.md"]


def test_query_follow_invalid_depth(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query", str(tmp_path), 'uuid = "c"',
            "--follow", "blocked_by",
            "--depth", "foo",
            "--resolver", "uuid",
        ],
    )
    assert result.exit_code == 2


def test_query_follow_pipe_to_append(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    # 1) query yields paths.
    q_result = runner.invoke(
        app,
        [
            "query", str(tmp_path), 'uuid = "c"',
            "--follow", "blocked_by",
            "--depth", "*",
            "--resolver", "uuid",
            "--include-origin",
        ],
    )
    assert q_result.exit_code == 0, q_result.output
    assert q_result.stdout.strip()

    # 2) pipe them into append --dry-run with --workspace.
    pipe_result = runner.invoke(
        app,
        [
            "append", "-", "tags=blocked-chain",
            "--workspace", str(tmp_path),
            "--dry-run",
        ],
        input=q_result.stdout,
    )
    assert pipe_result.exit_code == 0, pipe_result.output
    # Dry-run: files on disk unchanged.
    for name in ("a.md", "b.md", "c.md"):
        assert "blocked-chain" not in (tmp_path / name).read_text()
