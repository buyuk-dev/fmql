from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union

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
class CypherAST:
    pattern: Pattern
    where: Optional[ExprNode]
    returns: tuple[ReturnItem, ...]
    order_by: tuple[OrderKey, ...] = ()


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
