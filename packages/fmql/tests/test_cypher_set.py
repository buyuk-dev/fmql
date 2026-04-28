from __future__ import annotations

import pytest

from fmql.cypher.compile import parse_cypher
from fmql.cypher.executor import compile_cypher_ast
from fmql.errors import CypherError


@pytest.fixture
def status_ws(make_workspace):
    spec = {
        "tasks/a.md": {"frontmatter": {"uuid": "a", "status": "old"}, "body": "a\n"},
        "tasks/b.md": {"frontmatter": {"uuid": "b", "status": "old"}, "body": "b\n"},
        "tasks/c.md": {"frontmatter": {"uuid": "c", "status": "new"}, "body": "c\n"},
    }
    return make_workspace(spec)


@pytest.fixture
def id_refs_ws(make_workspace):
    spec = {
        "tasks/a.md": {"frontmatter": {"id": 1, "slug": "alpha"}, "body": "a\n"},
        "tasks/b.md": {"frontmatter": {"id": 8, "slug": "bravo"}, "body": "b\n"},
        "tasks/c.md": {
            "frontmatter": {"id": 17, "slug": "charlie", "depends_on": [1, 8]},
            "body": "c\n",
        },
    }
    ws = make_workspace(spec)
    from fmql.resolvers import IdResolver

    ws.resolvers["depends_on"] = IdResolver()
    return ws


def test_set_literal_produces_plan(status_ws):
    ast = parse_cypher('MATCH (t) WHERE t.status = "old" SET t.status = "archived"')
    execution = compile_cypher_ast(ast, status_ws)
    assert execution.plan is not None
    assert execution.result is None
    assert {op.packet_id for op in execution.plan.ops} == {"tasks/a.md", "tasks/b.md"}


def test_set_apply_writes_files(status_ws):
    ast = parse_cypher('MATCH (t) WHERE t.status = "old" SET t.status = "archived"')
    execution = compile_cypher_ast(ast, status_ws)
    report = execution.plan.apply(confirm=False)
    assert sorted(report.written) == ["tasks/a.md", "tasks/b.md"]
    a = status_ws.packets["tasks/a.md"].as_plain()
    assert a["status"] == "archived"
    c = status_ws.packets["tasks/c.md"].as_plain()
    assert c["status"] == "new"


def test_set_with_function_call_migrates_ids_to_slugs(id_refs_ws):
    ast = parse_cypher('MATCH (t) SET t.depends_on = field(resolve(t.depends_on, "id"), "slug")')
    execution = compile_cypher_ast(ast, id_refs_ws)
    report = execution.plan.apply(confirm=False)
    assert "tasks/c.md" in report.written
    c = id_refs_ws.packets["tasks/c.md"].as_plain()
    assert list(c["depends_on"]) == ["alpha", "bravo"]


def test_set_with_slug_shortcut(id_refs_ws):
    # slug(v) requires v to match the slug resolver (via slug field or stem).
    # For id-shaped values, use the field(resolve(..., "id"), "slug") form instead.
    spec_ast = parse_cypher('MATCH (t) WHERE t.id = 1 SET t.label = "first"')
    execution = compile_cypher_ast(spec_ast, id_refs_ws)
    execution.plan.apply(confirm=False)
    assert id_refs_ws.packets["tasks/a.md"].as_plain()["label"] == "first"


def test_set_with_return_runs_both(status_ws):
    ast = parse_cypher('MATCH (t) WHERE t.status = "old" SET t.status = "archived" RETURN t')
    execution = compile_cypher_ast(ast, status_ws)
    assert execution.plan is not None
    assert execution.result is not None
    # Pre-apply: result reflects pre-apply binding (just packet ids, no stored values).
    pids = {row[0] for row in execution.result.rows}
    assert pids == {"tasks/a.md", "tasks/b.md"}


def test_set_undeclared_var_rejected(status_ws):
    ast = parse_cypher("MATCH (t) SET u.x = 1")
    with pytest.raises(CypherError):
        compile_cypher_ast(ast, status_ws)


def test_set_unknown_function_rejected(status_ws):
    ast = parse_cypher("MATCH (t) SET t.x = nope(t.id)")
    with pytest.raises(CypherError):
        compile_cypher_ast(ast, status_ws)


def test_set_field_ref_undeclared_var_rejected(status_ws):
    ast = parse_cypher("MATCH (t) SET t.x = u.y")
    with pytest.raises(CypherError):
        compile_cypher_ast(ast, status_ws)


def test_set_conflict_raises(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"uuid": "a", "next": "b.md"}, "body": "a\n"},
        "b.md": {"frontmatter": {"uuid": "b", "label": "B"}, "body": "b\n"},
        "c.md": {"frontmatter": {"uuid": "c", "next": "b.md"}, "body": "c\n"},
    }
    ws = make_workspace(spec)
    # Two bindings (a→b and c→b) both write a.label = "from c" / "from a" via b.
    # Construct a query that writes to b's label using two different sources:
    # MATCH (x)-[:next]->(b) SET b.from = x.uuid
    ast = parse_cypher("MATCH (x)-[:next]->(b) SET b.label = x.uuid")
    with pytest.raises(CypherError, match="SET conflict"):
        compile_cypher_ast(ast, ws)


def test_set_identical_value_collision_is_noop(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"uuid": "a", "next": "b.md"}, "body": "a\n"},
        "b.md": {"frontmatter": {"uuid": "b"}, "body": "b\n"},
        "c.md": {"frontmatter": {"uuid": "c", "next": "b.md"}, "body": "c\n"},
    }
    ws = make_workspace(spec)
    ast = parse_cypher('MATCH (x)-[:next]->(b) SET b.checked = "yes"')
    execution = compile_cypher_ast(ast, ws)
    assert execution.plan is not None
    pids = [op.packet_id for op in execution.plan.ops]
    assert pids == ["b.md"]
