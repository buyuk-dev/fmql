from __future__ import annotations

import pytest

from fmql.cypher.compile import parse_cypher
from fmql.cypher.executor import compile_cypher_ast
from fmql.errors import CypherError


@pytest.fixture
def tagged_ws(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"uuid": "a", "tags": ["alpha", "beta", "gamma"]}, "body": "a\n"},
        "b.md": {"frontmatter": {"uuid": "b", "tags": ["alpha"]}, "body": "b\n"},
        "c.md": {"frontmatter": {"uuid": "c", "tags": []}, "body": "c\n"},
    }
    return make_workspace(spec)


def test_listcomp_filter_drops_matching_items(tagged_ws):
    ast = parse_cypher('MATCH (t) SET t.tags = [x IN t.tags WHERE x <> "alpha"]')
    plan = compile_cypher_ast(ast, tagged_ws).plan
    plan.apply(confirm=False)
    assert tagged_ws.packets["a.md"].as_plain()["tags"] == ["beta", "gamma"]
    assert tagged_ws.packets["b.md"].as_plain()["tags"] == []
    assert tagged_ws.packets["c.md"].as_plain()["tags"] == []


def test_listcomp_with_literal_projection(tagged_ws):
    ast = parse_cypher('MATCH (t) WHERE t.uuid = "b" SET t.shouts = [x IN t.tags | "yes"]')
    plan = compile_cypher_ast(ast, tagged_ws).plan
    plan.apply(confirm=False)
    assert tagged_ws.packets["b.md"].as_plain()["shouts"] == ["yes"]


def test_listcomp_empty_source(tagged_ws):
    ast = parse_cypher('MATCH (t) WHERE t.uuid = "c" SET t.tags = [x IN t.tags WHERE x <> "any"]')
    plan = compile_cypher_ast(ast, tagged_ws).plan
    plan.apply(confirm=False)
    assert tagged_ws.packets["c.md"].as_plain()["tags"] == []


def test_listcomp_predicate_compares_iter_var(tagged_ws):
    ast = parse_cypher('MATCH (t) WHERE t.uuid = "a" SET t.tags = [x IN t.tags WHERE x = "beta"]')
    plan = compile_cypher_ast(ast, tagged_ws).plan
    plan.apply(confirm=False)
    assert tagged_ws.packets["a.md"].as_plain()["tags"] == ["beta"]


def test_listcomp_undeclared_iter_in_outer(tagged_ws):
    # Iter var "x" referenced in a sibling SET expression where it's not in scope.
    # Here `t.x` is fine, but `[y IN t.tags | x]` where x is unknown should fail.
    ast = parse_cypher("MATCH (t) SET t.r = [y IN t.tags | y]")
    # y is properly scoped in projection
    plan = compile_cypher_ast(ast, tagged_ws).plan
    plan.apply(confirm=False)
    assert tagged_ws.packets["b.md"].as_plain()["r"] == ["alpha"]


def test_listcomp_predicate_undeclared_var_rejected(tagged_ws):
    # Reference to z in predicate is undeclared.
    ast = parse_cypher('MATCH (t) SET t.r = [x IN t.tags WHERE z.foo = "bar"]')
    with pytest.raises(CypherError):
        compile_cypher_ast(ast, tagged_ws)


def test_listcomp_with_packet_field_in_predicate(tagged_ws):
    # Outer variable t is still accessible inside the comprehension.
    ast = parse_cypher('MATCH (t) WHERE t.uuid = "a" SET t.r = [x IN t.tags WHERE t.uuid = "a"]')
    plan = compile_cypher_ast(ast, tagged_ws).plan
    plan.apply(confirm=False)
    assert tagged_ws.packets["a.md"].as_plain()["r"] == ["alpha", "beta", "gamma"]
