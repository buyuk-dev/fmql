from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Union

from fmq.filters import Predicate, match, parse_kwargs
from fmq.packet import Packet
from fmq.types import PacketId
from fmq.workspace import Workspace


@dataclass(frozen=True)
class PredNode:
    predicate: Predicate


@dataclass(frozen=True)
class AndNode:
    items: tuple["ExprNode", ...]


@dataclass(frozen=True)
class OrNode:
    items: tuple["ExprNode", ...]


@dataclass(frozen=True)
class NotNode:
    item: "ExprNode"


ExprNode = Union[PredNode, AndNode, OrNode, NotNode]


def _eval(expr: ExprNode, packet: Packet) -> bool:
    if isinstance(expr, PredNode):
        return match(packet, expr.predicate)
    if isinstance(expr, AndNode):
        return all(_eval(e, packet) for e in expr.items)
    if isinstance(expr, OrNode):
        return any(_eval(e, packet) for e in expr.items)
    if isinstance(expr, NotNode):
        return not _eval(expr.item, packet)
    raise TypeError(f"unknown expr node: {type(expr).__name__}")


@dataclass(frozen=True)
class Query:
    workspace: Workspace
    _exprs: tuple[ExprNode, ...] = field(default_factory=tuple)

    def where(self, **kwargs: Any) -> "Query":
        preds = parse_kwargs(kwargs)
        if not preds:
            return self
        nodes = tuple(PredNode(p) for p in preds)
        expr: ExprNode = nodes[0] if len(nodes) == 1 else AndNode(nodes)
        return Query(self.workspace, self._exprs + (expr,))

    def where_expr(self, expr: ExprNode) -> "Query":
        return Query(self.workspace, self._exprs + (expr,))

    def all(self) -> "Query":
        return self

    def _matches(self, packet: Packet) -> bool:
        return all(_eval(expr, packet) for expr in self._exprs)

    def __iter__(self) -> Iterator[Packet]:
        for pid in sorted(self.workspace.packets):
            packet = self.workspace.packets[pid]
            if self._matches(packet):
                yield packet

    def ids(self) -> list[PacketId]:
        return [p.id for p in self]
