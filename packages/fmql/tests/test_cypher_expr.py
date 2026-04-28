from __future__ import annotations

import pytest

from fmql.cypher.ast import CallExpr, FieldRef, LiteralExpr
from fmql.cypher.expr import EvalCtx, eval_value_expr
from fmql.errors import CypherError


@pytest.fixture
def id_ws(make_workspace):
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


def _ctx(ws, var="t", origin="tasks/c.md") -> EvalCtx:
    return EvalCtx(workspace=ws, binding={var: origin}, origin=origin)


def test_literal(id_ws):
    assert eval_value_expr(LiteralExpr(value=42), _ctx(id_ws)) == 42


def test_field_ref(id_ws):
    expr = FieldRef(var="t", field="slug")
    assert eval_value_expr(expr, _ctx(id_ws, origin="tasks/a.md")) == "alpha"


def test_resolve_default(id_ws):
    # Default is RelativePathResolver; "../tasks/a.md" from c.md resolves to a.md.
    expr = CallExpr(name="resolve", args=(LiteralExpr(value="a.md"),))
    pid = eval_value_expr(expr, _ctx(id_ws, origin="tasks/c.md"))
    assert pid == "tasks/a.md"


def test_resolve_named_id(id_ws):
    expr = CallExpr(name="resolve", args=(LiteralExpr(value=8), LiteralExpr(value="id")))
    assert eval_value_expr(expr, _ctx(id_ws)) == "tasks/b.md"


def test_field_function(id_ws):
    expr = CallExpr(
        name="field",
        args=(LiteralExpr(value="tasks/a.md"), LiteralExpr(value="slug")),
    )
    assert eval_value_expr(expr, _ctx(id_ws)) == "alpha"


def test_field_none_pid(id_ws):
    expr = CallExpr(name="field", args=(LiteralExpr(value=None), LiteralExpr(value="slug")))
    assert eval_value_expr(expr, _ctx(id_ws)) is None


def test_slug_shortcut_via_id_lookup(id_ws):
    # When called with an id, slug() resolves via SlugResolver — but SlugResolver
    # falls back to file stem too. With value=8 (int), no match.
    expr = CallExpr(name="slug", args=(LiteralExpr(value=8),))
    assert eval_value_expr(expr, _ctx(id_ws)) is None


def test_slug_shortcut_via_slug_string(id_ws):
    expr = CallExpr(name="slug", args=(LiteralExpr(value="alpha"),))
    assert eval_value_expr(expr, _ctx(id_ws)) == "alpha"


def test_id_to_slug_via_compose(id_ws):
    # field(resolve(v, "id"), "slug")
    expr = CallExpr(
        name="field",
        args=(
            CallExpr(name="resolve", args=(LiteralExpr(value=8), LiteralExpr(value="id"))),
            LiteralExpr(value="slug"),
        ),
    )
    assert eval_value_expr(expr, _ctx(id_ws)) == "bravo"


def test_broadcast_over_list(id_ws):
    # field(resolve([1, 8, 17], "id"), "slug") → ["alpha", "bravo", "charlie"]
    expr = CallExpr(
        name="field",
        args=(
            CallExpr(
                name="resolve",
                args=(LiteralExpr(value=[1, 8, 17]), LiteralExpr(value="id")),
            ),
            LiteralExpr(value="slug"),
        ),
    )
    result = eval_value_expr(expr, _ctx(id_ws))
    assert result == ["alpha", "bravo", "charlie"]


def test_broadcast_preserves_none_for_unresolved(id_ws):
    expr = CallExpr(
        name="resolve",
        args=(LiteralExpr(value=[1, 999, 8]), LiteralExpr(value="id")),
    )
    result = eval_value_expr(expr, _ctx(id_ws))
    assert result == ["tasks/a.md", None, "tasks/b.md"]


def test_unknown_function_raises(id_ws):
    expr = CallExpr(name="not_a_function", args=())
    with pytest.raises(CypherError):
        eval_value_expr(expr, _ctx(id_ws))


def test_resolve_arity_error(id_ws):
    expr = CallExpr(name="resolve", args=())
    with pytest.raises(CypherError):
        eval_value_expr(expr, _ctx(id_ws))


def test_resolve_unknown_resolver_name(id_ws):
    expr = CallExpr(
        name="resolve",
        args=(LiteralExpr(value=1), LiteralExpr(value="nope")),
    )
    with pytest.raises(CypherError):
        eval_value_expr(expr, _ctx(id_ws))
