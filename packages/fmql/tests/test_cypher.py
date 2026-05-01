from __future__ import annotations

import pytest

from fmql.cypher import compile_cypher
from fmql.cypher.ast import (
    NodePat,
    ReturnCount,
    ReturnField,
    ReturnVar,
)
from fmql.cypher.compile import parse_cypher
from fmql.errors import CypherError, CypherUnsupported
from fmql.query import Query
from fmql.resolvers import UuidResolver


def _set_rows(result):
    return {tuple(row) for row in result.rows}


# ---------- parsing ----------


def test_parse_single_hop():
    ast = parse_cypher("MATCH (a)-[:f]->(b) RETURN a")
    assert [n.var for n in ast.pattern.nodes] == ["a", "b"]
    assert ast.pattern.rels[0].field == "f"
    assert ast.pattern.rels[0].min_hops == 1
    assert ast.pattern.rels[0].max_hops == 1
    assert ast.returns == (ReturnVar("a"),)


def test_parse_chain():
    ast = parse_cypher("MATCH (a)-[:f1]->(b)-[:f2]->(c) RETURN a, b, c")
    assert [n.var for n in ast.pattern.nodes] == ["a", "b", "c"]
    assert [r.field for r in ast.pattern.rels] == ["f1", "f2"]


def test_parse_var_length_unbounded():
    ast = parse_cypher("MATCH (a)-[:f*]->(b) RETURN a")
    rel = ast.pattern.rels[0]
    assert rel.min_hops == 1
    assert rel.max_hops is None


def test_parse_var_length_range():
    ast = parse_cypher("MATCH (a)-[:f*1..3]->(b) RETURN a")
    rel = ast.pattern.rels[0]
    assert rel.min_hops == 1
    assert rel.max_hops == 3


def test_parse_label_is_ignored():
    ast = parse_cypher("MATCH (a:Task)-[:f]->(b:Epic) RETURN a")
    assert ast.pattern.nodes[0] == NodePat(var="a", label="Task")
    assert ast.pattern.nodes[1] == NodePat(var="b", label="Epic")


def test_parse_where_and_return_forms():
    ast = parse_cypher(
        'MATCH (a)-[:f]->(b) WHERE a.status = "active" AND a.priority > 2 ' "RETURN a, a.status, b"
    )
    assert ast.where is not None
    assert ast.returns == (ReturnVar("a"), ReturnField("a", "status"), ReturnVar("b"))


def test_parse_count_return():
    ast = parse_cypher("MATCH (a)-[:f]->(b) RETURN count(a)")
    assert ast.returns == (ReturnCount("a"),)


def test_parse_keywords_are_case_insensitive():
    ast = parse_cypher('match (a)-[:f]->(b) where a.x contains "y" return count(a)')
    assert [n.var for n in ast.pattern.nodes] == ["a", "b"]
    assert ast.returns == (ReturnCount("a"),)
    assert ast.where is not None


@pytest.mark.parametrize(
    "txt",
    [
        "CREATE (a) RETURN a",
        "MERGE (a) RETURN a",
        "DELETE a",
        "DETACH DELETE a",
        "OPTIONAL MATCH (a)-[:f]->(b) RETURN a",
        "MATCH (a)-[:f]->(b) WITH a RETURN a",
        "UNWIND [1,2] AS x RETURN x",
        "MATCH p = shortestPath((a)-[:f*]->(b)) RETURN p",
        "MATCH (a) RETURN a SKIP 5",
        "MATCH (a) RETURN sum(a)",
        "MATCH (a) RETURN avg(a.x)",
    ],
)
def test_unsupported_constructs_raise(txt):
    with pytest.raises(CypherUnsupported):
        parse_cypher(txt)


def test_reverse_direction_unsupported():
    with pytest.raises(CypherUnsupported):
        parse_cypher("MATCH (a)<-[:f]-(b) RETURN a")


def test_multi_pattern_match_unsupported():
    with pytest.raises(CypherUnsupported):
        parse_cypher("MATCH (a), (b) RETURN a")


def test_unquoted_string_value_raises():
    with pytest.raises(CypherError):
        parse_cypher("MATCH (a)-[:f]->(b) WHERE a.status = bananas RETURN a")


# ---------- SET clause parsing ----------


