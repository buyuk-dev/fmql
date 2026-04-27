from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app


def _write_blocked_ws(root: Path) -> None:
    """a (uuid=a) → b (uuid=b, blocked_by=a) → c (uuid=c, blocked_by=b)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nuuid: a\n---\nA\n", encoding="utf-8")
    (root / "b.md").write_text("---\nuuid: b\nblocked_by: a\n---\nB\n", encoding="utf-8")
    (root / "c.md").write_text("---\nuuid: c\nblocked_by: b\n---\nC\n", encoding="utf-8")


def test_subgraph_forward_single_hop(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--direction",
            "reverse",
            "--depth",
            "1",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert sorted(n["id"] for n in payload["nodes"]) == ["c.md"]
    assert payload["edges"] == []


def test_subgraph_forward_depth_star_full_closure(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    ids = sorted(n["id"] for n in payload["nodes"])
    assert ids == ["a.md", "b.md", "c.md"]
    edges = [(e["source"], e["target"], e["field"]) for e in payload["edges"]]
    assert ("c.md", "b.md", "blocked_by") in edges
    assert ("b.md", "a.md", "blocked_by") in edges


def test_subgraph_reverse_direction(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
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
    payload = json.loads(result.stdout.strip())
    ids = sorted(n["id"] for n in payload["nodes"])
    assert ids == ["a.md", "b.md", "c.md"]
    edges = [(e["source"], e["target"], e["field"]) for e in payload["edges"]]
    assert ("b.md", "a.md", "blocked_by") in edges
    assert ("c.md", "b.md", "blocked_by") in edges


def test_subgraph_ids_only(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--ids-only",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    for node in payload["nodes"]:
        assert set(node.keys()) == {"id"}


def test_subgraph_no_include_origin(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--no-include-origin",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    ids = sorted(n["id"] for n in payload["nodes"])
    assert ids == ["a.md", "b.md"]


def test_subgraph_resolver_mismatch_emits_warning(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--diagnose",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert payload["edges"] == []
    assert "warning:" in result.stderr
    assert "blocked_by" in result.stderr


def test_subgraph_no_diagnose_flag_is_silent(tmp_path: Path):
    """Default invocation (no --diagnose) must never emit warnings, even on misbinds."""
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" not in result.stderr


def test_subgraph_diagnose_via_workspace_md(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    (tmp_path / "WORKSPACE.md").write_text("---\nfmql:\n  diagnose: true\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "warning:" in result.stderr


def test_subgraph_warning_fires_on_partial_mismatch_with_nonempty_edges(tmp_path: Path):
    root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.md").write_text("---\nuuid: a\n---\n", encoding="utf-8")
    (root / "b.md").write_text("---\nuuid: b\nblocked_by: [a, ghost]\n---\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
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
    payload = json.loads(result.stdout.strip())
    assert len(payload["edges"]) == 1
    assert "warning:" in result.stderr


def test_subgraph_invalid_depth_exits_2(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
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


def test_subgraph_format_cytoscape(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--format",
            "cytoscape",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    assert set(payload.keys()) == {"elements"}
    assert set(payload["elements"].keys()) == {"nodes", "edges"}
    node_ids = sorted(n["data"]["id"] for n in payload["elements"]["nodes"])
    assert node_ids == ["a.md", "b.md", "c.md"]
    edge_ids = {e["data"]["id"] for e in payload["elements"]["edges"]}
    assert "c.md__blocked_by__b.md" in edge_ids
    assert "b.md__blocked_by__a.md" in edge_ids
    for n in payload["elements"]["nodes"]:
        assert "frontmatter" in n["data"]


def test_subgraph_format_cytoscape_ids_only(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--format",
            "cytoscape",
            "--ids-only",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout.strip())
    for n in payload["elements"]["nodes"]:
        assert set(n["data"].keys()) == {"id"}


def test_subgraph_format_raw_matches_default(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    args = [
        "subgraph",
        str(tmp_path),
        'uuid = "c"',
        "--follow",
        "blocked_by",
        "--resolver",
        "uuid",
    ]
    default_result = runner.invoke(app, args)
    raw_result = runner.invoke(app, [*args, "--format", "raw"])
    assert default_result.exit_code == 0
    assert raw_result.exit_code == 0
    assert json.loads(default_result.stdout) == json.loads(raw_result.stdout)


def test_subgraph_format_unknown_exits_2(tmp_path: Path):
    _write_blocked_ws(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "subgraph",
            str(tmp_path),
            'uuid = "c"',
            "--follow",
            "blocked_by",
            "--resolver",
            "uuid",
            "--format",
            "graphviz",
        ],
    )
    assert result.exit_code == 2
