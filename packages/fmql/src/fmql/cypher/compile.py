from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from lark import Lark, Token, Transformer, v_args
from lark.exceptions import LarkError, VisitError

from fmql.cypher.ast import (
    BinaryOp,
    CallExpr,
    CypherAST,
    FieldRef,
    ListComp,
    ListLit,
    LiteralExpr,
    NodePat,
    Pattern,
    RelHop,
    RemoveItem,
    ReturnCount,
    ReturnField,
    ReturnItem,
    ReturnNumber,
    ReturnString,
    ReturnVar,
    SetItem,
    UnaryOp,
    ValueExpr,
)
from fmql.dates import resolve_sentinel
from fmql.errors import CypherError, CypherUnsupported
from fmql.filters import Predicate
from fmql.ordering import OrderKey
from fmql.query import AndNode, ExprNode, NotNode, OrNode, PredNode

_GRAMMAR_PATH = Path(__file__).with_name("grammar.lark")

_OP_MAP = {
    "=": "eq",
    "!=": "ne",
    "<>": "ne",
    ">": "gt",
    ">=": "gte",
    "<": "lt",
    "<=": "lte",
    "CONTAINS": "contains",
    "MATCHES": "matches",
}

_UNSUPPORTED_KEYWORDS: tuple[tuple[str, str], ...] = (
    (r"\bCREATE\b", "CREATE"),
    (r"\bMERGE\b", "MERGE"),
    (r"\bDELETE\b", "DELETE"),
    (r"\bDETACH\b", "DETACH"),
    (r"\bOPTIONAL\s+MATCH\b", "OPTIONAL MATCH"),
    (r"\bWITH\b", "WITH"),
    (r"\bUNWIND\b", "UNWIND"),
    (r"\bshortestPath\b", "shortestPath"),
    (r"\ballShortestPaths\b", "allShortestPaths"),
    (r"\bSKIP\b", "SKIP"),
    (r"\bUNION\b", "UNION"),
    (r"\bCALL\b", "CALL"),
)

_AGG_FN_RE = re.compile(r"\b(sum|avg|min|max|collect)\s*\(", re.IGNORECASE)
_REVERSE_REL_RE = re.compile(r"<\s*-\s*\[")


def _check_unsupported(text: str) -> None:
    for pattern, label in _UNSUPPORTED_KEYWORDS:
        if re.search(pattern, text):
            raise CypherUnsupported(f"{label} is not supported in fmql cypher subset")
    m = _AGG_FN_RE.search(text)
    if m:
        raise CypherUnsupported(
            f"aggregation function {m.group(1)}() is not supported; only count() is"
        )
    if _REVERSE_REL_RE.search(text):
        raise CypherUnsupported("reverse-direction relationships (<-[...]-) are not supported")
    if re.search(r"MATCH\s*\([^)]*\)[^\[]*,\s*\(", text):
        raise CypherUnsupported("multi-pattern MATCH (comma-joined patterns) is not supported")


def _get_parser() -> Lark:
    global _PARSER
    try:
        return _PARSER  # type: ignore[name-defined]
    except NameError:
        pass
    grammar = _GRAMMAR_PATH.read_text(encoding="utf-8")
    _PARSER = Lark(grammar, parser="earley", start="start", maybe_placeholders=False)
    return _PARSER