def test_parse_set_literal():
    from fmql.cypher.ast import LiteralExpr, SetItem

    ast = parse_cypher("MATCH (t) SET t.x = 1")
    assert ast.set_items == (SetItem(var="t", field="x", expr=LiteralExpr(value=1)),)
    assert ast.returns == ()


def test_parse_set_multiple_assignments():
    ast = parse_cypher('MATCH (t) SET t.x = "a", t.y = 2')
    assert len(ast.set_items) == 2
    assert ast.set_items[0].field == "x"
    assert ast.set_items[1].field == "y"


def test_parse_set_qualified_ref():
    from fmql.cypher.ast import FieldRef

    ast = parse_cypher("MATCH (a)-[:f]->(b) SET a.next = b.next")
    assert ast.set_items[0].expr == FieldRef(var="b", field="next")


def test_parse_set_function_call():
    from fmql.cypher.ast import CallExpr, FieldRef

    ast = parse_cypher("MATCH (t) SET t.deps = slug(t.deps)")
    expr = ast.set_items[0].expr
    assert isinstance(expr, CallExpr)
    assert expr.name == "slug"
    assert expr.args == (FieldRef(var="t", field="deps"),)


def test_parse_set_nested_function_call():
    from fmql.cypher.ast import CallExpr

    ast = parse_cypher('MATCH (t) SET t.x = field(resolve(t.deps, "id"), "slug")')
    outer = ast.set_items[0].expr
    assert isinstance(outer, CallExpr)
    assert outer.name == "field"
    inner = outer.args[0]
    assert isinstance(inner, CallExpr)
    assert inner.name == "resolve"


def test_parse_set_with_where():
    ast = parse_cypher('MATCH (t) WHERE t.status = "old" SET t.status = "archived"')
    assert ast.where is not None
    assert len(ast.set_items) == 1


def test_parse_set_with_return():
    ast = parse_cypher("MATCH (t) SET t.x = 1 RETURN t")
    assert len(ast.set_items) == 1
    assert len(ast.returns) == 1


def test_parse_no_set_no_return_passes_grammar_but_validate_rejects():
    from fmql.cypher.executor import compile_cypher_ast

    ast = parse_cypher("MATCH (t)")
    # Grammar permits this; validator inside the executor should reject.
    # We don't need a workspace to validate — pass any minimal one.
    # Use a dummy that won't be touched: validation happens before enumeration uses ws.
    import tempfile

    from fmql.workspace import Workspace as WS

    with tempfile.TemporaryDirectory() as td:
        ws = WS(td)
        with pytest.raises(CypherError):
            compile_cypher_ast(ast, ws)


def test_parse_order_by_without_return_rejected():
    from fmql.cypher.executor import compile_cypher_ast

    ast = parse_cypher("MATCH (t) SET t.x = 1 ORDER BY t.x")
    import tempfile

    from fmql.workspace import Workspace as WS

    with tempfile.TemporaryDirectory() as td:
        ws = WS(td)
        with pytest.raises(CypherError):
            compile_cypher_ast(ast, ws)


# ---------- execution ----------


@pytest.fixture
def blocked_ws(cycles_ws):
    cycles_ws.resolvers["blocked_by"] = UuidResolver()
    return cycles_ws


def test_exec_single_hop(blocked_ws):
    res = compile_cypher("MATCH (a)-[:blocked_by]->(b) RETURN a, b", blocked_ws)
    assert _set_rows(res) == {
        ("a.md", "b.md"),
        ("b.md", "c.md"),
        ("c.md", "a.md"),
    }


def test_exec_self_cycle(blocked_ws):
    res = compile_cypher("MATCH (a)-[:blocked_by*]->(a) RETURN a", blocked_ws)
    assert _set_rows(res) == {("a.md",), ("b.md",), ("c.md",)}


def test_exec_var_length_range(blocked_ws):
    # Cycle a→b→c→a: from a, 2 hops → c; 3 hops → a. Range 2..3 yields {c, a}.
    res = compile_cypher("MATCH (a)-[:blocked_by*2..3]->(b) RETURN a, b", blocked_ws)
    rows = _set_rows(res)
    # Each origin sees {origin_itself_via_3, hop2_target}
    assert ("a.md", "a.md") in rows
    assert ("a.md", "c.md") in rows


