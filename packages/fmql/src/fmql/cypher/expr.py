from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from fmql.cypher.ast import (
    BinaryOp,
    CallExpr,
    FieldRef,
    ListComp,
    ListLit,
    LiteralExpr,
    UnaryOp,
    ValueExpr,
)
from fmql.errors import CypherError
from fmql.filters import _OPS as _PRED_OPS
from fmql.query import AndNode, ExprNode, NotNode, OrNode, PredNode
from fmql.resolvers import resolver_by_name
from fmql.types import PacketId, Resolver
from fmql.workspace import Workspace


class BinaryOpError(CypherError):
    """Raised when binary `+` operands have incompatible types."""


Binding = dict[str, PacketId]

# Virtual fields synthesized from a packet's id; readable in WHERE/SET/RETURN/ORDER BY.
# Frontmatter takes precedence: a frontmatter `path` shadows the virtual one.
RESERVED_VIRTUAL_FIELDS: tuple[str, ...] = ("path", "filename", "slug")

PSEUDO_FIELDS: tuple[str, ...] = ("_id", "_path")


def virtual_field(pid: PacketId, name: str) -> Any:
    if name == "path":
        return pid
    if name == "filename":
        return Path(pid).name
    if name == "slug":
        return Path(pid).stem
    raise CypherError(f"not a virtual field: {name}")


def pseudo_field(pid: PacketId, name: str) -> Any:
    if name in PSEUDO_FIELDS:
        return pid
    raise CypherError(f"not a pseudo-field: {name}")


def packet_field(workspace: Workspace, pid: PacketId, name: str) -> Any:
    """Read a packet field by name.

    Pseudo-fields (`_id`, `_path`) bypass frontmatter — they are the canonical
    identity. Otherwise frontmatter wins; virtual fields fill the gap.
    """
    if name in PSEUDO_FIELDS:
        return pseudo_field(pid, name)
    packet = workspace.packets.get(pid)
    if packet is None:
        return None
    plain = packet.as_plain()
    if name in plain:
        return plain[name]
    if name in RESERVED_VIRTUAL_FIELDS:
        return virtual_field(pid, name)
    return None


@dataclass
class EvalCtx:
    workspace: Workspace
    binding: Binding
    origin: PacketId
    local: dict[str, Any] = field(default_factory=dict)


CallFn = Callable[[EvalCtx, tuple[Any, ...]], Any]


def _require_string_arg(name: str, args: tuple[Any, ...], idx: int) -> str:
    if idx >= len(args) or not isinstance(args[idx], str):
        raise CypherError(f"{name}() requires a string literal as argument {idx + 1}")
    return args[idx]


def _resolver_for(name: str) -> Resolver:
    try:
        return resolver_by_name(name)
    except Exception as e:
        raise CypherError(f"unknown resolver name in expression: {name!r}") from e


def _resolve(ctx: EvalCtx, args: tuple[Any, ...]) -> Any:
    if len(args) not in (1, 2):
        raise CypherError(f"resolve() takes 1 or 2 arguments, got {len(args)}")
    raw = args[0]
    if len(args) == 2:
        resolver = _resolver_for(_require_string_arg("resolve", args, 1))
    else:
        resolver = ctx.workspace.default_resolver
    return resolver.resolve(raw, origin=ctx.origin, workspace=ctx.workspace)


def _field(ctx: EvalCtx, args: tuple[Any, ...]) -> Any:
    if len(args) != 2:
        raise CypherError(f"field() takes 2 arguments, got {len(args)}")
    pid, fname = args[0], _require_string_arg("field", args, 1)
    if pid is None:
        return None
    if not isinstance(pid, str):
        raise CypherError(f"field() expected a packet id (str), got {type(pid).__name__}")
    return packet_field(ctx.workspace, pid, fname)


REGISTRY: dict[str, CallFn] = {
    "resolve": _resolve,
    "field": _field,
}

# Names that used to be shortcuts in fmql's Cypher subset but collided with — or
# resembled — Cypher's own built-ins (`id()`, `path` as a sequence type). Removed
# in task 0022; the dispatch error points at the explicit composition.
_REMOVED_SHORTCUTS: dict[str, str] = {
    "id": 'field(resolve(v, "id"), "id")',
    "uuid": 'field(resolve(v, "uuid"), "uuid")',
    "slug": 'field(resolve(v, "slug"), "slug")',
    "path": 'resolve(v, "path")',
}


def is_known_function(name: str) -> bool:
    return name in REGISTRY


def unknown_function_error(name: str) -> CypherError:
    """Build the right error for a function name fmql does not know.

    Names listed in `_REMOVED_SHORTCUTS` get a hint pointing at the explicit
    composition the user should write instead; everything else gets the plain
    "unknown function" message.
    """
    hint = _REMOVED_SHORTCUTS.get(name)
    if hint is not None:
        return CypherError(f"function {name}() was removed; use {hint} instead")
    return CypherError(f"unknown function in SET expression: {name}()")


