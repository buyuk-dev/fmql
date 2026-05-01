from __future__ import annotations

import pytest

from fmql.ordering import OrderKey
from fmql.query import Query
from fmql.resolvers import UuidResolver


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
    assert ids == {"tasks/task-1.md", "tasks/task-3.md", "tasks/task-4.md"}


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


def test_follow_basic_forward(project_pm_ws):
    r = UuidResolver()
    q = Query(project_pm_ws).where(uuid="task-3").follow("blocked_by", resolver=r)
    assert q.ids() == ["tasks/task-1.md"]


def test_follow_include_origin(project_pm_ws):
    r = UuidResolver()
    q = (
        Query(project_pm_ws)
        .where(uuid="task-3")
        .follow("blocked_by", resolver=r, include_origin=True)
    )
    assert set(q.ids()) == {"tasks/task-1.md", "tasks/task-3.md"}


def test_filter_follow_filter_chain(project_pm_ws):
    r = UuidResolver()
    # Expand from task-3 via blocked_by, then filter reachable tasks by priority.
    q = (
        Query(project_pm_ws)
        .where(uuid="task-3")
        .follow("blocked_by", resolver=r)
        .where(priority__gt=2)
    )
    assert q.ids() == ["tasks/task-1.md"]  # task-1 has priority 3


def test_follow_reverse(project_pm_ws):
    r = UuidResolver()
    q = (
        Query(project_pm_ws)
        .where(uuid="task-1")
        .follow("blocked_by", direction="reverse", resolver=r)
    )
    assert q.ids() == ["tasks/task-3.md", "tasks/task-4.md"]


def test_follow_edit_sink(project_pm_ws):
    r = UuidResolver()
    q = (
        Query(project_pm_ws)
        .where(uuid="task-3")
        .follow("blocked_by", depth="*", resolver=r, include_origin=True)
    )
    plan = q.set(status="reviewed")
    report = plan.apply(confirm=False)
    assert set(report.written) == {"tasks/task-1.md", "tasks/task-3.md"}
    for pid in report.written:
        assert project_pm_ws.packets[pid].frontmatter["status"] == "reviewed"


# ---------- ordering (Python API) ----------


@pytest.fixture
def ordering_ws(make_workspace):
    return make_workspace(
        {
            "p1.md": {"frontmatter": {"uuid": "p1", "priority": 3, "status": "open"}},
            "p2.md": {"frontmatter": {"uuid": "p2", "priority": 1, "status": "open"}},
            "p3.md": {"frontmatter": {"uuid": "p3", "priority": 5, "status": "done"}},
            "p4.md": {"frontmatter": {"uuid": "p4", "priority": 2, "status": "open"}},
            "p5.md": {"frontmatter": {"uuid": "p5", "status": "open"}},
        }
    )


def _priorities(ids, ws):
    return [ws.packets[pid].as_plain().get("priority") for pid in ids]


def test_order_by_chainable(ordering_ws):
    q = Query(ordering_ws).where(status="open").order_by("priority", desc=True)
    assert _priorities(q.ids(), ordering_ws) == [None, 3, 2, 1]


def test_order_by_multi_key_accumulates(make_workspace):
    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"status": "open", "priority": 2}},
            "b.md": {"frontmatter": {"status": "open", "priority": 1}},
            "c.md": {"frontmatter": {"status": "done", "priority": 3}},
        }
    )
    q = Query(ws).order_by("status").order_by("priority", desc=True)
    rows = [
        (ws.packets[pid].as_plain()["status"], ws.packets[pid].as_plain()["priority"])
        for pid in q.ids()
    ]
    assert rows == [("done", 3), ("open", 2), ("open", 1)]


def test_order_key_validates_nulls():
    with pytest.raises(ValueError):
        OrderKey(field="x", nulls="bogus")