def test_exec_chain(blocked_ws):
    res = compile_cypher(
        "MATCH (a)-[:blocked_by]->(b)-[:blocked_by]->(c) RETURN a, b, c", blocked_ws
    )
    assert _set_rows(res) == {
        ("a.md", "b.md", "c.md"),
        ("b.md", "c.md", "a.md"),
        ("c.md", "a.md", "b.md"),
    }


def test_exec_where_filters(project_pm_ws):
    project_pm_ws.resolvers["blocked_by"] = UuidResolver()
    res = compile_cypher(
        "MATCH (a)-[:blocked_by]->(b) WHERE a.priority > 2 RETURN a",
        project_pm_ws,
    )
    # task-3 (priority=5) and task-4 (priority=2) both have blocked_by.
    # Only task-3 has priority > 2.
    assert _set_rows(res) == {("tasks/task-3.md",)}


def test_exec_return_field(project_pm_ws):
    project_pm_ws.resolvers["blocked_by"] = UuidResolver()
    res = compile_cypher("MATCH (a)-[:blocked_by]->(b) RETURN a.uuid", project_pm_ws)
    rows = _set_rows(res)
    assert ("task-3",) in rows
    assert ("task-4",) in rows


def test_exec_count(blocked_ws):
    res = compile_cypher("MATCH (a)-[:blocked_by]->(b) RETURN count(a)", blocked_ws)
    assert res.is_scalar is True
    assert res.scalar == 3
    assert res.columns == ("count(a)",)


def test_undeclared_return_var(blocked_ws):
    with pytest.raises(CypherError):
        compile_cypher("MATCH (a)-[:blocked_by]->(b) RETURN c", blocked_ws)


def test_undeclared_where_var(blocked_ws):
    with pytest.raises(CypherError):
        compile_cypher(
            'MATCH (a)-[:blocked_by]->(b) WHERE z.status = "x" RETURN a',
            blocked_ws,
        )


def test_where_requires_qualified_ident(blocked_ws):
    # The grammar requires `IDENT.IDENT` in WHERE, so a bare `status = "x"`
    # is a parse error (CypherError).
    with pytest.raises(CypherError):
        compile_cypher(
            'MATCH (a)-[:blocked_by]->(b) WHERE status = "active" RETURN a',
            blocked_ws,
        )


# ---------- Query.cypher() ----------


def test_query_cypher_single_var(blocked_ws):
    q = Query(blocked_ws).cypher("MATCH (a)-[:blocked_by*]->(a) RETURN a")
    assert set(q.ids()) == {"a.md", "b.md", "c.md"}


def test_query_cypher_multi_var_rejected(blocked_ws):
    with pytest.raises(CypherUnsupported):
        Query(blocked_ws).cypher("MATCH (a)-[:blocked_by]->(b) RETURN a, b")


def test_query_cypher_count_rejected(blocked_ws):
    with pytest.raises(CypherUnsupported):
        Query(blocked_ws).cypher("MATCH (a)-[:blocked_by]->(b) RETURN count(a)")


def test_query_cypher_field_return_rejected(blocked_ws):
    with pytest.raises(CypherUnsupported):
        Query(blocked_ws).cypher("MATCH (a)-[:blocked_by]->(b) RETURN a.uuid")


# ---------- ORDER BY ----------


def test_parse_order_by_single_key():
    ast = parse_cypher("MATCH (a) RETURN a ORDER BY a.priority DESC")
    assert len(ast.order_by) == 1
    k = ast.order_by[0]
    assert k.field == "a.priority"
    assert k.desc is True
    assert k.nulls == "auto"


def test_parse_order_by_multi_key_and_nulls():
    ast = parse_cypher("MATCH (a) RETURN a ORDER BY a.status ASC, a.priority DESC NULLS LAST")
    fields = [(k.field, k.desc, k.nulls) for k in ast.order_by]
    assert fields == [("a.status", False, "auto"), ("a.priority", True, "last")]


def test_exec_order_by_var(project_pm_ws):
    res = compile_cypher("MATCH (a) RETURN a ORDER BY a.priority", project_pm_ws)
    # Rows are single-tuple (packet_id,). Extract the priority of each.
    priorities = [project_pm_ws.packets[row[0]].as_plain().get("priority") for row in res.rows]
    # Non-null numeric ascending, strings bucketed separately, nulls last.
    # Numerics first: 1, 2, 3, 5; then string 'high'; then nulls (none packet, epic).
    assert priorities[:4] == [1, 2, 3, 5]