def eval_value_expr(expr: ValueExpr, ctx: EvalCtx) -> Any:
    if isinstance(expr, LiteralExpr):
        return expr.value
    if isinstance(expr, FieldRef):
        if expr.var in ctx.local:
            base = ctx.local[expr.var]
            if expr.field is None:
                return base
            if isinstance(base, dict):
                return base.get(expr.field)
            return None
        if expr.field is None:
            raise CypherError(f"bare identifier {expr.var!r} not bound in scope")
        pid = ctx.binding.get(expr.var)
        if pid is None:
            return None
        return packet_field(ctx.workspace, pid, expr.field)
    if isinstance(expr, CallExpr):
        fn = REGISTRY.get(expr.name)
        if fn is None:
            raise unknown_function_error(expr.name)
        return _eval_call(fn, expr.args, ctx)
    if isinstance(expr, UnaryOp):
        if expr.op == "not":
            value = eval_value_expr(expr.operand, ctx)
            if isinstance(value, list):
                return [_negate(v) for v in value]
            return _negate(value)
        raise CypherError(f"unknown unary operator: {expr.op!r}")
    if isinstance(expr, BinaryOp):
        if expr.op == "add":
            left = eval_value_expr(expr.left, ctx)
            right = eval_value_expr(expr.right, ctx)
            return _eval_add(left, right)
        raise CypherError(f"unknown binary operator: {expr.op!r}")
    if isinstance(expr, ListLit):
        return [eval_value_expr(item, ctx) for item in expr.items]
    if isinstance(expr, ListComp):
        source = eval_value_expr(expr.source, ctx)
        if source is None:
            return []
        if not isinstance(source, list):
            raise CypherError(
                f"list comprehension source must be a list, got {type(source).__name__}"
            )
        out: list[Any] = []
        for item in source:
            inner_local = dict(ctx.local)
            inner_local[expr.var] = item
            inner_ctx = EvalCtx(
                workspace=ctx.workspace,
                binding=ctx.binding,
                origin=ctx.origin,
                local=inner_local,
            )
            if expr.predicate is not None and not eval_predicate(expr.predicate, inner_ctx):
                continue
            if expr.projection is not None:
                out.append(eval_value_expr(expr.projection, inner_ctx))
            else:
                out.append(item)
        return out
    raise CypherError(f"unknown value expression: {type(expr).__name__}")


def _negate(v: Any) -> Any:
    if not isinstance(v, bool):
        raise CypherError(f"NOT operand must be bool, got {type(v).__name__}")
    return not v


def _is_list(v: Any) -> bool:
    return isinstance(v, (list, tuple))


def _is_number(v: Any) -> bool:
    # bool is a subclass of int in Python; exclude it so `True + 1` errors
    # rather than silently producing `2`.
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _eval_add(left: Any, right: Any) -> Any:
    if left is None or right is None:
        return None
    if _is_list(left) and _is_list(right):
        return [*left, *right]
    if _is_list(left):
        return [*left, right]
    if _is_list(right):
        return [left, *right]
    if isinstance(left, str) and isinstance(right, str):
        return left + right
    if _is_number(left) and _is_number(right):
        return left + right
    raise BinaryOpError(f"cannot add {type(left).__name__} and {type(right).__name__}")


def eval_predicate(expr: ExprNode, ctx: EvalCtx) -> bool:
    """Evaluate a predicate against a binding, with optional list-comp local scope."""
    if isinstance(expr, PredNode):
        field_name = expr.predicate.field
        if "." in field_name:
            var, _, sub = field_name.partition(".")
        else:
            var, sub = field_name, None
        if var in ctx.local:
            base = ctx.local[var]
            if sub is None:
                value = base
            elif isinstance(base, dict):
                value = base.get(sub)
            else:
                value = None
        else:
            if sub is None:
                raise CypherError(f"predicate {field_name!r} must be qualified as <var>.<field>")
            pid = ctx.binding.get(var)
            if pid is None:
                return False
            value = packet_field(ctx.workspace, pid, sub)
        return _PRED_OPS[expr.predicate.op](value, expr.predicate.value)
    if isinstance(expr, AndNode):
        return all(eval_predicate(e, ctx) for e in expr.items)
    if isinstance(expr, OrNode):
        return any(eval_predicate(e, ctx) for e in expr.items)
    if isinstance(expr, NotNode):
        return not eval_predicate(expr.item, ctx)
    raise CypherError(f"unknown expression node: {type(expr).__name__}")


def _eval_call(fn: CallFn, arg_exprs: tuple[ValueExpr, ...], ctx: EvalCtx) -> Any:
    args = tuple(eval_value_expr(a, ctx) for a in arg_exprs)
    if not args:
        return fn(ctx, args)
    first = args[0]
    if isinstance(first, (list, tuple)):
        rest = args[1:]
        return [fn(ctx, (item,) + rest) for item in first]
    return fn(ctx, args)


def make_eval_ctx(
    workspace: Workspace,
    binding: Binding,
    origin: Optional[PacketId] = None,
) -> EvalCtx:
    """Construct an EvalCtx with sensible defaults. Origin defaults to first bound pid."""
    pid = origin
    if pid is None:
        for v in binding.values():
            pid = v
            break
    if pid is None:
        raise CypherError("cannot evaluate expression without a binding")
    return EvalCtx(workspace=workspace, binding=binding, origin=pid)
