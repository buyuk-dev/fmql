from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app


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
    result = runner.invoke(app, ["query", str(tmp_path), 'status = "active" AND priority > 2'])
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/a.md"]


def test_query_json_format(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", str(tmp_path), "*", "--format", "json"])
    assert result.exit_code == 0, result.output
    rows = [json.loads(ln) for ln in result.stdout.splitlines() if ln.strip()]
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
    lines = sorted(ln for ln in result.stdout.splitlines() if ln.strip())
    assert lines == ["tasks/a.md", "tasks/b.md", "tasks/c.md"]


def test_query_bad_syntax_exits_nonzero(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", str(tmp_path), "this is not valid"])
    assert result.exit_code == 2


def test_query_order_by_desc(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", str(tmp_path), "* ORDER BY priority DESC"])
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    # priority 3, then ties at 1 broken stably by packet id order
    assert lines == ["tasks/a.md", "tasks/b.md", "tasks/c.md"]


def test_query_order_by_asc(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", str(tmp_path), "* ORDER BY priority"])
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    # priorities [3, 1, 1] → ascending: two 1s first (stable by id), then 3
    assert lines == ["tasks/b.md", "tasks/c.md", "tasks/a.md"]


def test_version_cmd():
    from importlib.metadata import version as pkg_version

    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == pkg_version("fmql")


# ---- follow ----


def _write_blocked_ws(root: Path) -> None:
    """a (uuid=a) → b (uuid=b, blocked_by=a) → c (uuid=c, blocked_by=b)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nuuid: a\n---\nA\n", encoding="utf-8")
    (root / "b.md").write_text("---\nuuid: b\nblocked_by: a\n---\nB\n", encoding="utf-8")
    (root / "c.md").write_text("---\nuuid: c\nblocked_by: b\n---\nC\n", encoding="utf-8")


def test_query_follow_depth_1(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--depth",
            "1",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["b.md"]


def test_query_follow_depth_star(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--depth",
            "*",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = sorted(ln for ln in result.stdout.splitlines() if ln.strip())
    assert lines == ["a.md", "b.md"]


def test_query_follow_reverse(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "a"',
            "--follow",
            "blocked_by",
            "--direction",
            "reverse",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["b.md"]


def test_query_follow_include_origin(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--depth",
            "*",
            "--resolver",
            "uuid",
            "--include-origin",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = sorted(ln for ln in result.stdout.splitlines() if ln.strip())
    assert lines == ["a.md", "b.md", "c.md"]


def test_query_follow_zero_results_emits_resolver_warning(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == ""
    assert "warning:" in result.stderr
    assert "blocked_by" in result.stderr


def test_query_follow_warning_suppressed_with_matching_resolver(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.stderr


def test_query_follow_warning_fires_even_with_empty_seeds(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "no-such-packet"',
            "--follow",
            "blocked_by",
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == ""
    # Warning reflects workspace state — bound resolver leaves blocked_by
    # values unresolved across the workspace, regardless of seed selection.
    assert "warning:" in result.stderr


def test_query_without_follow_no_warning(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", str(tmp_path), 'uuid = "nope"', "--diagnose"],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.stderr


def test_query_follow_no_diagnose_flag_is_silent(tmp_path: Path):
    """Default invocation (no --diagnose) must never emit warnings, even on misbinds."""
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.stderr


def test_query_diagnose_invalid_workspace_md_value_exits_2(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    (tmp_path / "WORKSPACE.md").write_text('---\nfmql:\n  diagnose: "yes"\n---\n', encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", str(tmp_path), 'uuid = "c"', "--follow", "blocked_by"],
    )
    assert result.exit_code == 2
    assert "diagnose" in result.stderr


def test_query_follow_diagnose_via_workspace_md(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    (tmp_path / "WORKSPACE.md").write_text("---\nfmql:\n  diagnose: true\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" in result.stderr


def test_query_follow_partial_mismatch_emits_warning(tmp_path: Path):
    """A field where some values resolve and some don't should still warn."""
    root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nuuid: a\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nuuid: b\nblocked_by: [a, ghost]\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "b"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" in result.stderr
    assert "blocked_by" in result.stderr


def test_query_workspace_md_id_resolver_end_to_end(tmp_path: Path):
    root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    (root / "WORKSPACE.md").write_text(
        "---\nfmql:\n  resolvers:\n    depends_on: id\n---\n", encoding="utf-8"
    )
    (root / "a.md").write_text("---\nid: 1\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nid: 2\ndepends_on: [1]\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", str(tmp_path), "id = 2", "--follow", "depends_on", "--diagnose"],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["a.md"]
    assert "warning:" not in result.stderr


def test_query_cli_resolver_overrides_workspace_md_binding(tmp_path: Path):
    root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    (root / "WORKSPACE.md").write_text(
        "---\nfmql:\n  resolvers:\n    depends_on: id\n---\n", encoding="utf-8"
    )
    (root / "a.md").write_text("---\nid: 1\nuuid: a\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nid: 2\nuuid: b\ndepends_on: [a]\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "b"',
            "--follow",
            "depends_on",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["a.md"]


def test_query_follow_invalid_depth(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--depth",
            "foo",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 2


def test_query_search_narrows(tmp_path: Path):
    _write_ws(tmp_path)
    (tmp_path / "tasks/a.md").write_text(
        "---\nstatus: active\npriority: 3\n---\nfind the banana here\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(app, ["query", str(tmp_path), "*", "--search", "banana"])
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/a.md"]


def test_query_search_explicit_grep_index(tmp_path: Path):
    _write_ws(tmp_path)
    (tmp_path / "tasks/a.md").write_text(
        "---\nstatus: active\npriority: 3\n---\nbanana\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", str(tmp_path), "*", "--search", "banana", "--index", "grep"],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/a.md"]


def test_query_unknown_index_exits_2(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", str(tmp_path), "*", "--search", "foo", "--index", "nope"],
    )
    assert result.exit_code == 2


def test_query_search_combines_with_filter(tmp_path: Path):
    _write_ws(tmp_path)
    (tmp_path / "tasks/a.md").write_text(
        "---\nstatus: active\npriority: 3\n---\nbanana\n",
        encoding="utf-8",
    )
    (tmp_path / "tasks/c.md").write_text(
        "---\nstatus: active\npriority: 1\n---\nbanana\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            "priority > 2",
            "--search",
            "banana",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/a.md"]


def test_query_follow_pipe_to_append(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    # 1) query yields paths.
    q_result = runner.invoke(
        app,
        [
            "query",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--depth",
            "*",
            "--resolver",
            "uuid",
            "--include-origin",
        ],
    )
    assert q_result.exit_code == 0, q_result.output
    assert q_result.stdout.strip()

    # 2) pipe them into append --dry-run with --workspace.
    pipe_result = runner.invoke(
        app,
        [
            "append",
            "-",
            "tags=blocked-chain",
            "--workspace",
            str(tmp_path),
            "--dry-run",
        ],
        input=q_result.stdout,
    )
    assert pipe_result.exit_code == 0, pipe_result.output
    # Dry-run: files on disk unchanged.
    for name in ("a.md", "b.md", "c.md"):
        assert "blocked-chain" not in (tmp_path / name).read_text()
