from __future__ import annotations

import pytest

from fmq.errors import QueryError
from fmq.resolvers import RelativePathResolver, UuidResolver
from fmq.traversal import follow


def test_forward_depth_1(project_pm_ws):
    r = UuidResolver()
    result = follow(
        project_pm_ws, ["tasks/task-3.md"], field="blocked_by", depth=1, resolver=r
    )
    assert result == ["tasks/task-1.md"]


def test_forward_list_values(project_pm_ws):
    r = UuidResolver()
    result = follow(
        project_pm_ws, ["tasks/task-4.md"], field="blocked_by", depth=1, resolver=r
    )
    assert result == ["tasks/task-1.md", "tasks/task-2.md"]


def test_forward_depth_2(cycles_ws):
    r = UuidResolver()
    # a → b → c (depth 2 from a)
    result = follow(cycles_ws, ["a.md"], field="blocked_by", depth=2, resolver=r)
    assert result == ["b.md", "c.md"]


def test_forward_depth_star_terminates_on_cycle(cycles_ws):
    r = UuidResolver()
    # a → b → c → a (would loop forever without cycle protection)
    result = follow(cycles_ws, ["a.md"], field="blocked_by", depth="*", resolver=r)
    assert result == ["b.md", "c.md"]


def test_include_origin_true(cycles_ws):
    r = UuidResolver()
    result = follow(
        cycles_ws,
        ["a.md"],
        field="blocked_by",
        depth="*",
        resolver=r,
        include_origin=True,
    )
    assert result == ["a.md", "b.md", "c.md"]


def test_include_origin_false_default(project_pm_ws):
    r = UuidResolver()
    result = follow(
        project_pm_ws, ["tasks/task-3.md"], field="blocked_by", depth=1, resolver=r
    )
    assert "tasks/task-3.md" not in result


def test_reverse_single_hop(project_pm_ws):
    r = UuidResolver()
    # Who is blocked by task-1? → task-3 (scalar) and task-4 (list)
    result = follow(
        project_pm_ws,
        ["tasks/task-1.md"],
        field="blocked_by",
        depth=1,
        direction="reverse",
        resolver=r,
    )
    assert result == ["tasks/task-3.md", "tasks/task-4.md"]


def test_reverse_multi_hop(cycles_ws):
    r = UuidResolver()
    # c's blockers (reverse): b, then a.
    result = follow(
        cycles_ws,
        ["c.md"],
        field="blocked_by",
        depth="*",
        direction="reverse",
        resolver=r,
    )
    assert result == ["a.md", "b.md"]


def test_unresolvable_value_dropped(make_workspace):
    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"uuid": "a", "blocked_by": "ghost"}},
            "b.md": {"frontmatter": {"uuid": "b"}},
        }
    )
    r = UuidResolver()
    result = follow(ws, ["a.md"], field="blocked_by", depth=1, resolver=r)
    assert result == []


def test_missing_field_empty(project_pm_ws):
    r = UuidResolver()
    # task-1 has no blocked_by field.
    result = follow(
        project_pm_ws, ["tasks/task-1.md"], field="blocked_by", depth=1, resolver=r
    )
    assert result == []


def test_invalid_direction(project_pm_ws):
    r = UuidResolver()
    with pytest.raises(QueryError):
        follow(
            project_pm_ws,
            ["tasks/task-1.md"],
            field="blocked_by",
            direction="sideways",
            resolver=r,
        )


def test_reverse_index_cached(project_pm_ws):
    r = UuidResolver()
    # Build cache
    idx1 = project_pm_ws.reverse_index("blocked_by", r)
    idx2 = project_pm_ws.reverse_index("blocked_by", r)
    assert idx1 is idx2


def test_uses_workspace_default_resolver(paths_refs_ws):
    # No resolver override → workspace.default_resolver (RelativePathResolver)
    result = follow(paths_refs_ws, ["tasks/a.md"], field="depends_on", depth=1)
    assert result == ["tasks/b.md"]


def test_uses_workspace_field_resolver(make_workspace):
    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"uuid": "a", "ref": "b"}},
            "b.md": {"frontmatter": {"uuid": "b"}},
        }
    )
    ws.resolvers["ref"] = UuidResolver()
    result = follow(ws, ["a.md"], field="ref", depth=1)
    assert result == ["b.md"]


def test_default_resolver_set_on_workspace(project_pm_ws):
    assert isinstance(project_pm_ws.default_resolver, RelativePathResolver)