def test_exec_order_by_desc_nulls_last(project_pm_ws):
    res = compile_cypher(
        "MATCH (a) RETURN a.uuid ORDER BY a.priority DESC NULLS LAST",
        project_pm_ws,
    )
    numeric_rows = [row for row in res.rows if row[0] is not None]
    # First non-null numeric rows should be strictly descending among numerics.
    nums = []
    for (uuid,) in numeric_rows:
        p = next(
            (
                pkt.as_plain().get("priority")
                for pkt in project_pm_ws.packets.values()
                if pkt.as_plain().get("uuid") == uuid
            ),
            None,
        )
        if isinstance(p, (int, float)):
            nums.append(p)
    assert nums == sorted(nums, reverse=True)


def test_exec_order_by_references_undeclared_var(project_pm_ws):
    with pytest.raises(CypherError):
        compile_cypher("MATCH (a) RETURN a ORDER BY z.priority", project_pm_ws)


def test_exec_order_by_unprojected_field(project_pm_ws):
    # ORDER BY can reference a field that isn't in RETURN.
    res = compile_cypher(
        "MATCH (a) RETURN a.uuid ORDER BY a.priority DESC NULLS LAST",
        project_pm_ws,
    )
    # Just verifying it executes and returns all packets.
    assert len(res.rows) == len(project_pm_ws.packets)


def test_exec_order_by_heterogeneous_types(make_workspace):
    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"k": 1}},
            "b.md": {"frontmatter": {"k": "zebra"}},
            "c.md": {"frontmatter": {"k": True}},
            "d.md": {"frontmatter": {"k": 2}},
        }
    )
    res = compile_cypher("MATCH (a) RETURN a ORDER BY a.k", ws)
    assert len(res.rows) == 4


def test_exec_order_by_date_field(make_workspace):
    from datetime import date

    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"due": date(2026, 5, 10)}},
            "b.md": {"frontmatter": {"due": date(2026, 4, 1)}},
            "c.md": {"frontmatter": {"due": date(2026, 7, 15)}},
        }
    )
    res = compile_cypher("MATCH (a) RETURN a ORDER BY a.due", ws)
    values = [ws.packets[row[0]].as_plain()["due"] for row in res.rows]
    assert values == [date(2026, 4, 1), date(2026, 5, 10), date(2026, 7, 15)]


def test_exec_order_by_unknown_field_keeps_all(make_workspace):
    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"x": 1}},
            "b.md": {"frontmatter": {"x": 2}},
        }
    )
    res = compile_cypher("MATCH (a) RETURN a ORDER BY a.nonexistent", ws)
    assert len(res.rows) == 2


def test_parse_order_by_invalid_direction_rejected():
    with pytest.raises(CypherError):
        parse_cypher("MATCH (a) RETURN a ORDER BY a.priority BOGUS")


# ---------- LIMIT ----------


def test_parse_limit_basic():
    ast = parse_cypher("MATCH (a) RETURN a LIMIT 5")
    assert ast.limit == 5


def test_parse_limit_zero():
    ast = parse_cypher("MATCH (a) RETURN a LIMIT 0")
    assert ast.limit == 0


def test_parse_limit_case_insensitive():
    ast = parse_cypher("MATCH (a) RETURN a limit 3")
    assert ast.limit == 3


def test_parse_limit_with_order_by():
    ast = parse_cypher("MATCH (a) RETURN a ORDER BY a.priority DESC LIMIT 2")
    assert ast.limit == 2
    assert len(ast.order_by) == 1


def test_parse_limit_negative_grammar_rejects():
    with pytest.raises(CypherError):
        parse_cypher("MATCH (a) RETURN a LIMIT -5")


def test_exec_limit_caps_rows(project_pm_ws):
    full = compile_cypher("MATCH (a) RETURN a", project_pm_ws)
    assert len(full.rows) > 2
    res = compile_cypher("MATCH (a) RETURN a LIMIT 2", project_pm_ws)
    assert len(res.rows) == 2


def test_exec_limit_zero_returns_empty(project_pm_ws):
    res = compile_cypher("MATCH (a) RETURN a LIMIT 0", project_pm_ws)
    assert res.rows == ()


