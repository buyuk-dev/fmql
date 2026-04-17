from __future__ import annotations

import math
from typing import Any

from fm.cypher.ast import (
    CypherAST,
    CypherResult,
    Pattern,
    RelHop,
    ReturnCount,
    ReturnField,
    ReturnItem,
    ReturnVar,
)
from fm.cypher.compile import parse_cypher
from fm.errors import CypherError
from fm.filters import Predicate, match
from fm.query import AndNode, ExprNode, NotNode, OrNode, PredNode
from fm.types import PacketId, Resolver
from fm.workspace import Workspace

Binding = dict[str, PacketId]


def compile_cypher(text: str, workspace: Workspace) -> CypherResult:
    ast = parse_cypher(text)
    return compile_cypher_ast(ast, workspace)


def compile_cypher_ast(ast: CypherAST, workspace: Workspace) -> CypherResult:
    _validate(ast)
    bindings = _enumerate(workspace, ast.pattern)
    if ast.where is not None:
        bindings = [b for b in bindings if _eval_scoped(ast.where, b, workspace)]
    return _project(ast.returns, bindings, workspace)


def _validate(ast: CypherAST) -> None:
    vars_declared = {n.var for n in ast.pattern.nodes}
    for item in ast.returns:
        if item.var not in vars_declared:
            raise CypherError(f"RETURN references undeclared variable {item.var!r}")
    if ast.where is not None:
        _check_where_vars(ast.where, vars_declared)


def _check_where_vars(expr: ExprNode, declared: set[str]) -> None:
    if isinstance(expr, PredNode):
        field = expr.predicate.field
        if "." not in field:
            raise CypherError(f"WHERE predicate {field!r} must be qualified as <var>.<field>")
        var = field.split(".", 1)[0]
        if var not in declared:
            raise CypherError(f"WHERE references undeclared variable {var!r}")
    elif isinstance(expr, (AndNode, OrNode)):
        for item in expr.items:
            _check_where_vars(item, declared)
    elif isinstance(expr, NotNode):
        _check_where_vars(expr.item, declared)


def _enumerate(workspace: Workspace, pattern: Pattern) -> list[Binding]:
    first = pattern.nodes[0].var
    bindings: list[Binding] = [{first: pid} for pid in sorted(workspace.packets)]
    for i, rel in enumerate(pattern.rels):
        src_var = pattern.nodes[i].var
        tgt_var = pattern.nodes[i + 1].var
        next_bindings: list[Binding] = []
        for b in bindings:
            src = b[src_var]
            reachable = _reachable(workspace, src, rel)
            if tgt_var in b:
                if b[tgt_var] in reachable:
                    next_bindings.append(b)
            else:
                for tgt in sorted(reachable):
                    new_b = dict(b)
                    new_b[tgt_var] = tgt
                    next_bindings.append(new_b)
        bindings = next_bindings
    return bindings


def _reachable(workspace: Workspace, src: PacketId, rel: RelHop) -> set[PacketId]:
    resolver: Resolver = workspace.resolvers.get(rel.field) or workspace.default_resolver
    if rel.min_hops == 1 and rel.max_hops == 1:
        return set(_neighbors(workspace, src, rel.field, resolver))

    max_depth: float
    if rel.max_hops is None:
        max_depth = math.inf
    else:
        max_depth = rel.max_hops
    visited: set[PacketId] = {src}
    frontier: set[PacketId] = {src}
    per_depth: list[set[PacketId]] = []
    hop = 0
    while frontier and hop < max_depth:
        next_frontier: set[PacketId] = set()
        for node in frontier:
            for nb in _neighbors(workspace, node, rel.field, resolver):
                if nb in visited and nb != src:
                    continue
                next_frontier.add(nb)
                if nb != src:
                    visited.add(nb)
        frontier = next_frontier
        hop += 1
        if hop >= rel.min_hops:
            per_depth.append(set(frontier))
    result: set[PacketId] = set()
    for s in per_depth:
        result |= s
    return result


