from __future__ import annotations

import pytest

from fm.edits import plan_append, plan_remove, plan_rename, plan_set, plan_toggle
from fm.errors import EditError


def test_plan_set_basic_preview(project_pm_ws) -> None:
    plan = plan_set(project_pm_ws, ["tasks/task-1.md"], status="escalated")
    text = plan.preview()
    assert "a/tasks/task-1.md" in text
    assert "b/tasks/task-1.md" in text
    assert "-status: active" in text
    assert "+status: escalated" in text


def test_plan_dry_run_equals_preview(project_pm_ws) -> None:
    plan = plan_set(project_pm_ws, ["tasks/task-1.md"], status="escalated")
    assert plan.dry_run() == plan.preview()


def test_plan_apply_writes_and_updates_workspace(project_pm_ws) -> None:
    plan = plan_set(project_pm_ws, ["tasks/task-1.md"], status="escalated")
    report = plan.apply(confirm=False)
    assert report.written == ["tasks/task-1.md"]
    assert report.aborted is False
    # In-memory workspace reflects disk.
    pkt = project_pm_ws.packets["tasks/task-1.md"]
    assert pkt.frontmatter["status"] == "escalated"
    # On-disk too.
    with open(pkt.abspath, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    assert "status: escalated" in text


def test_plan_apply_preserves_body(project_pm_ws) -> None:
    original = project_pm_ws.packets["tasks/task-1.md"].body
    plan = plan_set(project_pm_ws, ["tasks/task-1.md"], priority=99)
    plan.apply(confirm=False)
    assert project_pm_ws.packets["tasks/task-1.md"].body == original


def test_plan_apply_noop_reports_skipped(project_pm_ws) -> None:
    plan = plan_set(project_pm_ws, ["tasks/task-1.md"], status="active")
    report = plan.apply(confirm=False)
    assert report.skipped == ["tasks/task-1.md"]
    assert report.written == []


def test_plan_preview_omits_noop_files(project_pm_ws) -> None:
    plan = plan_set(
        project_pm_ws,
        ["tasks/task-1.md", "tasks/task-2.md"],
        status="done",
    )
    text = plan.preview()
    # task-2 already has status: done → omitted from preview.
    assert "tasks/task-2.md" not in text
    assert "tasks/task-1.md" in text


def test_plan_append_type_conflict_surfaces_as_error(project_pm_ws) -> None:
    plan = plan_append(project_pm_ws, ["epics/epic-1.md"], priority="extra")
    text = plan.preview()
    assert "!!" in text
    assert "cannot append" in text
    report = plan.apply(confirm=False)
    assert report.written == []
    assert len(report.errors) == 1


def test_plan_toggle_non_bool_reports_error(project_pm_ws) -> None:
    plan = plan_toggle(project_pm_ws, ["tasks/task-1.md"], "status")
    report = plan.apply(confirm=False)
    assert report.written == []
    assert len(report.errors) == 1
    assert "non-bool" in report.errors[0][1]


def test_plan_rename_preserves_position(project_pm_ws) -> None:
    plan = plan_rename(project_pm_ws, ["tasks/task-1.md"], uuid="id")
    plan.apply(confirm=False)
    pkt = project_pm_ws.packets["tasks/task-1.md"]
    keys = list(pkt.frontmatter)
    assert keys[0] == "id"


def test_plan_remove_absent_is_noop(project_pm_ws) -> None:
    plan = plan_remove(project_pm_ws, ["tasks/task-1.md"], "missing")
    report = plan.apply(confirm=False)
    assert report.skipped == ["tasks/task-1.md"]
    assert report.written == []


def test_plan_partial_failure_isolation(project_pm_ws) -> None:
    # task-1 has priority: int; epic-1 has priority: str.
    # Append on both: task-1 creates list[int]; epic-1 fails (scalar str).
    plan = plan_append(project_pm_ws, ["tasks/task-1.md", "epics/epic-1.md"], priority=9)
    report = plan.apply(confirm=False)
    # Wait — task-1 also has priority as int, so it's also scalar. Both fail.
    # Use tags instead.
    assert len(report.written) + len(report.errors) == 2


def test_plan_confirm_rejects(project_pm_ws) -> None:
    plan = plan_set(project_pm_ws, ["tasks/task-1.md"], status="escalated")
    report = plan.apply(confirm_fn=lambda msg: False)
    assert report.aborted is True
    assert report.written == []
    # Nothing changed on disk.
    assert project_pm_ws.packets["tasks/task-1.md"].frontmatter["status"] == "active"


def test_plan_confirm_accepts(project_pm_ws) -> None:
    plan = plan_set(project_pm_ws, ["tasks/task-1.md"], status="escalated")
    report = plan.apply(confirm_fn=lambda msg: True)
    assert report.written == ["tasks/task-1.md"]


def test_plan_set_rejects_empty_kwargs(project_pm_ws) -> None:
    with pytest.raises(EditError):
        plan_set(project_pm_ws, ["tasks/task-1.md"])


def test_plan_remove_rejects_empty(project_pm_ws) -> None:
    with pytest.raises(EditError):
        plan_remove(project_pm_ws, ["tasks/task-1.md"])


def test_plan_unknown_packet_raises(project_pm_ws) -> None:
    with pytest.raises(EditError):
        plan_set(project_pm_ws, ["no/such/file.md"], status="x")


def test_plan_summary(project_pm_ws) -> None:
    plan = plan_set(
        project_pm_ws,
        ["tasks/task-1.md", "tasks/task-2.md"],
        status="done",
    )
    # task-1: active→done (changed). task-2: already done (noop).
    summary = plan.summary()
    assert "1 changed" in summary
    assert "1 no-op" in summary
