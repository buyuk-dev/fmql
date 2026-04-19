from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union

import typer

from fmql.diagnostics import diagnose_resolver_mismatch
from fmql.errors import FmqlError
from fmql.qlang import compile_query
from fmql.resolvers import resolver_by_name
from fmql.subgraph import collect_subgraph
from fmql.workspace import Workspace


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
        raise FmqlError(f"invalid --depth {depth!r}: expected integer or '*'") from e
    if n < 0:
        raise FmqlError(f"invalid --depth {depth!r}: must be non-negative")
    return n


def subgraph_cmd(
    path: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, resolve_path=True
    ),
    query: str = typer.Argument(..., help="qlang expression selecting seed packets (or '*')."),
    fields: List[str] = typer.Option(
        ...,
        "--follow",
        help="Relationship field to traverse (repeatable for multiple fields).",
    ),
    depth: str = typer.Option(
        "*", "--depth", help="Hops to traverse: integer or '*' (default: full closure)."
    ),
    direction: Direction = typer.Option(Direction.forward, "--direction", help="forward | reverse"),
    resolver: Optional[str] = typer.Option(
        None, "--resolver", help="path | uuid | slug (default: per-workspace default)."
    ),
    include_origin: bool = typer.Option(
        True,
        "--include-origin/--no-include-origin",
        help="Whether to include seed packets in the subgraph.",
    ),
    ids_only: bool = typer.Option(
        False, "--ids-only", help="Emit nodes as ids only (omit frontmatter)."
    ),
) -> None:
    try:
        ws = Workspace(path)
        seeds = compile_query(query, ws).ids()
        d = _parse_depth(depth)
        r = resolver_by_name(resolver) if resolver else None
        sg = collect_subgraph(
            ws,
            seeds,
            fields=fields,
            depth=d,
            direction=direction.value,
            resolver=r,
            include_origin=include_origin,
        )
    except FmqlError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2)

    if ids_only:
        nodes_payload = [{"id": pid} for pid in sg.nodes]
    else:
        nodes_payload = []
        for pid in sg.nodes:
            packet = ws.packets.get(pid)
            nodes_payload.append({"id": pid, "frontmatter": packet.as_plain() if packet else {}})
    edges_payload = [{"source": e.source, "target": e.target, "field": e.field} for e in sg.edges]
    typer.echo(
        json.dumps(
            {"nodes": nodes_payload, "edges": edges_payload},
            default=_json_default,
            ensure_ascii=False,
        )
    )

    if not sg.edges and seeds:
        seen: set[str] = set()
        for field in fields:
            if field in seen:
                continue
            seen.add(field)
            eff_resolver = r or ws.resolvers.get(field) or ws.default_resolver
            hint = diagnose_resolver_mismatch(ws, field, eff_resolver)
            if hint is not None:
                typer.echo(hint, err=True)
