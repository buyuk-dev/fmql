from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Optional

from fmql.cypher.ast import (
    BinaryOp,
    CallExpr,
    CypherAST,
    CypherResult,
    FieldRef,
    ListComp,
    ListLit,
    LiteralExpr,
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
from fmql.cypher.compile import parse_cypher
from fmql.cypher.expr import (
    PSEUDO_FIELDS,
    BinaryOpError,
    EvalCtx,
    eval_predicate,
    eval_value_expr,
    is_known_function,
    packet_field,
    unknown_function_error,
)
from fmql.edges import iter_forward_targets
from fmql.edits import EditOp, EditPlan
from fmql.errors import CypherError
from fmql.ordering import OrderKey, apply_order
from fmql.query import AndNode, ExprNode, NotNode, OrNode, PredNode
from fmql.types import PacketId, Resolver
from fmql.workspace import Workspace

Binding = dict[str, PacketId]


@dataclass
class CypherExecution:
    plan: Optional[EditPlan] = None
    result: Optional[CypherResult] = None


def compile_cypher(text: str, workspace: Workspace) -> CypherResult:
    ast = parse_cypher(text)
    execution = compile_cypher_ast(ast, workspace)
    if execution.result is None:
        raise CypherError("query has no RETURN clause; expected CypherResult")
    return execution.result


def compile_cypher_ast(ast: CypherAST, workspace: Workspace) -> CypherExecution:
    _validate(ast)
    bindings = _enumerate(workspace, ast.pattern)
    if ast.where is not None:
        bindings = [
            b
            for b in bindings
            if eval_predicate(
                ast.where, EvalCtx(workspace=workspace, binding=b, origin=_first_pid(b))
            )
        ]

    plan: Optional[EditPlan] = None
    if ast.set_items or ast.remove_items:
        plan = _build_edit_plan(ast.set_items, ast.remove_items, bindings, workspace)

    if ast.order_by:
        bindings = _sort_bindings(bindings, ast.order_by, workspace)

    result: Optional[CypherResult] = None
    if ast.returns:
        if ast.limit == 0:
            result = _empty_result(ast.returns)
        else:
            result = _project(ast.returns, bindings, workspace, sort_rows=not ast.order_by)
            if ast.limit is not None:
                result = _apply_limit(result, ast.limit)

    return CypherExecution(plan=plan, result=result)


def _apply_limit(result: CypherResult, limit: int) -> CypherResult:
    if limit >= len(result.rows):
        return result
    new_rows = result.rows[:limit]
    if result.is_scalar and not new_rows:
        return replace(result, rows=new_rows, is_scalar=False, scalar=None)
    return replace(result, rows=new_rows)


def _empty_result(returns: tuple[ReturnItem, ...]) -> CypherResult:
    return CypherResult(columns=tuple(_column_name(r) for r in returns), rows=())


def _first_pid(binding: Binding) -> PacketId:
    for v in binding.values():
        return v
    raise CypherError("empty binding")


def _validate(ast: CypherAST) -> None:
    if not ast.set_items and not ast.remove_items and not ast.returns:
        raise CypherError("query must contain at least one of SET, REMOVE, or RETURN")
    if ast.order_by and not ast.returns:
        raise CypherError("ORDER BY requires a RETURN clause")
    if ast.limit is not None and not ast.returns:
        raise CypherError("LIMIT requires a RETURN clause")
    if ast.limit is not None and ast.limit < 0:
        raise CypherError(f"LIMIT must be non-negative, got {ast.limit}")
    vars_declared = {n.var for n in ast.pattern.nodes}
    for item in ast.returns:
        if isinstance(item, (ReturnString, ReturnNumber)):
            continue
        if item.var not in vars_declared:
            raise CypherError(f"RETURN references undeclared variable {item.var!r}")
    if ast.where is not None:
        _check_where_vars(ast.where, vars_declared)
    for key in ast.order_by:
        var = key.field.split(".", 1)[0]
        if var not in vars_declared:
            raise CypherError(f"ORDER BY references undeclared variable {var!r}")
    for set_item in ast.set_items:
        if set_item.var not in vars_declared:
            raise CypherError(f"SET references undeclared variable {set_item.var!r}")
        _reject_pseudo_write("SET", set_item.var, set_item.field)
        _check_value_expr_vars(set_item.expr, vars_declared)
    for remove_item in ast.remove_items:
        if remove_item.var not in vars_declared:
            raise CypherError(f"REMOVE references undeclared variable {remove_item.var!r}")
        _reject_pseudo_write("REMOVE", remove_item.var, remove_item.field)


def _reject_pseudo_write(op: str, var: str, field: str) -> None:
    if field in PSEUDO_FIELDS:
        raise CypherError(f"cannot {op} pseudo-field {var}.{field}: pseudo-fields are read-only")


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


def _check_value_expr_vars(expr: ValueExpr, declared: set[str]) -> None:
    if isinstance(expr, LiteralExpr):
        return
    if isinstance(expr, FieldRef):
        if expr.var not in declared:
            raise CypherError(f"SET expression references undeclared variable {expr.var!r}")
        return
    if isinstance(expr, CallExpr):
        if not is_known_function(expr.name):
            raise unknown_function_error(expr.name)
        for arg in expr.args:
            _check_value_expr_vars(arg, declared)
        return
    if isinstance(expr, UnaryOp):
        _check_value_expr_vars(expr.operand, declared)
        return
    if isinstance(expr, BinaryOp):
        _check_value_expr_vars(expr.left, declared)
        _check_value_expr_vars(expr.right, declared)
        return
    if isinstance(expr, ListLit):
        for item in expr.items:
            _check_value_expr_vars(item, declared)
        return
    if isinstance(expr, ListComp):
        _check_value_expr_vars(expr.source, declared)
        inner = declared | {expr.var}
        if expr.predicate is not None:
            _check_listcomp_pred_vars(expr.predicate, inner)
        if expr.projection is not None:
            _check_value_expr_vars(expr.projection, inner)
        return
    raise CypherError(f"unknown value expression: {type(expr).__name__}")


def _check_listcomp_pred_vars(expr: ExprNode, declared: set[str]) -> None:
    if isinstance(expr, PredNode):
        field = expr.predicate.field
        var = field.split(".", 1)[0]
        if var not in declared:
            raise CypherError(f"list-comp predicate references undeclared variable {var!r}")
    elif isinstance(expr, (AndNode, OrNode)):
        for item in expr.items:
            _check_listcomp_pred_vars(item, declared)
    elif isinstance(expr, NotNode):
        _check_listcomp_pred_vars(expr.item, declared)


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
    return list(iter_forward_targets(workspace, pid, field, resolver))


def _build_edit_plan(
    set_items: tuple[SetItem, ...],
    remove_items: tuple[RemoveItem, ...],
    bindings: list[Binding],
    workspace: Workspace,
) -> EditPlan:
    set_assigns: dict[PacketId, dict[str, Any]] = {}
    appends: dict[PacketId, list[tuple[str, Any]]] = {}
    removes: dict[PacketId, list[str]] = {}
    field_kind: dict[tuple[PacketId, str], str] = {}
    errors_by_pid: dict[PacketId, str] = {}
    order: list[PacketId] = []
    seen: set[PacketId] = set()

    def touch(pid: PacketId) -> None:
        if pid not in seen:
            seen.add(pid)
            order.append(pid)

    for binding in bindings:
        for item in set_items:
            pid = binding.get(item.var)
            if pid is None:
                continue
            touch(pid)
            ctx = EvalCtx(workspace=workspace, binding=binding, origin=pid)
            try:
                value = eval_value_expr(item.expr, ctx)
            except BinaryOpError as e:
                # First error wins; subsequent set/remove ops for this pid are
                # dropped by the op-assembly loop below so the file gets no
                # partial write — the error op short-circuits at apply time.
                errors_by_pid.setdefault(pid, str(e))
                continue
            kind = "append" if item.op == "append" else "set"
            key = (pid, item.field)
            existing = field_kind.get(key)
            if existing is None:
                field_kind[key] = kind
            elif existing != kind:
                raise CypherError(
                    f"SET conflict on {pid}.{item.field}: cannot mix '{existing}' and '{kind}'"
                )
            if kind == "append":
                appends.setdefault(pid, []).append((item.field, value))
            else:
                pid_assigns = set_assigns.setdefault(pid, {})
                if item.field in pid_assigns:
                    prev = pid_assigns[item.field]
                    if prev != value:
                        raise CypherError(
                            f"SET conflict on {pid}.{item.field}: {prev!r} vs {value!r}"
                        )
                else:
                    pid_assigns[item.field] = value
        for r in remove_items:
            pid = binding.get(r.var)
            if pid is None:
                continue
            touch(pid)
            key = (pid, r.field)
            existing = field_kind.get(key)
            if existing is None:
                field_kind[key] = "remove"
            elif existing != "remove":
                raise CypherError(
                    f"SET/REMOVE conflict on {pid}.{r.field}: cannot both modify and remove"
                )
            bucket = removes.setdefault(pid, [])
            if r.field not in bucket:
                bucket.append(r.field)

    ops: list[EditOp] = []
    for pid in order:
        if pid in errors_by_pid:
            ops.append(EditOp(packet_id=pid, kind="error", args={"message": errors_by_pid[pid]}))
            continue
        rm = removes.get(pid)
        if rm:
            ops.append(EditOp(packet_id=pid, kind="remove", args={"fields": list(rm)}))
        assigns = set_assigns.get(pid)
        if assigns:
            ops.append(EditOp(packet_id=pid, kind="set", args={"assignments": dict(assigns)}))
        for field_name, value in appends.get(pid, []):
            ops.append(
                EditOp(
                    packet_id=pid,
                    kind="append",
                    args={"assignments": {field_name: value}},
                )
            )
    return EditPlan(workspace=workspace, ops=ops)


def _project(
    returns: tuple[ReturnItem, ...],
    bindings: list[Binding],
    workspace: Workspace,
    *,
    sort_rows: bool = True,
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
    rows = _dedupe_sort(rows, sort_rows=sort_rows)
    return CypherResult(columns=columns, rows=tuple(rows), is_scalar=False, scalar=None)


def _sort_bindings(
    bindings: list[Binding],
    keys: tuple[OrderKey, ...],
    workspace: Workspace,
) -> list[Binding]:
    def extract(binding: Binding, key: OrderKey) -> tuple[Any, bool]:
        from fmql.cypher.expr import RESERVED_VIRTUAL_FIELDS

        ref = key.field
        var, _, fname = ref.partition(".")
        pid = binding.get(var)
        if pid is None:
            return (None, True)
        if not fname:
            return (pid, False)
        if fname in PSEUDO_FIELDS:
            return (packet_field(workspace, pid, fname), False)
        packet = workspace.packets.get(pid)
        if packet is None:
            return (None, True)
        plain = packet.as_plain()
        if fname in plain:
            return (plain[fname], False)
        if fname in RESERVED_VIRTUAL_FIELDS:
            return (packet_field(workspace, pid, fname), False)
        return (None, True)

    return apply_order(bindings, keys, extract)


def _column_name(r: ReturnItem) -> str:
    if isinstance(r, ReturnVar):
        return r.var
    if isinstance(r, ReturnField):
        return f"{r.var}.{r.field}"
    if isinstance(r, ReturnCount):
        return f"count({r.var})"
    if isinstance(r, (ReturnString, ReturnNumber)):
        return r.text
    raise CypherError(f"unknown return item: {type(r).__name__}")


def _project_item(item: ReturnItem, binding: Binding, workspace: Workspace) -> Any:
    if isinstance(item, (ReturnString, ReturnNumber)):
        return item.value
    pid = binding[item.var]
    if isinstance(item, ReturnVar):
        return pid
    if isinstance(item, ReturnField):
        return packet_field(workspace, pid, item.field)
    raise CypherError(f"unprojectable item: {type(item).__name__}")


def _dedupe_sort(rows: list[tuple[Any, ...]], *, sort_rows: bool = True) -> list[tuple[Any, ...]]:
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
    if sort_rows:
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