def test_exec_limit_larger_than_result(project_pm_ws):
    full = compile_cypher("MATCH (a) RETURN a", project_pm_ws)
    res = compile_cypher("MATCH (a) RETURN a LIMIT 9999", project_pm_ws)
    assert len(res.rows) == len(full.rows)


def test_exec_limit_with_order_by_takes_top_n(project_pm_ws):
    res = compile_cypher(
        'MATCH (a) WHERE a.type = "task" RETURN a.uuid ORDER BY a.priority DESC LIMIT 2',
        project_pm_ws,
    )
    uuids = [row[0] for row in res.rows]
    assert uuids == ["task-3", "task-1"]


def test_exec_limit_without_return_rejected(project_pm_ws):
    from fmql.cypher.ast import CypherAST
    from fmql.cypher.executor import compile_cypher_ast

    ast = parse_cypher("MATCH (a) SET a.x = 1")
    bad = CypherAST(pattern=ast.pattern, returns=(), set_items=ast.set_items, limit=5)
    with pytest.raises(CypherError, match="LIMIT requires a RETURN clause"):
        compile_cypher_ast(bad, project_pm_ws)


def test_exec_limit_negative_rejected_at_validate(project_pm_ws):
    from fmql.cypher.ast import CypherAST
    from fmql.cypher.executor import compile_cypher_ast

    ast = parse_cypher("MATCH (a) RETURN a")
    bad = CypherAST(
        pattern=ast.pattern,
        returns=ast.returns,
        limit=-1,
    )
    with pytest.raises(CypherError, match="LIMIT must be non-negative"):
        compile_cypher_ast(bad, project_pm_ws)


def test_exec_limit_count_keeps_scalar(project_pm_ws):
    res = compile_cypher("MATCH (a) RETURN count(a) LIMIT 1", project_pm_ws)
    assert res.is_scalar is True
    assert len(res.rows) == 1
    assert res.scalar == res.rows[0][0]


def test_exec_limit_count_zero_clears_scalar(project_pm_ws):
    res = compile_cypher("MATCH (a) RETURN count(a) LIMIT 0", project_pm_ws)
    assert res.rows == ()
    assert res.is_scalar is False
    assert res.scalar is None


def test_exec_limit_with_set_applies_writes_to_all(make_workspace):
    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"x": 1}},
            "b.md": {"frontmatter": {"x": 2}},
            "c.md": {"frontmatter": {"x": 3}},
        }
    )
    from fmql.cypher.executor import compile_cypher_ast

    ast = parse_cypher("MATCH (a) SET a.tag = 1 RETURN a LIMIT 1")
    execution = compile_cypher_ast(ast, ws)
    assert execution.plan is not None
    assert len(execution.plan.ops) == 3  # all three packets get SET
    assert execution.result is not None
    assert len(execution.result.rows) == 1


# ---------- WHERE operator coverage ----------


def test_exec_where_eq_string(project_pm_ws):
    res = compile_cypher('MATCH (a) WHERE a.status = "active" RETURN a', project_pm_ws)
    pids = {row[0] for row in res.rows}
    expected = {
        pid for pid, p in project_pm_ws.packets.items() if p.as_plain().get("status") == "active"
    }
    assert pids == expected


def test_exec_where_in_list(project_pm_ws):
    res = compile_cypher('MATCH (a) WHERE a.status IN ["active", "done"] RETURN a', project_pm_ws)
    pids = {row[0] for row in res.rows}
    expected = {
        pid
        for pid, p in project_pm_ws.packets.items()
        if p.as_plain().get("status") in ("active", "done")
    }
    assert pids == expected


def test_exec_where_is_empty(project_pm_ws):
    res = compile_cypher("MATCH (a) WHERE a.blocked_by IS EMPTY RETURN a", project_pm_ws)
    for row in res.rows:
        plain = project_pm_ws.packets[row[0]].as_plain()
        assert plain.get("blocked_by") in (None, "", [], {}) or "blocked_by" not in plain


def test_exec_where_is_not_empty(project_pm_ws):
    res = compile_cypher("MATCH (a) WHERE a.blocked_by IS NOT EMPTY RETURN a", project_pm_ws)
    pids = {row[0] for row in res.rows}
    assert pids == {"tasks/task-3.md", "tasks/task-4.md"}


