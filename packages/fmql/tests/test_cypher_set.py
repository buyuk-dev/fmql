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


def test_append_op_writes_list(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"uuid": "a", "tags": ["one"]}, "body": "a\n"},
        "b.md": {"frontmatter": {"uuid": "b"}, "body": "b\n"},
    }
    ws = make_workspace(spec)
    ast = parse_cypher('MATCH (t) SET t.tags += "two"')
    plan = compile_cypher_ast(ast, ws).plan
    plan.apply(confirm=False)
    assert ws.packets["a.md"].as_plain()["tags"] == ["one", "two"]
    assert ws.packets["b.md"].as_plain()["tags"] == ["two"]


def test_append_and_set_same_field_conflict(make_workspace):
    spec = {"a.md": {"frontmatter": {"uuid": "a", "tags": []}, "body": "a\n"}}
    ws = make_workspace(spec)
    ast = parse_cypher('MATCH (t) SET t.tags = ["x"], t.tags += "y"')
    with pytest.raises(CypherError, match="conflict"):
        compile_cypher_ast(ast, ws)


def test_append_initializes_when_field_absent(make_workspace):
    """`SET t.f += v` on a missing field initializes to `[v]` (locked-in divergence)."""
    spec = {"a.md": {"frontmatter": {"uuid": "a"}, "body": "a\n"}}
    ws = make_workspace(spec)
    ast = parse_cypher('MATCH (t) SET t.tags += "first"')
    compile_cypher_ast(ast, ws).plan.apply(confirm=False)
    assert ws.packets["a.md"].as_plain()["tags"] == ["first"]


def test_append_with_list_valued_rhs_nests(make_workspace):
    """`+=` appends the RHS as a single element, even when the RHS is itself a list.

    Diverges from Python's `list += list` extend; pinned for the divergences doc.
    """
    spec = {
        "a.md": {
            "frontmatter": {"uuid": "a", "tags": ["one"], "extras": ["two", "three"]},
            "body": "a\n",
        }
    }
    ws = make_workspace(spec)
    ast = parse_cypher("MATCH (t) SET t.tags += t.extras")
    compile_cypher_ast(ast, ws).plan.apply(confirm=False)
    assert list(ws.packets["a.md"].as_plain()["tags"]) == ["one", ["two", "three"]]


def test_append_to_non_list_field_errors(make_workspace):
    """`+=` against a non-list, non-absent field reports an error per packet."""
    spec = {"a.md": {"frontmatter": {"uuid": "a", "tags": "single"}, "body": "a\n"}}
    ws = make_workspace(spec)
    ast = parse_cypher('MATCH (t) SET t.tags += "more"')
    report = compile_cypher_ast(ast, ws).plan.apply(confirm=False)
    assert report.errors and "non-list" in report.errors[0][1]
    assert ws.packets["a.md"].as_plain()["tags"] == "single"


def test_set_list_literal_writes_list(make_workspace):
    spec = {"a.md": {"frontmatter": {"uuid": "a"}, "body": "a\n"}}
    ws = make_workspace(spec)
    ast = parse_cypher('MATCH (t) SET t.tags = ["red", "green"]')
    plan = compile_cypher_ast(ast, ws).plan
    plan.apply(confirm=False)
    assert ws.packets["a.md"].as_plain()["tags"] == ["red", "green"]


def test_set_with_not_toggles_bool(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"uuid": "a", "flag": True}, "body": "a\n"},
        "b.md": {"frontmatter": {"uuid": "b", "flag": False}, "body": "b\n"},
    }
    ws = make_workspace(spec)
    ast = parse_cypher("MATCH (t) SET t.flag = NOT t.flag")
    plan = compile_cypher_ast(ast, ws).plan
    plan.apply(confirm=False)
    assert ws.packets["a.md"].as_plain()["flag"] is False
    assert ws.packets["b.md"].as_plain()["flag"] is True


def test_where_uses_virtual_path(make_workspace):
    spec = {
        "docs/a.md": {"frontmatter": {"uuid": "a"}, "body": "a\n"},
        "docs/b.md": {"frontmatter": {"uuid": "b"}, "body": "b\n"},
    }
    ws = make_workspace(spec)
    ast = parse_cypher('MATCH (t) WHERE t.path = "docs/a.md" SET t.label = "first"')
    plan = compile_cypher_ast(ast, ws).plan
    pids = [op.packet_id for op in plan.ops]
    assert pids == ["docs/a.md"]


def test_where_uses_virtual_slug(make_workspace):
    spec = {
        "docs/alpha.md": {"frontmatter": {"uuid": "a"}, "body": "a\n"},
        "docs/bravo.md": {"frontmatter": {"uuid": "b"}, "body": "b\n"},
    }
    ws = make_workspace(spec)
    ast = parse_cypher('MATCH (t) WHERE t.slug = "alpha" SET t.label = "x"')
    plan = compile_cypher_ast(ast, ws).plan
    pids = [op.packet_id for op in plan.ops]
    assert pids == ["docs/alpha.md"]


def test_where_uses_pseudo_path(make_workspace):
    spec = {
        "docs/a.md": {"frontmatter": {"uuid": "a"}, "body": "a\n"},
        "docs/b.md": {"frontmatter": {"uuid": "b"}, "body": "b\n"},
    }
    ws = make_workspace(spec)
    ast = parse_cypher('MATCH (t) WHERE t._path = "docs/a.md" SET t.label = "first"')
    plan = compile_cypher_ast(ast, ws).plan
    assert [op.packet_id for op in plan.ops] == ["docs/a.md"]


def test_where_uses_pseudo_id(make_workspace):
    ws = make_workspace({"docs/a.md": {"frontmatter": {"uuid": "a"}, "body": "a\n"}})
    ast = parse_cypher('MATCH (t) WHERE t._id = "docs/a.md" SET t.label = "x"')
    plan = compile_cypher_ast(ast, ws).plan
    assert [op.packet_id for op in plan.ops] == ["docs/a.md"]


def test_pseudo_path_not_shadowed_by_frontmatter(make_workspace):
    ws = make_workspace(
        {
            "docs/a.md": {
                "frontmatter": {"uuid": "a", "_path": "lying"},
                "body": "a\n",
            },
        }
    )
    ast = parse_cypher('MATCH (t) WHERE t._path = "docs/a.md" RETURN t')
    result = compile_cypher_ast(ast, ws).result
    assert result.rows == (("docs/a.md",),)


def test_set_on_pseudo_field_rejected(make_workspace):
    ws = make_workspace({"docs/a.md": {"frontmatter": {"uuid": "a"}, "body": "a\n"}})
    with pytest.raises(CypherError, match="cannot SET pseudo-field t._path"):
        compile_cypher_ast(parse_cypher('MATCH (t) SET t._path = "x"'), ws)


def test_remove_on_pseudo_field_rejected(make_workspace):
    ws = make_workspace({"docs/a.md": {"frontmatter": {"uuid": "a"}, "body": "a\n"}})
    with pytest.raises(CypherError, match="cannot REMOVE pseudo-field t._id"):
        compile_cypher_ast(parse_cypher("MATCH (t) REMOVE t._id"), ws)
