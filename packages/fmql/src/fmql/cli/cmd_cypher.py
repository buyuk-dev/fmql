from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from fmql.cypher import compile_cypher_ast, parse_cypher
from fmql.diagnostics import emit_resolver_mismatch_hints
from fmql.errors import FmqlError
from fmql.resolvers import resolver_by_name
from fmql.workspace import Workspace


class CypherFormat(str, Enum):
    rows = "rows"
    json = "json"


def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(f"not JSON-serializable: {type(o).__name__}")


def _format_cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def cypher_cmd(
    path: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, resolve_path=True
    ),
    query: str = typer.Argument(..., help="Cypher subset query (MATCH ... [WHERE ...] RETURN ...)"),
    fmt: CypherFormat = typer.Option(CypherFormat.rows, "--format", "-f", help="Output format."),
    resolver: Optional[str] = typer.Option(
        None,
        "--resolver",
        help="Default resolver applied to every relationship: path | uuid | slug.",
    ),
) -> None:
    try:
        default_r = resolver_by_name(resolver) if resolver else None
        ws = Workspace(path, default_resolver=default_r)
        ast = parse_cypher(query)
        result = compile_cypher_ast(ast, ws)
    except FmqlError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2)

    if fmt is CypherFormat.rows:
        if result.is_scalar:
            typer.echo(str(result.scalar))
        else:
            for row in result.rows:
                typer.echo("\t".join(_format_cell(v) for v in row))
    else:
        if result.is_scalar:
            typer.echo(json.dumps({"count": result.scalar}))
        else:
            cols = list(result.columns)
            for row in result.rows:
                payload = {"columns": cols, "row": list(row)}
                typer.echo(json.dumps(payload, default=_json_default, ensure_ascii=False))

    if not result.is_scalar and not result.rows:
        emit_resolver_mismatch_hints(ws, (rel.field for rel in ast.pattern.rels))