def test_exec_where_is_null_matches_absent_in_cypher(project_pm_ws):
    res = compile_cypher("MATCH (a) WHERE a.blocked_by IS NULL RETURN a", project_pm_ws)
    pids = {row[0] for row in res.rows}
    expected = {
        pid for pid, p in project_pm_ws.packets.items() if p.as_plain().get("blocked_by") is None
    }
    assert pids == expected


def test_exec_where_is_not_null(project_pm_ws):
    res = compile_cypher("MATCH (a) WHERE a.blocked_by IS NOT NULL RETURN a", project_pm_ws)
    pids = {row[0] for row in res.rows}
    assert pids == {"tasks/task-3.md", "tasks/task-4.md"}


def test_exec_where_is_null_and_is_not_null_partition(project_pm_ws):
    null_res = compile_cypher("MATCH (a) WHERE a.blocked_by IS NULL RETURN a", project_pm_ws)
    not_null_res = compile_cypher(
        "MATCH (a) WHERE a.blocked_by IS NOT NULL RETURN a", project_pm_ws
    )
    null_pids = {row[0] for row in null_res.rows}
    not_null_pids = {row[0] for row in not_null_res.rows}
    assert null_pids.isdisjoint(not_null_pids)
    assert null_pids | not_null_pids == set(project_pm_ws.packets.keys())


def test_exec_where_eq_null_matches_absent_or_explicit(null_partition_ws):
    res = compile_cypher("MATCH (a) WHERE a.blocked_by = null RETURN a", null_partition_ws)
    pids = {row[0] for row in res.rows}
    assert pids == {"absent.md", "explicit.md"}


def test_exec_where_ne_null_matches_present_non_null(null_partition_ws):
    res = compile_cypher("MATCH (a) WHERE a.blocked_by != null RETURN a", null_partition_ws)
    pids = {row[0] for row in res.rows}
    assert pids == {"present.md"}


def test_exec_where_eq_null_and_ne_null_partition(null_partition_ws):
    eq = compile_cypher("MATCH (a) WHERE a.blocked_by = null RETURN a", null_partition_ws)
    ne = compile_cypher("MATCH (a) WHERE a.blocked_by != null RETURN a", null_partition_ws)
    eq_pids = {row[0] for row in eq.rows}
    ne_pids = {row[0] for row in ne.rows}
    assert eq_pids.isdisjoint(ne_pids)
    assert eq_pids | ne_pids == set(null_partition_ws.packets.keys())


def test_exec_where_not_in_list(project_pm_ws):
    res = compile_cypher(
        'MATCH (a) WHERE a.status NOT IN ["active", "done"] RETURN a', project_pm_ws
    )
    in_res = compile_cypher(
        'MATCH (a) WHERE a.status IN ["active", "done"] RETURN a', project_pm_ws
    )
    not_in_pids = {row[0] for row in res.rows}
    in_pids = {row[0] for row in in_res.rows}
    assert not_in_pids.isdisjoint(in_pids)
    assert not_in_pids | in_pids == set(project_pm_ws.packets.keys())


def test_exec_where_not_in_list_with_null(make_workspace):
    ws = make_workspace(
        {
            "absent.md": {"frontmatter": {"uuid": "absent"}},
            "explicit.md": {"frontmatter": {"uuid": "explicit", "status": None}},
            "active.md": {"frontmatter": {"uuid": "active", "status": "active"}},
            "other.md": {"frontmatter": {"uuid": "other", "status": "blocked"}},
        }
    )
    res = compile_cypher('MATCH (a) WHERE a.status NOT IN [null, "active"] RETURN a', ws)
    pids = {row[0] for row in res.rows}
    assert pids == {"other.md"}


def test_exec_where_in_list_only_null(make_workspace):
    ws = make_workspace(
        {
            "absent.md": {"frontmatter": {"uuid": "absent"}},
            "explicit.md": {"frontmatter": {"uuid": "explicit", "status": None}},
            "active.md": {"frontmatter": {"uuid": "active", "status": "active"}},
        }
    )
    res = compile_cypher("MATCH (a) WHERE a.status IN [null] RETURN a", ws)
    pids = {row[0] for row in res.rows}
    assert pids == {"absent.md", "explicit.md"}


