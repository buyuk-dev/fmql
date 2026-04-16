from __future__ import annotations

from fmq.query import Query


def test_all_returns_every_packet(project_pm_ws):
    q = Query(project_pm_ws).all()
    ids = q.ids()
    assert set(ids) == set(project_pm_ws.packets.keys())


def test_iteration_is_sorted(project_pm_ws):
    q = Query(project_pm_ws)
    ids = [p.id for p in q]
    assert ids == sorted(ids)


def test_where_filters(project_pm_ws):
    q = Query(project_pm_ws).where(type="task", status="active")
    ids = set(q.ids())
    assert ids == {"tasks/task-1.md", "tasks/task-3.md"}


def test_where_chaining_is_and(project_pm_ws):
    q = Query(project_pm_ws).where(type="task").where(priority__gt=2)
    ids = set(q.ids())
    assert ids == {"tasks/task-1.md", "tasks/task-3.md"}


def test_where_gt_excludes_string_priority(project_pm_ws):
    # epic-1 has priority="high", must not match priority__gt=2
    q = Query(project_pm_ws).where(priority__gt=2)
    ids = set(q.ids())
    assert "epics/epic-1.md" not in ids


def test_immutable_builder(project_pm_ws):
    base = Query(project_pm_ws)
    narrowed = base.where(status="active")
    assert base.ids() != narrowed.ids()
    assert set(base.ids()) == set(project_pm_ws.packets.keys())
