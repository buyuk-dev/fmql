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
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.status = "active" AND t.priority > 2 RETURN t',
            "-w",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/a.md"]


def test_query_json_format(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN t", "-w", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    rows = [json.loads(ln) for ln in result.stdout.splitlines() if ln.strip()]
    assert len(rows) == 3
    ids = sorted(r["id"] for r in rows)
    assert ids == ["tasks/a.md", "tasks/b.md", "tasks/c.md"]
    for r in rows:
        assert "status" in r["frontmatter"]


def test_query_rows_format_multi_var(tmp_path: Path):
    root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nuuid: a\nblocked_by: b\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nuuid: b\n---\n", encoding="utf-8")
    (root / "WORKSPACE.md").write_text(
        "---\nfmql:\n  resolvers:\n    blocked_by: uuid\n---\n", encoding="utf-8"
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (a)-[:blocked_by]->(b) RETURN a, b",
            "-w",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    rows = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert rows == ["a.md\tb.md"]


def test_query_paths_format_rejects_field_return(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (t) RETURN t.status",
            "-w",
            str(tmp_path),
            "--format",
            "paths",
        ],
    )
    assert result.exit_code == 2
    assert "single packet variable" in result.stderr.lower() or "paths" in result.stderr.lower()


def test_query_star_prints_all(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", "MATCH (t) RETURN t", "-w", str(tmp_path)])
    assert result.exit_code == 0
    lines = sorted(ln for ln in result.stdout.splitlines() if ln.strip())
    assert lines == ["tasks/a.md", "tasks/b.md", "tasks/c.md"]


def test_query_defaults_workspace_to_cwd(tmp_path: Path, monkeypatch):
    _write_ws(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", "MATCH (t) RETURN t"])
    assert result.exit_code == 0, result.output
    lines = sorted(ln for ln in result.stdout.splitlines() if ln.strip())
    assert lines == ["tasks/a.md", "tasks/b.md", "tasks/c.md"]


def test_query_bad_syntax_exits_nonzero(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["query", "this is not valid", "-w", str(tmp_path)])
    assert result.exit_code == 2


def test_query_order_by_desc(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN t ORDER BY t.priority DESC", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/a.md", "tasks/b.md", "tasks/c.md"]


def test_query_order_by_asc(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN t ORDER BY t.priority", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/b.md", "tasks/c.md", "tasks/a.md"]


def test_query_count_return(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN count(t)", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "3"


def test_query_in_query_limit(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN t ORDER BY t.priority DESC LIMIT 2", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/a.md", "tasks/b.md"]


def test_query_limit_flag_caps_output(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN t ORDER BY t.priority", "-w", str(tmp_path), "--limit", "2"],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/b.md", "tasks/c.md"]


def test_query_limit_flag_more_restrictive_than_query(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (t) RETURN t ORDER BY t.priority LIMIT 5",
            "-w",
            str(tmp_path),
            "--limit",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/b.md"]


def test_query_limit_in_query_more_restrictive_than_flag(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (t) RETURN t ORDER BY t.priority LIMIT 1",
            "-w",
            str(tmp_path),
            "--limit",
            "5",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/b.md"]


def test_query_limit_zero_emits_nothing(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN t LIMIT 0", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == ""


def test_query_limit_flag_negative_errors(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN t", "-w", str(tmp_path), "--limit=-1"],
    )
    assert result.exit_code == 2
    assert "limit" in result.stderr.lower()


def test_query_limit_with_follow(tmp_path: Path):
    root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nuuid: a\nblocked_by: [b, c]\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nuuid: b\n---\n", encoding="utf-8")
    (root / "c.md").write_text("---\nuuid: c\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "a" RETURN t',
            "-w",
            str(tmp_path),
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--limit",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1


def test_query_limit_count_keeps_scalar(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN count(t) LIMIT 1", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "3"


def test_query_limit_count_zero_emits_nothing(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN count(t) LIMIT 0", "-w", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == ""


def test_version_cmd():
    from importlib.metadata import version as pkg_version

    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == pkg_version("fmql")


def test_cypher_command_removed():
    runner = CliRunner()
    result = runner.invoke(app, ["cypher", "MATCH (t) RETURN t"])
    assert result.exit_code != 0


def test_query_follow_depth_1(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "c" RETURN t',
            "-w",
            str(tmp_path),
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


def test_query_follow_depth_star(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "c" RETURN t',
            "-w",
            str(tmp_path),
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


def test_query_follow_reverse(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "a" RETURN t',
            "-w",
            str(tmp_path),
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


def test_query_follow_include_origin(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "c" RETURN t',
            "-w",
            str(tmp_path),
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


def test_query_follow_zero_results_emits_resolver_warning(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "c" RETURN t',
            "-w",
            str(tmp_path),
            "--follow",
            "blocked_by",
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == ""
    assert "warning:" in result.stderr
    assert "blocked_by" in result.stderr


def test_query_follow_warning_suppressed_with_matching_resolver(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "c" RETURN t',
            "-w",
            str(tmp_path),
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.stderr


def test_query_follow_warning_fires_even_with_empty_seeds(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "no-such-packet" RETURN t',
            "-w",
            str(tmp_path),
            "--follow",
            "blocked_by",
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == ""
    assert "warning:" in result.stderr


def test_query_without_follow_no_warning(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "nope" RETURN t',
            "-w",
            str(tmp_path),
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.stderr


def test_query_follow_no_diagnose_flag_is_silent(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "c" RETURN t',
            "-w",
            str(tmp_path),
            "--follow",
            "blocked_by",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.stderr


def test_query_diagnose_invalid_workspace_md_value_exits_2(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    (tmp_path / "WORKSPACE.md").write_text('---\nfmql:\n  diagnose: "yes"\n---\n', encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "c" RETURN t',
            "-w",
            str(tmp_path),
            "--follow",
            "blocked_by",
        ],
    )
    assert result.exit_code == 2
    assert "diagnose" in result.stderr


def test_query_follow_diagnose_via_workspace_md(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    (tmp_path / "WORKSPACE.md").write_text("---\nfmql:\n  diagnose: true\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "c" RETURN t',
            "-w",
            str(tmp_path),
            "--follow",
            "blocked_by",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" in result.stderr


def test_query_follow_partial_mismatch_emits_warning(tmp_path: Path):
    root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nuuid: a\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nuuid: b\nblocked_by: [a, ghost]\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "b" RETURN t',
            "-w",
            str(tmp_path),
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
        [
            "query",
            "MATCH (t) WHERE t.id = 2 RETURN t",
            "-w",
            str(tmp_path),
            "--follow",
            "depends_on",
            "--diagnose",
        ],
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
            'MATCH (t) WHERE t.uuid = "b" RETURN t',
            "-w",
            str(tmp_path),
            "--follow",
            "depends_on",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["a.md"]


def test_query_follow_invalid_depth(tmp_path: Path, write_blocked_ws):
    write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            'MATCH (t) WHERE t.uuid = "c" RETURN t',
            "-w",
            str(tmp_path),
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
    result = runner.invoke(
        app,
        ["query", "MATCH (t) RETURN t", "-w", str(tmp_path), "--search", "banana"],
    )
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
        [
            "query",
            "MATCH (t) RETURN t",
            "-w",
            str(tmp_path),
            "--search",
            "banana",
            "--index",
            "grep",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/a.md"]


def test_query_unknown_index_exits_2(tmp_path: Path):
    _write_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "MATCH (t) RETURN t",
            "-w",
            str(tmp_path),
            "--search",
            "foo",
            "--index",
            "nope",
        ],
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
            "MATCH (t) WHERE t.priority > 2 RETURN t",
            "-w",
            str(tmp_path),
            "--search",
            "banana",
        ],
    )
    assert result.exit_code == 0, result.output
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["tasks/a.md"]