def test_exec_where_in_list_with_null_mixed(make_workspace):
    ws = make_workspace(
        {
            "absent.md": {"frontmatter": {"uuid": "absent"}},
            "explicit.md": {"frontmatter": {"uuid": "explicit", "status": None}},
            "active.md": {"frontmatter": {"uuid": "active", "status": "active"}},
            "done.md": {"frontmatter": {"uuid": "done", "status": "done"}},
        }
    )
    res = compile_cypher('MATCH (a) WHERE a.status IN [null, "active"] RETURN a', ws)
    pids = {row[0] for row in res.rows}
    assert pids == {"absent.md", "explicit.md", "active.md"}


@pytest.mark.parametrize(
    "txt",
    [
        'MATCH (a) WHERE a.status NOT IN ["x"] RETURN a',
        'MATCH (a) WHERE a.status NOT  IN ["x"] RETURN a',
        'MATCH (a) WHERE a.status not in ["x"] RETURN a',
        'MATCH (a) WHERE a.status Not In ["x"] RETURN a',
        'MATCH (a) WHERE a.status NOT\tIN ["x"] RETURN a',
    ],
)
def test_parse_not_in_whitespace_and_case(txt):
    ast = parse_cypher(txt)
    assert ast.where is not None


@pytest.mark.parametrize(
    "txt",
    [
        "MATCH (a) WHERE a.x IS NOT NULL RETURN a",
        "MATCH (a) WHERE a.x IS  NOT  NULL RETURN a",
        "MATCH (a) WHERE a.x is not null RETURN a",
        "MATCH (a) WHERE a.x Is Not Null RETURN a",
    ],
)
def test_parse_is_not_null_whitespace_and_case(txt):
    ast = parse_cypher(txt)
    assert ast.where is not None


@pytest.mark.parametrize("token", ["null", "NULL", "Null", "nUlL"])
def test_parse_null_literal_case_insensitive(token):
    ast = parse_cypher(f"MATCH (a) WHERE a.x = {token} RETURN a")
    assert ast.where is not None


def test_exec_where_not_in_no_regression_with_paren_not(project_pm_ws):
    paren = compile_cypher('MATCH (a) WHERE NOT (a.status IN ["active"]) RETURN a', project_pm_ws)
    fused = compile_cypher('MATCH (a) WHERE a.status NOT IN ["active"] RETURN a', project_pm_ws)
    paren_pids = {row[0] for row in paren.rows}
    fused_pids = {row[0] for row in fused.rows}
    assert paren_pids == fused_pids


def test_exec_where_contains(project_pm_ws):
    res = compile_cypher('MATCH (a) WHERE a.tags CONTAINS "urgent" RETURN a', project_pm_ws)
    pids = {row[0] for row in res.rows}
    assert pids == {"tasks/task-3.md"}


def test_exec_where_matches(project_pm_ws):
    res = compile_cypher('MATCH (a) WHERE a.uuid MATCHES "^task-\\\\d+$" RETURN a', project_pm_ws)
    pids = {row[0] for row in res.rows}
    assert pids == {
        "tasks/task-1.md",
        "tasks/task-2.md",
        "tasks/task-3.md",
        "tasks/task-4.md",
    }


def test_exec_where_not(project_pm_ws):
    res = compile_cypher('MATCH (a) WHERE NOT a.status = "done" RETURN a', project_pm_ws)
    pids = {row[0] for row in res.rows}
    expected = {
        pid for pid, p in project_pm_ws.packets.items() if p.as_plain().get("status") != "done"
    }
    assert pids == expected


def test_exec_where_keywords_case_insensitive(project_pm_ws):
    upper = compile_cypher(
        'MATCH (a) WHERE a.status = "active" AND a.priority > 2 RETURN a', project_pm_ws
    )
    lower = compile_cypher(
        'MATCH (a) WHERE a.status = "active" and a.priority > 2 return a', project_pm_ws
    )
    assert _set_rows(upper) == _set_rows(lower)


def test_exec_where_today_sentinel(project_pm_ws):
    from datetime import date

    res = compile_cypher("MATCH (a) WHERE a.due_date < today+0d RETURN a", project_pm_ws)
    pids = {row[0] for row in res.rows}
    today_d = date.today()
    expected = {
        pid
        for pid, p in project_pm_ws.packets.items()
        if isinstance(p.as_plain().get("due_date"), date) and p.as_plain().get("due_date") < today_d
    }
    assert pids == expected
