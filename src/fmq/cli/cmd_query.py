from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path

import typer

from fmq.errors import FmqError
from fmq.qlang import compile_query
from fmq.workspace import Workspace


class OutputFormat(str, Enum):
    paths = "paths"
    json = "json"


def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(f"not JSON-serializable: {type(o).__name__}")


def query_cmd(
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    query: str = typer.Argument(..., help="qlang expression or '*' for all"),
    fmt: OutputFormat = typer.Option(OutputFormat.paths, "--format", "-f", help="Output format."),
) -> None:
    try:
        ws = Workspace(path)
        q = compile_query(query, ws)
    except FmqError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2)

    if fmt is OutputFormat.paths:
        for packet in q:
            typer.echo(packet.id)
    else:
        for packet in q:
            payload = {"id": packet.id, "frontmatter": packet.as_plain()}
            typer.echo(json.dumps(payload, default=_json_default, ensure_ascii=False))