def _neighbors(
    workspace: Workspace, pid: PacketId, field: str, resolver: Resolver
) -> list[PacketId]:
    packet = workspace.packets.get(pid)
    if packet is None:
        return []
    raw = packet.as_plain().get(field)
    if raw is None:
        return []
    items = raw if isinstance(raw, (list, tuple)) else [raw]
    out: list[PacketId] = []
    for item in items:
        tgt = resolver.resolve(item, origin=pid, workspace=workspace)
        if tgt is not None:
            out.append(tgt)
    return out


def _eval_scoped(expr: ExprNode, binding: Binding, workspace: Workspace) -> bool:
    if isinstance(expr, PredNode):
        qfield = expr.predicate.field
        var, _, field = qfield.partition(".")
        pid = binding.get(var)
        if pid is None:
            return False
        packet = workspace.packets.get(pid)
        if packet is None:
            return False
        local = Predicate(field=field, op=expr.predicate.op, value=expr.predicate.value)
        return match(packet, local)
    if isinstance(expr, AndNode):
        return all(_eval_scoped(e, binding, workspace) for e in expr.items)
    if isinstance(expr, OrNode):
        return any(_eval_scoped(e, binding, workspace) for e in expr.items)
    if isinstance(expr, NotNode):
        return not _eval_scoped(expr.item, binding, workspace)
    raise CypherError(f"unknown expression node: {type(expr).__name__}")


def _project(
    returns: tuple[ReturnItem, ...],
    bindings: list[Binding],
    workspace: Workspace,
) -> CypherResult:
    if len(returns) == 1 and isinstance(returns[0], ReturnCount):
        return CypherResult(
            columns=(f"count({returns[0].var})",),
            rows=((len(bindings),),),
            is_scalar=True,
            scalar=len(bindings),
        )
    if any(isinstance(r, ReturnCount) for r in returns):
        raise CypherError("count() must be the sole RETURN item")
    columns = tuple(_column_name(r) for r in returns)
    rows: list[tuple[Any, ...]] = []
    for b in bindings:
        row = tuple(_project_item(r, b, workspace) for r in returns)
        rows.append(row)
    rows = _dedupe_sort(rows)
    return CypherResult(columns=columns, rows=tuple(rows), is_scalar=False, scalar=None)


def _column_name(r: ReturnItem) -> str:
    if isinstance(r, ReturnVar):
        return r.var
    if isinstance(r, ReturnField):
        return f"{r.var}.{r.field}"
    if isinstance(r, ReturnCount):
        return f"count({r.var})"
    raise CypherError(f"unknown return item: {type(r).__name__}")


def _project_item(item: ReturnItem, binding: Binding, workspace: Workspace) -> Any:
    pid = binding[item.var]
    if isinstance(item, ReturnVar):
        return pid
    if isinstance(item, ReturnField):
        packet = workspace.packets.get(pid)
        if packet is None:
            return None
        return packet.as_plain().get(item.field)
    raise CypherError(f"unprojectable item: {type(item).__name__}")


def _dedupe_sort(rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    seen: set[tuple[Any, ...]] = set()
    uniq: list[tuple[Any, ...]] = []
    for row in rows:
        try:
            key = tuple(_hashable(v) for v in row)
        except TypeError:
            key = None  # type: ignore[assignment]
        if key is not None and key in seen:
            continue
        if key is not None:
            seen.add(key)
        uniq.append(row)
    try:
        uniq.sort(key=lambda r: tuple(_sort_key(v) for v in r))
    except TypeError:
        pass
    return uniq


def _hashable(v: Any) -> Any:
    if isinstance(v, (list, tuple)):
        return tuple(_hashable(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted((k, _hashable(x)) for k, x in v.items()))
    return v


def _sort_key(v: Any) -> tuple[int, Any]:
    if v is None:
        return (0, "")
    if isinstance(v, bool):
        return (1, int(v))
    if isinstance(v, (int, float)):
        return (2, v)
    if isinstance(v, str):
        return (3, v)
    return (9, repr(v))
