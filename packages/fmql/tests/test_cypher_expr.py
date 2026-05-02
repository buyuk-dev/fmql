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


@pytest.mark.parametrize(
    "name,hint_fragment",
    [
        ("id", 'field(resolve(v, "id"), "id")'),
        ("uuid", 'field(resolve(v, "uuid"), "uuid")'),
        ("slug", 'field(resolve(v, "slug"), "slug")'),
        ("path", 'resolve(v, "path")'),
    ],
)
def test_removed_shortcut_raises_with_hint(id_ws, name, hint_fragment):
    expr = CallExpr(name=name, args=(LiteralExpr(value=1),))
    with pytest.raises(CypherError) as exc:
        eval_value_expr(expr, _ctx(id_ws))
    msg = str(exc.value)
    assert "was removed" in msg
    assert hint_fragment in msg


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


def test_unary_not_bool():
    from fmql.cypher.ast import LiteralExpr, UnaryOp
    from fmql.cypher.expr import EvalCtx, eval_value_expr

    expr = UnaryOp(op="not", operand=LiteralExpr(value=True))
    assert eval_value_expr(expr, EvalCtx(workspace=None, binding={}, origin="x")) is False


def test_unary_not_non_bool_errors():
    from fmql.cypher.ast import LiteralExpr, UnaryOp
    from fmql.cypher.expr import EvalCtx, eval_value_expr
    from fmql.errors import CypherError

    expr = UnaryOp(op="not", operand=LiteralExpr(value="hello"))
    with pytest.raises(CypherError, match="NOT operand"):
        eval_value_expr(expr, EvalCtx(workspace=None, binding={}, origin="x"))


def test_unary_not_broadcasts_over_list():
    from fmql.cypher.ast import LiteralExpr, UnaryOp
    from fmql.cypher.expr import EvalCtx, eval_value_expr

    expr = UnaryOp(op="not", operand=LiteralExpr(value=[True, False, True]))
    out = eval_value_expr(expr, EvalCtx(workspace=None, binding={}, origin="x"))
    assert out == [False, True, False]


def test_list_lit_evaluates_each_item():
    from fmql.cypher.ast import ListLit, LiteralExpr
    from fmql.cypher.expr import EvalCtx, eval_value_expr

    expr = ListLit(items=(LiteralExpr(value=1), LiteralExpr(value="x")))
    assert eval_value_expr(expr, EvalCtx(workspace=None, binding={}, origin="x")) == [1, "x"]


def test_virtual_path_field(id_ws):
    expr = FieldRef(var="t", field="path")
    assert eval_value_expr(expr, _ctx(id_ws, origin="tasks/a.md")) == "tasks/a.md"


def test_virtual_filename_field(id_ws):
    expr = FieldRef(var="t", field="filename")
    assert eval_value_expr(expr, _ctx(id_ws, origin="tasks/a.md")) == "a.md"


def test_virtual_slug_falls_back_to_stem(id_ws):
    # tasks/a.md has frontmatter slug=alpha; frontmatter wins.
    expr = FieldRef(var="t", field="slug")
    assert eval_value_expr(expr, _ctx(id_ws, origin="tasks/a.md")) == "alpha"


def test_virtual_slug_uses_stem_when_no_frontmatter_slug(make_workspace):
    spec = {"docs/x.md": {"frontmatter": {"uuid": "x"}, "body": "x\n"}}
    ws = make_workspace(spec)
    expr = FieldRef(var="t", field="slug")
    ctx = EvalCtx(workspace=ws, binding={"t": "docs/x.md"}, origin="docs/x.md")
    assert eval_value_expr(expr, ctx) == "x"
