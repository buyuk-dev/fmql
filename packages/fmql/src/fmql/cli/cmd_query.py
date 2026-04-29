from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Optional, Union

import typer

from fmql.cli._run import resolve_workspace
from fmql.diagnostics import maybe_emit_warnings
from fmql.errors import FmqlError
from fmql.qlang import compile_query
from fmql.resolvers import resolver_by_name
from fmql.serialization import json_default
from fmql.workspace import Workspace


class OutputFormat(str, Enum):
    paths = "paths"
    json = "json"


class Direction(str, Enum):
    forward = "forward"
    reverse = "reverse"


def _parse_depth(depth: str) -> Union[int, str]:
    if depth in ("*", "all"):
        return "*"
    try:
        n = int(depth)
    except ValueError as e:
        raise FmqlError(f"invalid --depth {depth!r}: expected integer or '*'") from e
    if n < 0:
        raise FmqlError(f"invalid --depth {depth!r}: must be non-negative")
    return n


def query_cmd(
    query: str = typer.Argument(..., help="qlang expression or '*' for all"),
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace root (default: cwd)."
    ),
    fmt: OutputFormat = typer.Option(OutputFormat.paths, "--format", "-f", help="Output format."),
    follow: Optional[str] = typer.Option(None, "--follow", help="Field name to traverse."),
    depth: str = typer.Option("1", "--depth", help="Hops to traverse: integer or '*' (or 'all')."),
    direction: Direction = typer.Option(Direction.forward, "--direction", help="forward | reverse"),
    resolver: Optional[str] = typer.Option(
        None, "--resolver", help="path | uuid | slug | id (default: path)."
    ),
    include_origin: bool = typer.Option(
        False, "--include-origin", help="Include origin packets in output."
    ),
    search: Optional[str] = typer.Option(
        None, "--search", help="Narrow results to packets matching this search query."
    ),
    index: str = typer.Option("grep", "--index", help="Search backend name (default: grep)."),
    index_location: Optional[str] = typer.Option(
        None,
        "--index-location",
        help="Location string for indexed backends (path / URI). Ignored by scan backends.",
    ),
    diagnose: bool = typer.Option(
        False,
        "--diagnose",
        help="Emit stderr warnings for unresolved reference values "
        "(extra workspace scan per follow-field; default: off).",
    ),
) -> None:
    r = None
    try:
        ws_root = resolve_workspace(workspace)
        ws = Workspace(ws_root)
        q = compile_query(query, ws)
        if search is not None:
            q = q.search(search, index=index, location=index_location)
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
    except FmqlError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2)

    if fmt is OutputFormat.paths:
        for packet in packets:
            typer.echo(packet.id)
    else:
        for packet in packets:
            payload = {"id": packet.id, "frontmatter": packet.as_plain()}
            typer.echo(json.dumps(payload, default=json_default, ensure_ascii=False))

    if follow is not None:
        maybe_emit_warnings(ws, [follow], diagnose=diagnose, resolver=r)
