from __future__ import annotations

import pytest

from fmq.cypher import compile_cypher
from fmq.cypher.ast import (
    NodePat,
    ReturnCount,
    ReturnField,
    ReturnVar,
)
from fmq.cypher.compile import parse_cypher
from fmq.errors import CypherError, CypherUnsupported
from fmq.query import Query
from fmq.resolvers import UuidResolver


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
        'MATCH (a)-[:f]->(b) WHERE a.status = "active" AND a.priority > 2 '
        "RETURN a, a.status, b"
    )
    assert ast.where is not None
    assert ast.returns == (ReturnVar("a"), ReturnField("a", "status"), ReturnVar("b"))


def test_parse_count_return():
    ast = parse_cypher("MATCH (a)-[:f]->(b) RETURN count(a)")
    assert ast.returns == (ReturnCount("a"),)


@pytest.mark.parametrize(
    "txt",
    [
        "CREATE (a) RETURN a",
        "MERGE (a) RETURN a",
        "DELETE a",
        "DETACH DELETE a",
        "MATCH (a)-[:f]->(b) SET a.x = 1 RETURN a",
        "OPTIONAL MATCH (a)-[:f]->(b) RETURN a",
        "MATCH (a)-[:f]->(b) WITH a RETURN a",
        "UNWIND [1,2] AS x RETURN x",
        "MATCH p = shortestPath((a)-[:f*]->(b)) RETURN p",
        "MATCH (a) RETURN a ORDER BY a.x",
        "MATCH (a) RETURN a LIMIT 10",
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
        parse_cypher('MATCH (a)-[:f]->(b) WHERE a.status = bananas RETURN a')


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
    res = compile_cypher(
        "MATCH (a)-[:blocked_by*2..3]->(b) RETURN a, b", blocked_ws
    )
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
        'MATCH (a)-[:blocked_by]->(b) WHERE a.priority > 2 RETURN a',
        project_pm_ws,
    )
    # task-3 (priority=5) and task-4 (priority=2) both have blocked_by.
    # Only task-3 has priority > 2.
    assert _set_rows(res) == {("tasks/task-3.md",)}


def test_exec_return_field(project_pm_ws):
    project_pm_ws.resolvers["blocked_by"] = UuidResolver()
    res = compile_cypher(
        "MATCH (a)-[:blocked_by]->(b) RETURN a.uuid", project_pm_ws
    )
    rows = _set_rows(res)
    assert ("task-3",) in rows
    assert ("task-4",) in rows


def test_exec_count(blocked_ws):
    res = compile_cypher(
        "MATCH (a)-[:blocked_by]->(b) RETURN count(a)", blocked_ws
    )
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