class _Compiler(Transformer):
    def cypher(self, children):
        match_tree = children[0]
        returns: tuple[ReturnItem, ...] = ()
        where: Optional[ExprNode] = None
        order_by: tuple[OrderKey, ...] = ()
        set_items: list[SetItem] = []
        remove_items: list[RemoveItem] = []
        limit: Optional[int] = None
        for c in children[1:]:
            if isinstance(c, tuple) and c and c[0] == "__where__":
                where = c[1]
            elif isinstance(c, tuple) and c and c[0] == "__return__":
                returns = c[1]
            elif isinstance(c, tuple) and c and c[0] == "__order__":
                order_by = c[1]
            elif isinstance(c, tuple) and c and c[0] == "__limit__":
                limit = c[1]
            elif isinstance(c, tuple) and c and c[0] == "__set__":
                set_items.extend(c[1])
            elif isinstance(c, tuple) and c and c[0] == "__remove__":
                remove_items.extend(c[1])
        return CypherAST(
            pattern=match_tree,
            where=where,
            returns=returns,
            order_by=order_by,
            set_items=tuple(set_items),
            remove_items=tuple(remove_items),
            limit=limit,
        )

    def edit_clause(self, children):
        return children[0]

    def match_clause(self, children):
        for c in children:
            if isinstance(c, Pattern):
                return c
        raise CypherError("MATCH clause missing pattern")

    def pattern(self, children):
        nodes: list[NodePat] = []
        rels: list[RelHop] = []
        for item in children:
            if isinstance(item, NodePat):
                nodes.append(item)
            elif isinstance(item, RelHop):
                rels.append(item)
        if len(nodes) == 0:
            raise CypherError("pattern requires at least one node")
        if len(rels) != len(nodes) - 1:
            raise CypherError("malformed pattern: rel/node count mismatch")
        return Pattern(nodes=tuple(nodes), rels=tuple(rels))

    def node(self, children):
        idents = [str(c) for c in children if _is_ident(c)]
        if not idents:
            raise CypherError("node missing identifier")
        var = idents[0]
        label = idents[1] if len(idents) > 1 else None
        return NodePat(var=var, label=label)

    def rel(self, children):
        idents = [str(c) for c in children if _is_ident(c)]
        if not idents:
            raise CypherError("relationship missing field name")
        field = idents[0]
        min_h = 1
        max_h: Optional[int] = 1
        for c in children:
            if isinstance(c, tuple) and c and c[0] == "__star__":
                min_h, max_h = c[1], c[2]
        return RelHop(field=field, min_hops=min_h, max_hops=max_h)

    def star_spec(self, children):
        if not children:
            return ("__star__", 1, None)
        spec = children[0]
        return spec

    def range_both(self, children):
        lo = int(str(children[0]))
        hi = int(str(children[1]))
        if lo < 0 or hi < lo:
            raise CypherError(f"invalid range *{lo}..{hi}")
        return ("__star__", lo, hi)

    def range_max(self, children):
        hi = int(str(children[0]))
        if hi < 1:
            raise CypherError(f"invalid range *{hi}")
        return ("__star__", 1, hi)

    def range_upper_only(self, children):
        hi = int(str(children[0]))
        return ("__star__", 1, hi)

    def where_clause(self, children):
        expr = next(c for c in children if not _is_kw_token(c))
        return ("__where__", expr)

    def return_clause(self, children):
        items = tuple(
            c
            for c in children
            if isinstance(c, (ReturnVar, ReturnField, ReturnCount, ReturnString, ReturnNumber))
        )
        if not items:
            raise CypherError("RETURN requires at least one item")
        return ("__return__", items)

    def order_clause(self, children):
        keys = tuple(c for c in children if isinstance(c, OrderKey))
        if not keys:
            raise CypherError("ORDER BY requires at least one key")
        return ("__order__", keys)

    def limit_clause(self, children):
        int_tok = next(c for c in children if isinstance(c, Token) and c.type == "INT")
        return ("__limit__", int(str(int_tok)))

    def set_clause(self, children):
        items = tuple(c for c in children if isinstance(c, SetItem))
        if not items:
            raise CypherError("SET requires at least one assignment")
        return ("__set__", items)

    def remove_clause(self, children):
        items: list[RemoveItem] = []
        for c in children:
            if isinstance(c, Token):
                continue
            if isinstance(c, str):
                var, _, fname = c.partition(".")
                if not fname:
                    raise CypherError(f"REMOVE target {c!r} must be qualified as <var>.<field>")
                items.append(RemoveItem(var=var, field=fname))
        if not items:
            raise CypherError("REMOVE requires at least one field")
        return ("__remove__", tuple(items))

    @v_args(inline=True)
    def set_op(self, tok):
        return str(tok)

    def set_item(self, children):
        qident = children[0]
        op_str = children[1] if isinstance(children[1], str) else str(children[1])
        expr = children[2]
        var, _, fname = str(qident).partition(".")
        if not fname:
            raise CypherError(f"SET target {qident!r} must be qualified as <var>.<field>")
        op = "append" if op_str == "+=" else "set"
        return SetItem(var=var, field=fname, expr=_to_value_expr(expr), op=op)

    @v_args(inline=True)
    def ve_ref(self, qident):
        var, _, fname = str(qident).partition(".")
        return FieldRef(var=var, field=fname or None)

    @v_args(inline=True)
    def ve_not(self, _kw, expr):
        return UnaryOp(op="not", operand=_to_value_expr(expr))

    @v_args(inline=True)
    def ve_add(self, left, _plus, right):
        return BinaryOp(op="add", left=_to_value_expr(left), right=_to_value_expr(right))

    def list_lit(self, children):
        items = tuple(_to_value_expr(c) for c in children if not _is_kw_token(c))
        return ListLit(items=items)

    def list_comp(self, children):
        # children: IDENT IN_KW value_expr (WHERE_KW or_expr)? (PIPE value_expr)?
        var: Optional[str] = None
        source: Optional[Any] = None
        predicate: Optional[ExprNode] = None
        projection: Optional[Any] = None
        consumed_in = False
        consumed_where = False
        consumed_pipe = False
        i = 0
        toks = list(children)
        while i < len(toks):
            c = toks[i]
            if isinstance(c, Token):
                ttype = c.type
                if ttype == "IDENT" and var is None and not consumed_in:
                    var = str(c)
                elif ttype == "IN_KW":
                    consumed_in = True
                elif ttype == "WHERE_KW":
                    consumed_where = True
                elif ttype == "PIPE":
                    consumed_pipe = True
            else:
                if consumed_pipe and projection is None:
                    projection = c
                elif consumed_where and not consumed_pipe and predicate is None:
                    predicate = c
                elif consumed_in and source is None:
                    source = c
            i += 1
        if var is None or source is None:
            raise CypherError("malformed list comprehension")
        return ListComp(
            var=var,
            source=_to_value_expr(source),
            predicate=predicate,
            projection=_to_value_expr(projection) if projection is not None else None,
        )

    def func_call(self, children):
        name: Optional[str] = None
        args: list[ValueExpr] = []
        for c in children:
            if isinstance(c, Token) and c.type == "IDENT" and name is None:
                name = str(c)
                continue
            if isinstance(c, Token):
                continue
            args.append(_to_value_expr(c))
        if name is None:
            raise CypherError("function call missing identifier")
        return CallExpr(name=name, args=tuple(args))

    def cypher_order_key(self, children):
        ref: Optional[str] = None
        desc = False
        nulls = "auto"
        for c in children:
            if isinstance(c, tuple) and c and c[0] == "__ref__":
                ref = c[1]
            elif isinstance(c, tuple) and c and c[0] == "__dir__":
                desc = c[1]
            elif isinstance(c, tuple) and c and c[0] == "__nulls__":
                nulls = c[1]
        if ref is None:
            raise CypherError("ORDER BY key missing reference")
        return OrderKey(field=ref, desc=desc, nulls=nulls)

    @v_args(inline=True)
    def order_ref_qual(self, qident):
        return ("__ref__", str(qident))

    def direction_kw(self, children):
        tok = children[0]
        return ("__dir__", str(tok).upper() == "DESC")

    def nulls_spec(self, children):
        last = children[-1]
        return ("__nulls__", "last" if str(last).upper() == "LAST" else "first")

    @v_args(inline=True)
    def r_count(self, _kw, ident):
        return ReturnCount(var=str(ident))

    @v_args(inline=True)
    def r_field(self, var_ident, field_ident):
        return ReturnField(var=str(var_ident), field=str(field_ident))

    @v_args(inline=True)
    def r_var(self, ident):
        return ReturnVar(var=str(ident))

    @v_args(inline=True)
    def r_string(self, tok):
        text = str(tok)
        return ReturnString(value=_unquote(text), text=text)

    @v_args(inline=True)
    def r_number(self, tok):
        text = str(tok)
        return ReturnNumber(value=_parse_number(text), text=text)

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

    def qualified_ident(self, children):
        idents = [str(c) for c in children if _is_ident(c)]
        if len(idents) == 1:
            return idents[0]
        return f"{idents[0]}.{idents[1]}"

    @v_args(inline=True)
    def p_binop(self, qident, op, value):
        op_name = _OP_MAP[op.upper()] if op.isalpha() else _OP_MAP[op]
        return PredNode(Predicate(field=str(qident), op=op_name, value=value))

    def p_in(self, children):
        qident = children[0]
        values = [c for c in children[2:] if not _is_kw_token(c)]
        return PredNode(Predicate(field=str(qident), op="in", value=values))

    def p_not_in(self, children):
        qident = children[0]
        values = [c for c in children[3:] if not _is_kw_token(c)]
        return PredNode(Predicate(field=str(qident), op="not_in", value=values))

    @v_args(inline=True)
    def p_not_empty(self, qident, *_kws):
        return PredNode(Predicate(field=str(qident), op="not_empty", value=True))

    @v_args(inline=True)
    def p_empty(self, qident, *_kws):
        return PredNode(Predicate(field=str(qident), op="not_empty", value=False))

    @v_args(inline=True)
    def p_null(self, qident, *_kws):
        return PredNode(Predicate(field=str(qident), op="is_null", value=True))

    @v_args(inline=True)
    def p_not_null(self, qident, *_kws):
        return NotNode(PredNode(Predicate(field=str(qident), op="is_null", value=True)))

    @v_args(inline=True)
    def v_string(self, tok):
        s = str(tok)
        return _unquote(s)

    @v_args(inline=True)
    def v_number(self, tok):
        return _parse_number(str(tok))

    @v_args(inline=True)
    def v_bool(self, tok):
        return str(tok).lower() == "true"

    @v_args(inline=True)
    def v_null(self, _tok):
        return None

    @v_args(inline=True)
    def v_date_offset(self, tok):
        return resolve_sentinel(str(tok))


def _parse_number(text: str) -> int | float:
    if "." in text or "e" in text or "E" in text:
        return float(text)
    return int(text)


def _to_value_expr(obj: Any) -> ValueExpr:
    if isinstance(obj, (LiteralExpr, FieldRef, CallExpr, UnaryOp, BinaryOp, ListLit, ListComp)):
        return obj
    return LiteralExpr(value=obj)


def _is_ident(obj: Any) -> bool:
    return isinstance(obj, Token) and obj.type == "IDENT"


def _is_kw_token(obj: Any) -> bool:
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


def parse_cypher(text: str) -> CypherAST:
    _check_unsupported(text)
    parser = _get_parser()
    try:
        tree = parser.parse(text)
    except LarkError as e:
        raise CypherError(f"cypher parse error: {e}") from e
    try:
        result = _Compiler().transform(tree)
    except VisitError as e:
        if isinstance(e.orig_exc, (CypherError, CypherUnsupported)):
            raise e.orig_exc
        raise
    if not isinstance(result, CypherAST):
        raise CypherError(f"unexpected top-level compile result: {result!r}")
    return result
