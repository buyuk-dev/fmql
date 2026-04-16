from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from lark import Lark, Transformer, v_args
from lark.exceptions import LarkError, VisitError

from fm.cypher.ast import (
    CypherAST,
    NodePat,
    Pattern,
    RelHop,
    ReturnCount,
    ReturnField,
    ReturnItem,
    ReturnVar,
)
from fm.dates import is_sentinel, resolve_sentinel
from fm.errors import CypherError, CypherUnsupported
from fm.filters import Predicate
from fm.query import AndNode, ExprNode, NotNode, OrNode, PredNode

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

_UNSUPPORTED_KEYWORDS: tuple[tuple[str, str], ...] = (
    (r"\bCREATE\b", "CREATE"),
    (r"\bMERGE\b", "MERGE"),
    (r"\bDELETE\b", "DELETE"),
    (r"\bDETACH\b", "DETACH"),
    (r"\bSET\b", "SET"),
    (r"\bOPTIONAL\s+MATCH\b", "OPTIONAL MATCH"),
    (r"\bWITH\b", "WITH"),
    (r"\bUNWIND\b", "UNWIND"),
    (r"\bshortestPath\b", "shortestPath"),
    (r"\ballShortestPaths\b", "allShortestPaths"),
    (r"\bORDER\s+BY\b", "ORDER BY"),
    (r"\bSKIP\b", "SKIP"),
    (r"\bLIMIT\b", "LIMIT"),
    (r"\bUNION\b", "UNION"),
    (r"\bCALL\b", "CALL"),
)

_AGG_FN_RE = re.compile(r"\b(sum|avg|min|max|collect)\s*\(", re.IGNORECASE)
_REVERSE_REL_RE = re.compile(r"<\s*-\s*\[")


def _check_unsupported(text: str) -> None:
    for pattern, label in _UNSUPPORTED_KEYWORDS:
        if re.search(pattern, text):
            raise CypherUnsupported(f"{label} is not supported in fm cypher subset")
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
    _PARSER = Lark(grammar, parser="lalr", start="start", maybe_placeholders=False)
    return _PARSER


class _Compiler(Transformer):
    def cypher(self, children):
        match_tree = children[0]
        returns: tuple[ReturnItem, ...] = ()
        where: Optional[ExprNode] = None
        for c in children[1:]:
            if isinstance(c, tuple) and c and c[0] == "__where__":
                where = c[1]
            elif isinstance(c, tuple) and c and c[0] == "__return__":
                returns = c[1]
        return CypherAST(pattern=match_tree, where=where, returns=returns)

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
        items = tuple(c for c in children if isinstance(c, (ReturnVar, ReturnField, ReturnCount)))
        if not items:
            raise CypherError("RETURN requires at least one item")
        return ("__return__", items)

    @v_args(inline=True)
    def r_count(self, _kw, ident):
        return ReturnCount(var=str(ident))

    @v_args(inline=True)
    def r_field(self, var_ident, field_ident):
        return ReturnField(var=str(var_ident), field=str(field_ident))

    @v_args(inline=True)
    def r_var(self, ident):
        return ReturnVar(var=str(ident))

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
    def qualified_ident(self, var_tok, field_tok):
        return f"{var_tok}.{field_tok}"

    @v_args(inline=True)
    def p_binop(self, qident, op, value):
        op_name = _OP_MAP[op.upper()] if op.isalpha() else _OP_MAP[op]
        return PredNode(Predicate(field=str(qident), op=op_name, value=value))

    def p_in(self, children):
        qident = children[0]
        values = [c for c in children[2:] if not _is_kw_token(c)]
        return PredNode(Predicate(field=str(qident), op="in", value=values))

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
        return str(tok).lower() == "true"

    @v_args(inline=True)
    def v_date_offset(self, tok):
        return resolve_sentinel(str(tok))

    @v_args(inline=True)
    def v_ident(self, tok):
        name = str(tok)
        if is_sentinel(name):
            return resolve_sentinel(name)
        raise CypherError(
            f"unexpected bare identifier as value: {name!r}. " "String values must be quoted."
        )


def _is_ident(obj: Any) -> bool:
    from lark import Token

    return isinstance(obj, Token) and obj.type == "IDENT"


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
