from __future__ import annotations

from datetime import date

from fmq.aggregation import Avg, Count, GroupedQuery, Max, Min, Sum
from fmq.query import Query
from fmq.resolvers import UuidResolver


def test_group_by_status_count_tasks(project_pm_ws):
    result = Query(project_pm_ws).where(type="task").group_by("status").count()
    assert result == {"active": 3, "done": 1}


def test_group_by_in_sprint_count(project_pm_ws):
    result = Query(project_pm_ws).where(type="task").group_by("in_sprint").count()
    assert result == {"sprint-3": 2, "sprint-4": 2}


def test_group_by_status_sum_priority_type_honest(project_pm_ws):
    # epic has priority="high" (str) → skipped. tasks: active=3+5+2, done=1.
    result = Query(project_pm_ws).group_by("status").sum("priority")
    assert result == {"active": 10, "done": 1}


def test_group_by_status_avg_priority(project_pm_ws):
    result = Query(project_pm_ws).where(type="task").group_by("status").avg("priority")
    assert result == {"active": (3 + 5 + 2) / 3, "done": 1.0}


def test_group_by_in_sprint_min_max_due_date(project_pm_ws):
    q = Query(project_pm_ws).where(type="task")
    assert q.group_by("in_sprint").min("due_date") == {
        "sprint-3": date(2026, 4, 10),
        "sprint-4": date(2026, 5, 1),
    }
    assert q.group_by("in_sprint").max("due_date") == {
        "sprint-3": date(2026, 4, 20),
        "sprint-4": date(2026, 5, 5),
    }


def test_group_by_nonexistent_field_empty(project_pm_ws):
    assert Query(project_pm_ws).group_by("nope").count() == {}
    assert Query(project_pm_ws).group_by("nope").sum("priority") == {}


def test_group_by_list_field_skipped(project_pm_ws):
    # tags is a list on every task → all packets dropped → empty result
    assert Query(project_pm_ws).group_by("tags").count() == {}


def test_sum_non_numeric_returns_zero(project_pm_ws):
    # Sum on a string field returns 0 per group, no raise.
    result = Query(project_pm_ws).where(type="task").group_by("status").sum("status")
    assert result == {"active": 0, "done": 0}


def test_avg_non_numeric_omits_key(project_pm_ws):
    # Avg on string field → all values skipped → key omitted.
    result = Query(project_pm_ws).where(type="task").group_by("status").avg("status")
    assert result == {}


def test_min_max_non_comparable_omits(project_pm_ws):
    # type is str, so min/max on it works; on non-existent field omits everything.
    assert Query(project_pm_ws).group_by("status").min("nope") == {}
    assert Query(project_pm_ws).group_by("status").max("nope") == {}


def test_count_field_counts_presence(project_pm_ws):
    # group by status across all packets, count packets with due_date field present
    grouped = Query(project_pm_ws).group_by("status")
    result = grouped.aggregate(with_due=Count("due_date"))
    # active: 3 tasks have due_date, epic does not → 3
    # done: 1 task has due_date → 1
    assert result["active"]["with_due"] == 3
    assert result["done"]["with_due"] == 1


def test_aggregate_multi(project_pm_ws):
    grouped = Query(project_pm_ws).where(type="task").group_by("in_sprint")
    result = grouped.aggregate(
        total=Count(),
        pri_sum=Sum("priority"),
        earliest=Min("due_date"),
        latest=Max("due_date"),
        pri_avg=Avg("priority"),
    )
    assert result["sprint-3"] == {
        "total": 2,
        "pri_sum": 4,
        "earliest": date(2026, 4, 10),
        "latest": date(2026, 4, 20),
        "pri_avg": 2.0,
    }
    assert result["sprint-4"]["total"] == 2
    assert result["sprint-4"]["pri_sum"] == 7


def test_group_by_preserves_sorted_order(project_pm_ws):
    result = Query(project_pm_ws).where(type="task").group_by("status").count()
    assert list(result.keys()) == ["active", "done"]


def test_group_by_after_follow(project_pm_ws):
    # Start from task-1, follow who blocks-by back to it (reverse).
    # blocked_by stores uuids, so explicit resolver is required.
    q = (
        Query(project_pm_ws)
        .where(uuid="task-1")
        .follow("blocked_by", direction="reverse", resolver=UuidResolver())
    )
    grouped = q.group_by("status").count()
    # task-3 (active) and task-4 (active) both blocked_by includes task-1
    assert grouped == {"active": 2}


def test_groups_returns_packets(project_pm_ws):
    grouped = Query(project_pm_ws).where(type="task").group_by("status")
    g = grouped.groups()
    assert set(g.keys()) == {"active", "done"}
    assert all(p.id.startswith("tasks/") for packets in g.values() for p in packets)
    assert len(g["active"]) == 3
    assert len(g["done"]) == 1


def test_grouped_query_is_from_query_method(project_pm_ws):
    grouped = Query(project_pm_ws).group_by("status")
    assert isinstance(grouped, GroupedQuery)
    assert grouped.field == "status"
