from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from fmql.cli._run import resolve_workspace
from fmql.describe import describe, format_json, format_text
from fmql.errors import FmqlError
from fmql.workspace import Workspace


class DescribeFormat(str, Enum):
    text = "text"
    json = "json"


def describe_cmd(
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace root (default: cwd)."
    ),
    fmt: DescribeFormat = typer.Option(
        DescribeFormat.text, "--format", "-f", help="Output format: text | json."
    ),
    top_n: int = typer.Option(5, "--top", help="Max distinct values to show per field."),
) -> None:
    try:
        ws_root = resolve_workspace(workspace)
        ws = Workspace(ws_root)
    except (FmqlError, FileNotFoundError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2)
    stats = describe(ws, top_n=top_n)
    output = format_text(stats) if fmt is DescribeFormat.text else format_json(stats)
    typer.echo(output, nl=False)
