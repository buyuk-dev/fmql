from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from fmql.cli._edit_common import cli_guard, run_plan
from fmql.cypher import compile_cypher_ast, parse_cypher
from fmql.diagnostics import maybe_emit_warnings
from fmql.errors import CypherError
from fmql.resolvers import resolver_by_name
from fmql.workspace import Workspace


@cli_guard
def update_cmd(
    path: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, resolve_path=True
    ),
    query: str = typer.Argument(..., help="Cypher subset query with a SET clause."),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    resolver: Optional[str] = typer.Option(
        None,
        "--resolver",
        help="Default resolver applied to every relationship: path | uuid | slug | id.",
    ),
    diagnose: bool = typer.Option(
        False,
        "--diagnose",
        help="Emit stderr warnings for unresolved reference values.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
) -> int:
    default_r = resolver_by_name(resolver) if resolver else None
    ws_root = workspace.resolve() if workspace is not None else path
    ws = Workspace(ws_root, default_resolver=default_r)

    ast = parse_cypher(query)
    if not ast.set_items:
        raise CypherError("update requires a SET clause; use 'fmql cypher' for read-only queries")
    if ast.returns or ast.order_by:
        raise CypherError(
            "update does not support RETURN or ORDER BY; use 'fmql cypher' for projections"
        )

    execution = compile_cypher_ast(ast, ws)
    code = run_plan(execution.plan, dry_run=dry_run, yes=yes)
    if ast.pattern.rels:
        maybe_emit_warnings(ws, (rel.field for rel in ast.pattern.rels), diagnose=diagnose)
    return code
