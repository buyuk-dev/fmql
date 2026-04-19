from __future__ import annotations

import pytest

from fmql.errors import QueryError
from fmql.resolvers import UuidResolver
from fmql.subgraph import Edge, collect_subgraph


def test_single_hop_forward(cycles_ws):
    r = UuidResolver()
    sg = collect_subgraph(cycles_ws, ["a.md"], fields=["blocked_by"], depth=1, resolver=r)
    assert sg.nodes == ("a.md", "b.md")
    assert sg.edges == (Edge(source="a.md", target="b.md", field="blocked_by"),)


def test_multi_hop_forward_star_cycle_safe(cycles_ws):
    r = UuidResolver()
    sg = collect_subgraph(cycles_ws, ["a.md"], fields=["blocked_by"], depth="*", resolver=r)
    assert sg.nodes == ("a.md", "b.md", "c.md")
    assert sg.edges == (
        Edge(source="a.md", target="b.md", field="blocked_by"),
        Edge(source="b.md", target="c.md", field="blocked_by"),
        Edge(source="c.md", target="a.md", field="blocked_by"),
    )


def test_reverse_direction_edges_preserved(cycles_ws):
    r = UuidResolver()
    sg = collect_subgraph(
        cycles_ws,
        ["a.md"],
        fields=["blocked_by"],
        depth="*",
        direction="reverse",
        resolver=r,
    )
    assert set(sg.nodes) == {"a.md", "b.md", "c.md"}
    assert Edge(source="c.md", target="a.md", field="blocked_by") in sg.edges
    assert Edge(source="b.md", target="c.md", field="blocked_by") in sg.edges


def test_include_origin_false(cycles_ws):
    r = UuidResolver()
    sg = collect_subgraph(
        cycles_ws,
        ["a.md"],
        fields=["blocked_by"],
        depth="*",
        resolver=r,
        include_origin=False,
    )
    assert "a.md" not in sg.nodes
    assert set(sg.nodes) == {"b.md", "c.md"}


def test_dedupe_list_valued_field(project_pm_ws):
    r = UuidResolver()
    sg = collect_subgraph(
        project_pm_ws,
        ["tasks/task-4.md"],
        fields=["blocked_by"],
        depth=1,
        resolver=r,
    )
    assert set(sg.nodes) == {"tasks/task-4.md", "tasks/task-1.md", "tasks/task-2.md"}
    assert len(sg.edges) == 2
    assert Edge(source="tasks/task-4.md", target="tasks/task-1.md", field="blocked_by") in sg.edges
    assert Edge(source="tasks/task-4.md", target="tasks/task-2.md", field="blocked_by") in sg.edges


def test_multi_field_traversal(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"uuid": "a", "rel_x": "b", "rel_y": "c"}},
        "b.md": {"frontmatter": {"uuid": "b"}},
        "c.md": {"frontmatter": {"uuid": "c"}},
    }
    ws = make_workspace(spec)
    r = UuidResolver()
    sg = collect_subgraph(ws, ["a.md"], fields=["rel_x", "rel_y"], depth=1, resolver=r)
    assert set(sg.nodes) == {"a.md", "b.md", "c.md"}
    assert Edge(source="a.md", target="b.md", field="rel_x") in sg.edges
    assert Edge(source="a.md", target="c.md", field="rel_y") in sg.edges


def test_invalid_depth_raises(cycles_ws):
    with pytest.raises(QueryError):
        collect_subgraph(cycles_ws, ["a.md"], fields=["blocked_by"], depth="nope")


def test_invalid_direction_raises(cycles_ws):
    with pytest.raises(QueryError):
        collect_subgraph(cycles_ws, ["a.md"], fields=["blocked_by"], direction="sideways")


def test_no_fields_raises(cycles_ws):
    with pytest.raises(QueryError):
        collect_subgraph(cycles_ws, ["a.md"], fields=[])
