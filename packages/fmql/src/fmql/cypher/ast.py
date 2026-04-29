from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Union

from fmql.ordering import OrderKey
from fmql.query import ExprNode


@dataclass(frozen=True)
class NodePat:
    var: str
    label: Optional[str] = None


@dataclass(frozen=True)
class RelHop:
    field: str
    min_hops: int
    max_hops: Optional[int]


@dataclass(frozen=True)
class Pattern:
    nodes: tuple[NodePat, ...]
    rels: tuple[RelHop, ...]


@dataclass(frozen=True)
class ReturnVar:
    var: str


@dataclass(frozen=True)
class ReturnField:
    var: str
    field: str


@dataclass(frozen=True)
class ReturnCount:
    var: str


ReturnItem = Union[ReturnVar, ReturnField, ReturnCount]


@dataclass(frozen=True)
class LiteralExpr:
    value: Any


@dataclass(frozen=True)
class FieldRef:
    var: str
    field: Optional[str] = None


@dataclass(frozen=True)
class CallExpr:
    name: str
    args: tuple["ValueExpr", ...]


@dataclass(frozen=True)
class UnaryOp:
    op: str
    operand: "ValueExpr"


@dataclass(frozen=True)
class ListLit:
    items: tuple["ValueExpr", ...]


@dataclass(frozen=True)
class ListComp:
    var: str
    source: "ValueExpr"
    predicate: Optional[ExprNode]
    projection: Optional["ValueExpr"]


ValueExpr = Union[LiteralExpr, FieldRef, CallExpr, UnaryOp, ListLit, ListComp]


SetOp = Literal["set", "append"]


@dataclass(frozen=True)
class SetItem:
    var: str
    field: str
    expr: ValueExpr
    op: SetOp = "set"


@dataclass(frozen=True)
class RemoveItem:
    var: str
    field: str


@dataclass(frozen=True)
class CypherAST:
    pattern: Pattern
    where: Optional[ExprNode] = None
    returns: tuple[ReturnItem, ...] = ()
    order_by: tuple[OrderKey, ...] = ()
    set_items: tuple[SetItem, ...] = ()
    remove_items: tuple[RemoveItem, ...] = ()


@dataclass(frozen=True)
class CypherResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    is_scalar: bool = False
    scalar: Optional[int] = None

    def __iter__(self):
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)
