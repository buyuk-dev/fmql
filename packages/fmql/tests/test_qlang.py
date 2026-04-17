from __future__ import annotations

import pytest

from fmql.errors import QueryError
from fmql.qlang import compile_query
from fmql.query import Query


def _ids(q) -> set[str]:
    return set(q.ids())


def test_star_matches_all(project_pm_ws):
    q = compile_query("*", project_pm_ws)
    assert _ids(q) == set(project_pm_ws.packets.keys())


def test_eq_string(project_pm_ws):
    q = compile_query('status = "active"', project_pm_ws)
    expected = _ids(Query(project_pm_ws).where(status="active"))
    assert _ids(q) == expected


def test_eq_number(project_pm_ws):
    q = compile_query("priority = 3", project_pm_ws)
    expected = _ids(Query(project_pm_ws).where(priority=3))
    assert _ids(q) == expected


def test_gt(project_pm_ws):
    q = compile_query("priority > 2", project_pm_ws)
    expected = _ids(Query(project_pm_ws).where(priority__gt=2))
    assert _ids(q) == expected


def test_ne(project_pm_ws):
    q = compile_query('status != "done"', project_pm_ws)
    expected = _ids(Query(project_pm_ws).where(status__ne="done"))
    assert _ids(q) == expected


def test_and(project_pm_ws):
    q = compile_query('status = "active" AND priority > 2', project_pm_ws)
    expected = _ids(Query(project_pm_ws).where(status="active", priority__gt=2))
    assert _ids(q) == expected


def test_or(project_pm_ws):
    q = compile_query('status = "active" OR status = "done"', project_pm_ws)
    all_tasks = set()
    for pid, p in project_pm_ws.packets.items():
        s = p.frontmatter.get("status")
        if s in ("active", "done"):
            all_tasks.add(pid)
    assert _ids(q) == all_tasks


def test_not(project_pm_ws):
    q = compile_query('NOT status = "done"', project_pm_ws)
    not_done = {
        pid for pid, p in project_pm_ws.packets.items() if p.frontmatter.get("status") != "done"
    }
    assert _ids(q) == not_done


def test_parens(project_pm_ws):
    q = compile_query('(status = "active" OR status = "done") AND priority > 1', project_pm_ws)
    expected = set()
    for pid, p in project_pm_ws.packets.items():
        s = p.frontmatter.get("status")
        pr = p.frontmatter.get("priority")
        if s in ("active", "done") and isinstance(pr, int) and pr > 1:
            expected.add(pid)
    assert _ids(q) == expected


def test_in_list(project_pm_ws):
    q = compile_query('status IN ["active", "done"]', project_pm_ws)
    expected = {
        pid
        for pid, p in project_pm_ws.packets.items()
        if p.frontmatter.get("status") in ("active", "done")
    }
    assert _ids(q) == expected


def test_is_empty(project_pm_ws):
    q = compile_query("blocked_by IS EMPTY", project_pm_ws)
    for pid in _ids(q):
        p = project_pm_ws.packets[pid]
        assert (
            p.frontmatter.get("blocked_by") in (None, "", [], {})
            or "blocked_by" not in p.frontmatter
        )


def test_is_not_empty(project_pm_ws):
    q = compile_query("blocked_by IS NOT EMPTY", project_pm_ws)
    assert _ids(q) == {"tasks/task-3.md", "tasks/task-4.md"}


def test_is_null_false_for_absent(project_pm_ws):
    q = compile_query("blocked_by IS NULL", project_pm_ws)
    # absent != null, so none
    assert _ids(q) == set()


def test_contains(project_pm_ws):
    q = compile_query('tags CONTAINS "urgent"', project_pm_ws)
    assert _ids(q) == {"tasks/task-3.md"}


def test_matches(project_pm_ws):
    q = compile_query('uuid MATCHES "^task-\\\\d+$"', project_pm_ws)
    # accept any task-N uuid
    assert _ids(q) == {
        "tasks/task-1.md",
        "tasks/task-2.md",
        "tasks/task-3.md",
        "tasks/task-4.md",
    }


def test_keywords_are_case_insensitive(project_pm_ws):
    upper = _ids(compile_query('status = "active" AND priority > 2', project_pm_ws))
    lower = _ids(compile_query('status = "active" and priority > 2', project_pm_ws))
    mixed = _ids(compile_query('tags Contains "urgent"', project_pm_ws))
    assert lower == upper
    assert mixed == {"tasks/task-3.md"}


def test_bool_literal(make_workspace):
    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"flag": True}},
            "b.md": {"frontmatter": {"flag": False}},
        }
    )
    q = compile_query("flag = true", ws)
    assert _ids(q) == {"a.md"}


def test_today_sentinel(project_pm_ws):
    q = compile_query("due_date < today", project_pm_ws)
    # all fixture dates are in 2026-04/05; today's date resolved at compile time.
    from datetime import date

    today_d = date.today()
    expected = {
        pid
        for pid, p in project_pm_ws.packets.items()
        if isinstance(p.frontmatter.get("due_date"), date)
        and p.frontmatter.get("due_date") < today_d
    }
    assert _ids(q) == expected


def test_today_offset(project_pm_ws):
    # just verify it compiles and runs without error
    q = compile_query("due_date > today-30d", project_pm_ws)
    q.ids()


def test_unquoted_string_is_error(project_pm_ws):
    with pytest.raises(QueryError):
        compile_query("status = active", project_pm_ws)


def test_parse_error(project_pm_ws):
    with pytest.raises(QueryError):
        compile_query("this is not valid", project_pm_ws)
