from __future__ import annotations

import pytest

from fmql.cypher.compile import parse_cypher
from fmql.cypher.executor import compile_cypher_ast
from fmql.errors import CypherError


@pytest.fixture
def flagged_ws(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"uuid": "a", "stale": True, "label": "A"}, "body": "a\n"},
        "b.md": {"frontmatter": {"uuid": "b", "stale": False, "label": "B"}, "body": "b\n"},
        "c.md": {"frontmatter": {"uuid": "c", "label": "C"}, "body": "c\n"},
    }
    return make_workspace(spec)


def test_remove_single_field_drops_key(flagged_ws):
    ast = parse_cypher("MATCH (t) WHERE t.stale = true REMOVE t.stale")
    plan = compile_cypher_ast(ast, flagged_ws).plan
    plan.apply(confirm=False)
    assert "stale" not in flagged_ws.packets["a.md"].as_plain()
    assert "stale" in flagged_ws.packets["b.md"].as_plain()


def test_remove_multiple_fields(flagged_ws):
    ast = parse_cypher('MATCH (t) WHERE t.uuid = "a" REMOVE t.stale, t.label')
    plan = compile_cypher_ast(ast, flagged_ws).plan
    plan.apply(confirm=False)
    a = flagged_ws.packets["a.md"].as_plain()
    assert "stale" not in a
    assert "label" not in a
    assert a["uuid"] == "a"


def test_remove_absent_field_is_noop(flagged_ws):
    ast = parse_cypher("MATCH (t) REMOVE t.nonexistent")
    plan = compile_cypher_ast(ast, flagged_ws).plan
    rep = plan.apply(confirm=False)
    assert rep.errors == []


def test_remove_with_set_on_disjoint_fields(flagged_ws):
    ast = parse_cypher('MATCH (t) WHERE t.uuid = "a" SET t.label = "A2" REMOVE t.stale')
    plan = compile_cypher_ast(ast, flagged_ws).plan
    plan.apply(confirm=False)
    a = flagged_ws.packets["a.md"].as_plain()
    assert a["label"] == "A2"
    assert "stale" not in a


def test_remove_and_set_same_field_conflict(flagged_ws):
    ast = parse_cypher('MATCH (t) SET t.label = "X" REMOVE t.label')
    with pytest.raises(CypherError, match="REMOVE"):
        compile_cypher_ast(ast, flagged_ws)


def test_remove_undeclared_var_rejected(flagged_ws):
    ast = parse_cypher("MATCH (t) REMOVE u.x")
    with pytest.raises(CypherError, match="undeclared"):
        compile_cypher_ast(ast, flagged_ws)


def test_remove_only_no_return_no_set_is_valid(flagged_ws):
    ast = parse_cypher("MATCH (t) REMOVE t.stale")
    exec = compile_cypher_ast(ast, flagged_ws)
    assert exec.plan is not None
    assert exec.result is None


# ---------- backtick-quoted field names ----------


@pytest.fixture
def hyphen_remove_ws(make_workspace):
    spec = {
        "a.md": {
            "frontmatter": {"uuid": "a", "org-type": "school", "status": "active"},
            "body": "a\n",
        },
        "b.md": {
            "frontmatter": {"uuid": "b", "org-type": "company", "status": "active"},
            "body": "b\n",
        },
    }
    return make_workspace(spec)


def test_remove_backtick_drops_hyphenated_key(hyphen_remove_ws):
    ast = parse_cypher("MATCH (t) REMOVE t.`org-type`")
    plan = compile_cypher_ast(ast, hyphen_remove_ws).plan
    plan.apply(confirm=False)
    for pid in ("a.md", "b.md"):
        body = hyphen_remove_ws.packets[pid].as_plain()
        assert "org-type" not in body
        assert body["status"] == "active"  # untouched


def test_remove_backtick_pseudo_field_still_rejected(hyphen_remove_ws):
    """Backtick-escaping `_path` does not bypass the pseudo-field reject on REMOVE."""
    ast = parse_cypher("MATCH (t) REMOVE t.`_path`")
    with pytest.raises(CypherError):
        compile_cypher_ast(ast, hyphen_remove_ws)
