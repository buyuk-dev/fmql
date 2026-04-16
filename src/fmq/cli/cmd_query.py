from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Union

import typer

from fmq.errors import FmqError
from fmq.qlang import compile_query
from fmq.resolvers import resolver_by_name
from fmq.workspace import Workspace


class OutputFormat(str, Enum):
    paths = "paths"
    json = "json"


class Direction(str, Enum):
    forward = "forward"
    reverse = "reverse"


def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(f"not JSON-serializable: {type(o).__name__}")


def _parse_depth(depth: str) -> Union[int, str]:
    if depth in ("*", "all"):
        return "*"
    try:
        n = int(depth)
    except ValueError as e:
        raise FmqError(f"invalid --depth {depth!r}: expected integer or '*'") from e
    if n < 0:
        raise FmqError(f"invalid --depth {depth!r}: must be non-negative")
    return n


def query_cmd(
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    query: str = typer.Argument(..., help="qlang expression or '*' for all"),
    fmt: OutputFormat = typer.Option(OutputFormat.paths, "--format", "-f", help="Output format."),
    follow: Optional[str] = typer.Option(None, "--follow", help="Field name to traverse."),
    depth: str = typer.Option("1", "--depth", help="Hops to traverse: integer or '*' (or 'all')."),
    direction: Direction = typer.Option(Direction.forward, "--direction", help="forward | reverse"),
    resolver: Optional[str] = typer.Option(None, "--resolver", help="path | uuid | slug (default: path)."),
    include_origin: bool = typer.Option(False, "--include-origin", help="Include origin packets in output."),
    search: Optional[str] = typer.Option(None, "--search", help="Narrow results to packets matching this search query."),
    index: str = typer.Option("text", "--index", help="Search index name (default: text)."),
) -> None:
    try:
        ws = Workspace(path)
        q = compile_query(query, ws)
        if search is not None:
            q = q.search(search, index=index)
        if follow is not None:
            d = _parse_depth(depth)
            r = resolver_by_name(resolver) if resolver else None
            q = q.follow(
                follow,
                depth=d,
                direction=direction.value,
                resolver=r,
                include_origin=include_origin,
            )
        packets = list(q)
    except FmqError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2)

    if fmt is OutputFormat.paths:
        for packet in packets:
            typer.echo(packet.id)
    else:
        for packet in packets:
            payload = {"id": packet.id, "frontmatter": packet.as_plain()}
            typer.echo(json.dumps(payload, default=_json_default, ensure_ascii=False))
