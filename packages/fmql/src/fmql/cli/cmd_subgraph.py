from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer

from fmql.cli._run import parse_depth, resolve_workspace
from fmql.diagnostics import maybe_emit_warnings
from fmql.errors import FmqlError
from fmql.query import Query
from fmql.resolvers import resolver_by_name
from fmql.serialization import json_default
from fmql.subgraph import collect_subgraph
from fmql.subgraph_formats import SubgraphFormat, format_subgraph
from fmql.workspace import Workspace


class Direction(str, Enum):
    forward = "forward"
    reverse = "reverse"


def subgraph_cmd(
    query: str = typer.Argument(
        ...,
        help="Cypher query (MATCH ... RETURN var) selecting seed packets.",
    ),
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace root (default: cwd)."
    ),
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
        None, "--resolver", help="path | uuid | slug | id (default: per-workspace default)."
    ),
    include_origin: bool = typer.Option(
        True,
        "--include-origin/--no-include-origin",
        help="Whether to include seed packets in the subgraph.",
    ),
    ids_only: bool = typer.Option(
        False, "--ids-only", help="Emit nodes as ids only (omit frontmatter)."
    ),
    fmt: SubgraphFormat = typer.Option(
        SubgraphFormat.raw,
        "--format",
        help="Output format: raw (default) | cytoscape.",
    ),
    diagnose: bool = typer.Option(
        False,
        "--diagnose",
        help="Emit stderr warnings for unresolved reference values "
        "(extra workspace scan per follow-field; default: off).",
    ),
) -> None:
    try:
        ws_root = resolve_workspace(workspace)
        ws = Workspace(ws_root)
        seeds = Query(ws).cypher(query).ids()
        d = parse_depth(depth)
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
    output = format_subgraph({"nodes": nodes_payload, "edges": edges_payload}, fmt)
    typer.echo(json.dumps(output, default=json_default, ensure_ascii=False))

    maybe_emit_warnings(ws, fields, diagnose=diagnose, resolver=r)
