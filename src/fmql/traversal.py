from __future__ import annotations

import math
from typing import Any, Iterable, Iterator, Optional, Union

from fm.errors import QueryError
from fm.types import PacketId, Resolver
from fm.workspace import Workspace


def follow(
    workspace: Workspace,
    origin_ids: Iterable[PacketId],
    *,
    field: str,
    depth: Union[int, str] = 1,
    direction: str = "forward",
    resolver: Optional[Resolver] = None,
    include_origin: bool = False,
) -> list[PacketId]:
    r = resolver or workspace.resolvers.get(field) or workspace.default_resolver
    origin_set: set[PacketId] = set(origin_ids)

    if depth == "*" or depth == "all":
        max_depth: float = math.inf
    else:
        try:
            max_depth = int(depth)
        except (TypeError, ValueError) as e:
            raise QueryError(f"invalid depth: {depth!r}") from e
        if max_depth < 0:
            raise QueryError(f"invalid depth: {depth!r}")

    visited: set[PacketId] = set(origin_set)
    frontier: set[PacketId] = set(origin_set)
    collected: set[PacketId] = set()
    hop = 0
    while frontier and hop < max_depth:
        next_frontier: set[PacketId] = set()
        for src in frontier:
            for tgt in _neighbors(workspace, src, field, r, direction):
                if tgt in visited:
                    continue
                visited.add(tgt)
                next_frontier.add(tgt)
                collected.add(tgt)
        frontier = next_frontier
        hop += 1

    result = (origin_set | collected) if include_origin else collected
    return sorted(result)


def _neighbors(
    workspace: Workspace,
    pid: PacketId,
    field: str,
    resolver: Resolver,
    direction: str,
) -> Iterator[PacketId]:
    if direction == "forward":
        packet = workspace.packets.get(pid)
        if packet is None:
            return
        raw = packet.as_plain().get(field)
        for item in _iter_raw(raw):
            tgt = resolver.resolve(item, origin=pid, workspace=workspace)
            if tgt is not None:
                yield tgt
    elif direction == "reverse":
        yield from workspace.reverse_index(field, resolver).get(pid, ())
    else:
        raise QueryError(f"invalid direction: {direction!r}")


def _iter_raw(raw: Any) -> Iterator[Any]:
    if raw is None:
        return
    if isinstance(raw, (list, tuple)):
        yield from raw
    else:
        yield raw
