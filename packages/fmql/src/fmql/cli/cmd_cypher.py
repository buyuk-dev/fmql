from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from fmql.cli._run import resolve_workspace, run_plan
from fmql.cypher import compile_cypher_ast, parse_cypher
from fmql.diagnostics import maybe_emit_warnings
from fmql.errors import FmqlError
from fmql.resolvers import resolver_by_name
from fmql.serialization import json_default
from fmql.workspace import Workspace


class CypherFormat(str, Enum):
    rows = "rows"
    json = "json"


def _format_cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def cypher_cmd(
    query: str = typer.Argument(..., help="Cypher subset query (MATCH ... [SET ...] [RETURN ...])"),
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace root (default: cwd)."
    ),
    fmt: CypherFormat = typer.Option(CypherFormat.rows, "--format", "-f", help="Output format."),
    resolver: Optional[str] = typer.Option(
        None,
        "--resolver",
        help="Default resolver applied to every relationship: path | uuid | slug | id.",
    ),
    diagnose: bool = typer.Option(
        False,
        "--diagnose",
        help="Emit stderr warnings for unresolved reference values "
        "(extra workspace scan per relationship field; default: off).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="With SET: preview changes without writing."
    ),
    yes: bool = typer.Option(False, "--yes", help="With SET: skip the confirmation prompt."),
) -> None:
    try:
        default_r = resolver_by_name(resolver) if resolver else None
        ws_root = resolve_workspace(workspace)
        ws = Workspace(ws_root, default_resolver=default_r)
        ast = parse_cypher(query)
        execution = compile_cypher_ast(ast, ws)
    except FmqlError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2)

    code = run_plan(execution.plan, dry_run=dry_run, yes=yes) if execution.plan is not None else 0

    if execution.result is not None and code == 0:
        result = execution.result
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
                    typer.echo(json.dumps(payload, default=json_default, ensure_ascii=False))

    if ast.pattern.rels:
        maybe_emit_warnings(ws, (rel.field for rel in ast.pattern.rels), diagnose=diagnose)

    if code != 0:
        raise typer.Exit(code=code)
