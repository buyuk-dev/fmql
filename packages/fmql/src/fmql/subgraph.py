from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Optional, Union

from fmql.errors import QueryError
from fmql.types import PacketId, Resolver
from fmql.workspace import Workspace


@dataclass(frozen=True)
class Edge:
    source: PacketId
    target: PacketId
    field: str


@dataclass(frozen=True)
class Subgraph:
    nodes: tuple[PacketId, ...]
    edges: tuple[Edge, ...]


def collect_subgraph(
    workspace: Workspace,
    origins: Iterable[PacketId],
    *,
    fields: Iterable[str],
    depth: Union[int, str] = "*",
    direction: str = "forward",
    resolver: Optional[Resolver] = None,
    include_origin: bool = True,
) -> Subgraph:
    field_list = tuple(fields)
    if not field_list:
        raise QueryError("collect_subgraph requires at least one field")

    if depth == "*" or depth == "all":
        max_depth: float = math.inf
    else:
        try:
            max_depth = int(depth)
        except (TypeError, ValueError) as e:
            raise QueryError(f"invalid depth: {depth!r}") from e
        if max_depth < 0:
            raise QueryError(f"invalid depth: {depth!r}")

    if direction not in ("forward", "reverse"):
        raise QueryError(f"invalid direction: {direction!r}")

    origin_set: set[PacketId] = {pid for pid in origins if pid in workspace.packets}

    eff_resolvers = {
        field: resolver or workspace.resolvers.get(field) or workspace.default_resolver
        for field in field_list
    }

    visited: set[PacketId] = set(origin_set)
    frontier: set[PacketId] = set(origin_set)
    edges: set[Edge] = set()
    hop = 0
    while frontier and hop < max_depth:
        next_frontier: set[PacketId] = set()
        for pid in frontier:
            for field in field_list:
                for source, target in _edges_for(
                    workspace, pid, field, eff_resolvers[field], direction
                ):
                    edges.add(Edge(source=source, target=target, field=field))
                    neighbor = target if direction == "forward" else source
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
        frontier = next_frontier
        hop += 1

    nodes = visited if include_origin else (visited - origin_set)
    return Subgraph(
        nodes=tuple(sorted(nodes)),
        edges=tuple(sorted(edges, key=lambda e: (e.source, e.target, e.field))),
    )


def _edges_for(
    workspace: Workspace,
    pid: PacketId,
    field: str,
    resolver: Resolver,
    direction: str,
) -> Iterator[tuple[PacketId, PacketId]]:
    if direction == "forward":
        packet = workspace.packets.get(pid)
        if packet is None:
            return
        raw = packet.as_plain().get(field)
        for item in _iter_raw(raw):
            tgt = resolver.resolve(item, origin=pid, workspace=workspace)
            if tgt is not None:
                yield (pid, tgt)
    else:
        for src in workspace.reverse_index(field, resolver).get(pid, ()):
            yield (src, pid)


def _iter_raw(raw: Any) -> Iterator[Any]:
    if raw is None:
        return
    if isinstance(raw, (list, tuple)):
        yield from raw
    else:
        yield raw
