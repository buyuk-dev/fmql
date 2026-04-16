from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from fm.cli._edit_common import cli_guard, resolve_targets_and_workspace, run_plan
from fm.edits import plan_remove
from fm.errors import EditError


@cli_guard
def remove_cmd(
    args: list[str] = typer.Argument(None, help="Targets then field names"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
) -> int:
    args = args or []
    # Targets: existing files, directories, or '-'. Fields: everything else.
    targets: list[str] = []
    fields: list[str] = []
    for tok in args:
        if tok == "-":
            targets.append(tok)
            continue
        p = Path(tok)
        if p.exists():
            targets.append(tok)
        else:
            fields.append(tok)
    if not fields:
        raise EditError("no fields to remove")
    ws, pids = resolve_targets_and_workspace(targets, workspace_flag=workspace)
    plan = plan_remove(ws, pids, *fields)
    return run_plan(plan, dry_run=dry_run, yes=yes)
