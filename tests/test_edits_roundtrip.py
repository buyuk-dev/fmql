from __future__ import annotations

from pathlib import Path

from fm.edits import plan_append, plan_remove, plan_rename, plan_set, plan_toggle
from fm.workspace import Workspace


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _read(root: Path, rel: str) -> str:
    with open(root / rel, "r", encoding="utf-8", newline="") as f:
        return f.read()


def test_set_preserves_body_bytes_on_fixture(tmp_path: Path) -> None:
    text = (
        "---\n"
        "uuid: task-x\n"
        "status: active\n"
        "tags:\n"
        "  - a\n"
        "  - b\n"
        "---\n"
        "\n"
        "Body line 1.\n"
        "Body line 2.\n"
    )
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_set(ws, ["x.md"], status="escalated").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert (
        result == "---\n"
        "uuid: task-x\n"
        "status: escalated\n"
        "tags:\n"
        "  - a\n"
        "  - b\n"
        "---\n"
        "\n"
        "Body line 1.\n"
        "Body line 2.\n"
    )


def test_set_preserves_comments(tmp_path: Path) -> None:
    text = (
        "---\n"
        "# header comment\n"
        "uuid: task-x  # uuid comment\n"
        "status: active\n"
        "---\n"
        "body\n"
    )
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_set(ws, ["x.md"], status="escalated").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert "# header comment" in result
    assert "# uuid comment" in result
    assert "status: escalated" in result


def test_set_preserves_quoted_numeric_string(tmp_path: Path) -> None:
    text = '---\npriority: "42"\nstatus: active\n---\nbody\n'
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_set(ws, ["x.md"], status="escalated").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert 'priority: "42"' in result


def test_append_to_flow_list_preserves_flow_style(tmp_path: Path) -> None:
    text = "---\ntags: [a, b]\n---\nbody\n"
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_append(ws, ["x.md"], tags="c").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert "tags: [a, b, c]" in result


def test_rename_preserves_inline_comment(tmp_path: Path) -> None:
    text = "---\na: 1\nb: 2 # keep me\nc: 3\n---\nbody\n"
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_rename(ws, ["x.md"], b="bb").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert "bb: 2" in result
    assert "# keep me" in result


def test_remove_preserves_surrounding(tmp_path: Path) -> None:
    text = "---\n" "a: 1\n" "b: 2\n" "c: 3\n" "---\n" "Body with multiple lines.\n" "And another.\n"
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_remove(ws, ["x.md"], "b").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert (
        result == "---\n" "a: 1\n" "c: 3\n" "---\n" "Body with multiple lines.\n" "And another.\n"
    )


def test_toggle_preserves_body(tmp_path: Path) -> None:
    text = "---\nflagged: false\n---\nBody.\n"
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_toggle(ws, ["x.md"], "flagged").apply(confirm=False)
    assert _read(tmp_path, "x.md") == "---\nflagged: true\n---\nBody.\n"


def test_set_on_no_frontmatter_creates_fence(tmp_path: Path) -> None:
    text = "just plain markdown\n"
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_set(ws, ["x.md"], status="new").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert result == "---\nstatus: new\n---\njust plain markdown\n"


def test_set_on_no_fm_guards_body_starting_with_fence(tmp_path: Path) -> None:
    text = "---\nhorizontal rule below body\n"
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_set(ws, ["x.md"], status="new").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    # New FM fence pair, then a blank line separator, then the original body
    # which starts with the markdown ---.
    assert result.startswith("---\nstatus: new\n---\n\n---\n")


def test_remove_last_key_emits_empty_fence_pair(tmp_path: Path) -> None:
    text = "---\nonly: 1\n---\nbody\n"
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_remove(ws, ["x.md"], "only").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert result == "---\n---\nbody\n"


def test_crlf_preserved_under_edit(tmp_path: Path) -> None:
    text = "---\r\nstatus: active\r\ntags:\r\n  - a\r\n---\r\nbody\r\n"
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_set(ws, ["x.md"], status="escalated").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert result == "---\r\nstatus: escalated\r\ntags:\r\n  - a\r\n---\r\nbody\r\n"


def test_unicode_values_preserved(tmp_path: Path) -> None:
    text = "---\nstatus: 进行中\ntitle: café\n---\nbody\n"
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_set(ws, ["x.md"], priority=1).apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert "进行中" in result
    assert "café" in result
    assert "priority: 1" in result


def test_no_eof_newline_preserved_on_edit(tmp_path: Path) -> None:
    text = "---\nstatus: active\n---\nbody without trailing newline"
    _write(tmp_path, "x.md", text)
    ws = Workspace(tmp_path)
    plan_set(ws, ["x.md"], status="escalated").apply(confirm=False)
    result = _read(tmp_path, "x.md")
    assert result == "---\nstatus: escalated\n---\nbody without trailing newline"


def test_query_sink_roundtrip(project_pm_ws) -> None:
    """Query.set → EditPlan → apply updates workspace and disk."""
    from fm.query import Query

    q = Query(project_pm_ws).where(status="active")
    matching_before = q.ids()
    assert "tasks/task-1.md" in matching_before

    q.set(status="reviewed").apply(confirm=False)

    # Re-query: previously-matching packets now have status=reviewed.
    for pid in matching_before:
        assert project_pm_ws.packets[pid].frontmatter["status"] == "reviewed"


def test_query_append_bulk(project_pm_ws) -> None:
    from fm.query import Query

    q = Query(project_pm_ws).where(type="task")
    report = q.append(tags="migrated").apply(confirm=False)
    # Every task had tags (as a list) — all should succeed.
    assert len(report.written) == 4
    for pid in report.written:
        tags = project_pm_ws.packets[pid].frontmatter["tags"]
        assert "migrated" in list(tags)
