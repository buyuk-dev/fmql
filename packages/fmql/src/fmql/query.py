from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator, Optional, Union

from fmql.filters import Predicate, match, parse_kwargs
from fmql.packet import Packet
from fmql.types import PacketId, Resolver
from fmql.workspace import Workspace

if TYPE_CHECKING:
    from fmql.aggregation import GroupedQuery
    from fmql.edits import EditPlan


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
class FilterStage:
    expr: ExprNode


@dataclass(frozen=True)
class FollowStage:
    field: str
    depth: Union[int, str]
    direction: str
    resolver: Optional[Resolver]
    include_origin: bool


@dataclass(frozen=True)
class SearchStage:
    index_name: str
    query: str
    location: Optional[str] = None
    options: Optional[tuple[tuple[str, Any], ...]] = None


@dataclass(frozen=True)
class IdSetStage:
    ids: frozenset[PacketId]


Stage = Union[FilterStage, FollowStage, SearchStage, IdSetStage]


@dataclass(frozen=True)
class Query:
    workspace: Workspace
    _stages: tuple[Stage, ...] = field(default_factory=tuple)

    def where(self, **kwargs: Any) -> "Query":
        preds = parse_kwargs(kwargs)
        if not preds:
            return self
        nodes = tuple(PredNode(p) for p in preds)
        expr: ExprNode = nodes[0] if len(nodes) == 1 else AndNode(nodes)
        return Query(self.workspace, self._stages + (FilterStage(expr),))

    def where_expr(self, expr: ExprNode) -> "Query":
        return Query(self.workspace, self._stages + (FilterStage(expr),))

    def follow(
        self,
        field: str,
        *,
        depth: Union[int, str] = 1,
        direction: str = "forward",
        resolver: Optional[Resolver] = None,
        include_origin: bool = False,
    ) -> "Query":
        stage = FollowStage(field, depth, direction, resolver, include_origin)
        return Query(self.workspace, self._stages + (stage,))

    def all(self) -> "Query":
        return self

    def search(
        self,
        query: str,
        *,
        index: str = "grep",
        location: Optional[str] = None,
        options: Optional[dict] = None,
    ) -> "Query":
        opts = tuple(sorted(options.items())) if options else None
        stage = SearchStage(index_name=index, query=query, location=location, options=opts)
        return Query(self.workspace, self._stages + (stage,))

    def cypher(self, text: str) -> "Query":
        from fmql.cypher.ast import ReturnVar
        from fmql.cypher.compile import parse_cypher
        from fmql.cypher.executor import compile_cypher_ast
        from fmql.errors import CypherUnsupported

        ast = parse_cypher(text)
        if len(ast.returns) != 1 or not isinstance(ast.returns[0], ReturnVar):
            raise CypherUnsupported(
                "Query.cypher supports only single-variable RETURN; "
                "use fmql.cypher.compile_cypher() or the `fmql cypher` CLI for richer results"
            )
        result = compile_cypher_ast(ast, self.workspace)
        id_set = frozenset(row[0] for row in result.rows)
        return Query(self.workspace, self._stages + (IdSetStage(ids=id_set),))

    def group_by(self, field: str) -> "GroupedQuery":
        from fmql.aggregation import GroupedQuery

        return GroupedQuery(self, field)

    def _execute(self) -> list[PacketId]:
        ids: list[PacketId] = sorted(self.workspace.packets)
        for stage in self._stages:
            if isinstance(stage, FilterStage):
                ids = [pid for pid in ids if _eval(stage.expr, self.workspace.packets[pid])]
            elif isinstance(stage, SearchStage):
                from fmql.search import BackendKindError, get_backend, is_indexed

                backend = get_backend(stage.index_name)
                opts = dict(stage.options) if stage.options else None
                k = len(self.workspace.packets) or 1
                if is_indexed(backend):
                    location = stage.location or backend.default_location(self.workspace)
                    if location is None:
                        raise BackendKindError(
                            f"backend {stage.index_name!r} is indexed and requires "
                            f"an index location; pass location= to Query.search() "
                            f"or --index-location on the CLI"
                        )
                    raw_hits = backend.query(stage.query, location, k=k, options=opts)
                else:
                    raw_hits = backend.query(stage.query, self.workspace, k=k, options=opts)
                hits = {h.packet_id for h in raw_hits}
                ids = [pid for pid in ids if pid in hits]
            elif isinstance(stage, IdSetStage):
                ids = [pid for pid in ids if pid in stage.ids]
            else:
                from fmql.traversal import follow

                ids = follow(
                    self.workspace,
                    ids,
                    field=stage.field,
                    depth=stage.depth,
                    direction=stage.direction,
                    resolver=stage.resolver,
                    include_origin=stage.include_origin,
                )
        return ids

    def __iter__(self) -> Iterator[Packet]:
        for pid in self._execute():
            yield self.workspace.packets[pid]

    def ids(self) -> list[PacketId]:
        return self._execute()

    def set(self, **assignments: Any) -> "EditPlan":
        from fmql.edits import plan_set

        return plan_set(self.workspace, self.ids(), **assignments)

    def remove(self, *fields: str) -> "EditPlan":
        from fmql.edits import plan_remove

        return plan_remove(self.workspace, self.ids(), *fields)

    def rename(self, **mapping: str) -> "EditPlan":
        from fmql.edits import plan_rename

        return plan_rename(self.workspace, self.ids(), **mapping)

    def append(self, **assignments: Any) -> "EditPlan":
        from fmql.edits import plan_append

        return plan_append(self.workspace, self.ids(), **assignments)

    def toggle(self, *fields: str) -> "EditPlan":
        from fmql.edits import plan_toggle

        return plan_toggle(self.workspace, self.ids(), *fields)
