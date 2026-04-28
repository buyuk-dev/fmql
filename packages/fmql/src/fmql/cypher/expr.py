from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fmql.cypher.ast import CallExpr, FieldRef, LiteralExpr, ValueExpr
from fmql.errors import CypherError
from fmql.resolvers import resolver_by_name
from fmql.types import PacketId, Resolver
from fmql.workspace import Workspace

Binding = dict[str, PacketId]


@dataclass
class EvalCtx:
    workspace: Workspace
    binding: Binding
    origin: PacketId


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
    packet = ctx.workspace.packets.get(pid)
    if packet is None:
        return None
    return packet.as_plain().get(fname)


def _make_shortcut(resolver_name: str) -> CallFn:
    def fn(ctx: EvalCtx, args: tuple[Any, ...]) -> Any:
        if len(args) != 1:
            raise CypherError(f"{resolver_name}() takes 1 argument, got {len(args)}")
        resolver = _resolver_for(resolver_name)
        pid = resolver.resolve(args[0], origin=ctx.origin, workspace=ctx.workspace)
        if pid is None:
            return None
        packet = ctx.workspace.packets.get(pid)
        if packet is None:
            return None
        return packet.as_plain().get(resolver_name)

    return fn


def _path(ctx: EvalCtx, args: tuple[Any, ...]) -> Any:
    if len(args) != 1:
        raise CypherError(f"path() takes 1 argument, got {len(args)}")
    resolver = _resolver_for("path")
    return resolver.resolve(args[0], origin=ctx.origin, workspace=ctx.workspace)


REGISTRY: dict[str, CallFn] = {
    "resolve": _resolve,
    "field": _field,
    "slug": _make_shortcut("slug"),
    "id": _make_shortcut("id"),
    "uuid": _make_shortcut("uuid"),
    "path": _path,
}


def is_known_function(name: str) -> bool:
    return name in REGISTRY


def eval_value_expr(expr: ValueExpr, ctx: EvalCtx) -> Any:
    if isinstance(expr, LiteralExpr):
        return expr.value
    if isinstance(expr, FieldRef):
        pid = ctx.binding.get(expr.var)
        if pid is None:
            return None
        packet = ctx.workspace.packets.get(pid)
        if packet is None:
            return None
        return packet.as_plain().get(expr.field)
    if isinstance(expr, CallExpr):
        fn = REGISTRY.get(expr.name)
        if fn is None:
            raise CypherError(f"unknown function in SET expression: {expr.name}()")
        return _eval_call(fn, expr.name, expr.args, ctx)
    raise CypherError(f"unknown value expression: {type(expr).__name__}")


def _eval_call(fn: CallFn, name: str, arg_exprs: tuple[ValueExpr, ...], ctx: EvalCtx) -> Any:
    args = tuple(eval_value_expr(a, ctx) for a in arg_exprs)
    if not args:
        return fn(ctx, args)
    first = args[0]
    if isinstance(first, (list, tuple)):
        rest = args[1:]
        return [fn(ctx, (item,) + rest) for item in first]
    return fn(ctx, args)
