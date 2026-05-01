from __future__ import annotations

import itertools
import json
from dataclasses import replace
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from fmql.cli._run import cli_guard, parse_depth, resolve_workspace, run_plan
from fmql.cypher import compile_cypher_ast, parse_cypher
from fmql.cypher.ast import ReturnVar
from fmql.diagnostics import maybe_emit_warnings
from fmql.errors import CypherError
from fmql.query import IdSetStage, Query
from fmql.resolvers import resolver_by_name
from fmql.serialization import json_default
from fmql.workspace import Workspace


class QueryFormat(str, Enum):
    paths = "paths"
    rows = "rows"
    json = "json"


class Direction(str, Enum):
    forward = "forward"
    reverse = "reverse"


def _format_cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def _is_single_packet_var(ast) -> bool:
    return len(ast.returns) == 1 and isinstance(ast.returns[0], ReturnVar)


@cli_guard
def query_cmd(
    query: str = typer.Argument(
        ...,
        help=(
            "Cypher query "
            "(MATCH ... [WHERE ...] [SET|REMOVE ...] [RETURN ...] [ORDER BY ...] [LIMIT N])."
        ),
    ),
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace root (default: cwd)."
    ),
    fmt: Optional[QueryFormat] = typer.Option(
        None,
        "--format",
        "-f",
        help="Output format: paths | rows | json "
        "(default: paths for single-var RETURN, rows otherwise).",
    ),
    follow: Optional[str] = typer.Option(None, "--follow", help="Field name to traverse."),
    depth: str = typer.Option("1", "--depth", help="Hops to traverse: integer or '*' (or 'all')."),
    direction: Direction = typer.Option(Direction.forward, "--direction", help="forward | reverse"),
    include_origin: bool = typer.Option(
        False, "--include-origin", help="Include origin packets in output (with --follow)."
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
        False, "--dry-run", help="With SET/REMOVE: preview changes without writing."
    ),
    yes: bool = typer.Option(False, "--yes", help="With SET/REMOVE: skip the confirmation prompt."),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        min=0,
        help="Cap output rows. With an in-query LIMIT, the more restrictive cap applies.",
    ),
) -> int:
    default_r = resolver_by_name(resolver) if resolver else None
    ws_root = resolve_workspace(workspace)
    ws = Workspace(ws_root, default_resolver=default_r)
    ast = parse_cypher(query)

    use_query_path = follow is not None or search is not None
    if limit is not None and not use_query_path:
        # Direct path: --limit caps the same row stream as in-query LIMIT;
        # fold them into one cap and let the executor enforce it.
        merged = limit if ast.limit is None else min(ast.limit, limit)
        ast = replace(ast, limit=merged)
    single_var = _is_single_packet_var(ast)
    effective_fmt = (
        fmt if fmt is not None else (QueryFormat.paths if single_var else QueryFormat.rows)
    )

    if use_query_path:
        if ast.set_items or ast.remove_items:
            raise CypherError(
                "SET/REMOVE incompatible with --follow/--search; use 'fmql update' instead"
            )
        if not single_var:
            raise CypherError(
                "--follow/--search require a single packet variable in RETURN "
                "(e.g. 'MATCH (t) RETURN t')"
            )
        execution = compile_cypher_ast(ast, ws)
        if execution.result is None:
            raise CypherError("query has no RETURN clause; expected packet rows")
        seed_ids = frozenset(row[0] for row in execution.result.rows)
        q = Query(ws, _stages=(IdSetStage(ids=seed_ids),))
        if search is not None:
            q = q.search(search, index=index, location=index_location)
        follow_resolver = None
        if follow is not None:
            d = parse_depth(depth)
            follow_resolver = resolver_by_name(resolver) if resolver else None
            q = q.follow(
                follow,
                depth=d,
                direction=direction.value,
                resolver=follow_resolver,
                include_origin=include_origin,
            )
        packets = list(itertools.islice(q, limit) if limit is not None else q)
        _emit_packets(packets, effective_fmt)
        if follow is not None:
            maybe_emit_warnings(ws, [follow], diagnose=diagnose, resolver=follow_resolver)
        if ast.pattern.rels:
            maybe_emit_warnings(ws, (rel.field for rel in ast.pattern.rels), diagnose=diagnose)
        return 0

    execution = compile_cypher_ast(ast, ws)
    code = run_plan(execution.plan, dry_run=dry_run, yes=yes) if execution.plan is not None else 0

    if execution.result is not None and code == 0:
        result = execution.result
        if effective_fmt is QueryFormat.paths:
            if not single_var:
                raise CypherError("--format paths requires a single packet variable in RETURN")
            for row in result.rows:
                typer.echo(row[0])
        elif effective_fmt is QueryFormat.rows:
            if result.is_scalar:
                typer.echo(str(result.scalar))
            else:
                for row in result.rows:
                    typer.echo("\t".join(_format_cell(v) for v in row))
        else:
            if result.is_scalar:
                typer.echo(json.dumps({"count": result.scalar}))
            elif single_var:
                for row in result.rows:
                    pid = row[0]
                    packet = ws.packets.get(pid)
                    payload = {
                        "id": pid,
                        "frontmatter": packet.as_plain() if packet else {},
                    }
                    typer.echo(json.dumps(payload, default=json_default, ensure_ascii=False))
            else:
                cols = list(result.columns)
                for row in result.rows:
                    payload = {"columns": cols, "row": list(row)}
                    typer.echo(json.dumps(payload, default=json_default, ensure_ascii=False))

    if ast.pattern.rels:
        maybe_emit_warnings(ws, (rel.field for rel in ast.pattern.rels), diagnose=diagnose)

    return code


def _emit_packets(packets, fmt: QueryFormat) -> None:
    if fmt is QueryFormat.json:
        for p in packets:
            payload = {"id": p.id, "frontmatter": p.as_plain()}
            typer.echo(json.dumps(payload, default=json_default, ensure_ascii=False))
    else:
        for p in packets:
            typer.echo(p.id)
