from __future__ import annotations

from pathlib import Path
from typing import Any

from lark import Lark, Transformer, v_args
from lark.exceptions import LarkError, VisitError

from fmq.dates import is_sentinel, resolve_sentinel
from fmq.errors import QueryError
from fmq.filters import Predicate
from fmq.query import AndNode, ExprNode, NotNode, OrNode, PredNode, Query
from fmq.workspace import Workspace

_GRAMMAR_PATH = Path(__file__).with_name("grammar.lark")

_OP_MAP = {
    "=": "eq",
    "!=": "ne",
    ">": "gt",
    ">=": "gte",
    "<": "lt",
    "<=": "lte",
    "CONTAINS": "contains",
    "MATCHES": "matches",
}


def _get_parser() -> Lark:
    global _PARSER
    try:
        return _PARSER  # type: ignore[name-defined]
    except NameError:
        pass
    grammar = _GRAMMAR_PATH.read_text(encoding="utf-8")
    _PARSER = Lark(grammar, parser="lalr", start="start", maybe_placeholders=False)
    return _PARSER


class _STAR:  # sentinel
    pass


STAR = _STAR()


class _Compiler(Transformer):
    @v_args(inline=True)
    def q_star(self, _tok):
        return STAR

    @v_args(inline=True)
    def q_expr(self, expr):
        return expr

    def or_list(self, items):
        items = [i for i in items if not _is_kw_token(i)]
        if len(items) == 1:
            return items[0]
        return OrNode(tuple(items))

    def and_list(self, items):
        items = [i for i in items if not _is_kw_token(i)]
        if len(items) == 1:
            return items[0]
        return AndNode(tuple(items))

    @v_args(inline=True)
    def not_op(self, _kw, inner):
        return NotNode(inner)

    @v_args(inline=True)
    def cmp_op(self, tok):
        return str(tok)

    @v_args(inline=True)
    def p_binop(self, ident, op, value):
        op_name = _OP_MAP[op]
        return PredNode(Predicate(field=str(ident), op=op_name, value=value))

    def p_in(self, children):
        ident = children[0]
        values = [c for c in children[2:] if not _is_kw_token(c)]
        return PredNode(Predicate(field=str(ident), op="in", value=values))

    @v_args(inline=True)
    def p_not_empty(self, ident, *_kws):
        return PredNode(Predicate(field=str(ident), op="not_empty", value=True))

    @v_args(inline=True)
    def p_empty(self, ident, *_kws):
        return PredNode(Predicate(field=str(ident), op="not_empty", value=False))

    @v_args(inline=True)
    def p_null(self, ident, *_kws):
        return PredNode(Predicate(field=str(ident), op="is_null", value=True))

    @v_args(inline=True)
    def v_string(self, tok):
        s = str(tok)
        return _unquote(s)

    @v_args(inline=True)
    def v_number(self, tok):
        s = str(tok)
        if "." in s or "e" in s or "E" in s:
            return float(s)
        return int(s)

    @v_args(inline=True)
    def v_bool(self, tok):
        return str(tok) == "true"

    @v_args(inline=True)
    def v_date_offset(self, tok):
        return resolve_sentinel(str(tok))

    @v_args(inline=True)
    def v_ident(self, tok):
        name = str(tok)
        if is_sentinel(name):
            return resolve_sentinel(name)
        raise QueryError(
            f"unexpected bare identifier as value: {name!r}. "
            "String values must be quoted."
        )


def _is_kw_token(obj: Any) -> bool:
    from lark import Token

    return isinstance(obj, Token)


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        inner = s[1:-1]
        return (
            inner.replace("\\\\", "\\")
            .replace('\\"', '"')
            .replace("\\'", "'")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\r", "\r")
        )
    return s


def compile_query(text: str, workspace: Workspace) -> Query:
    parser = _get_parser()
    try:
        tree = parser.parse(text)
    except LarkError as e:
        raise QueryError(f"query parse error: {e}") from e
    try:
        result = _Compiler().transform(tree)
    except VisitError as e:
        if isinstance(e.orig_exc, QueryError):
            raise e.orig_exc
        raise
    if isinstance(result, _STAR):
        return Query(workspace)
    if not isinstance(result, (PredNode, AndNode, OrNode, NotNode)):
        raise QueryError(f"unexpected top-level result: {result!r}")
    return Query(workspace).where_expr(result)
