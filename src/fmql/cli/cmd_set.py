from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from fmql.cli._coerce import coerce_value, split_assignments
from fmql.cli._edit_common import cli_guard, resolve_targets_and_workspace, run_plan
from fmql.edits import plan_set
from fmql.errors import EditError


@cli_guard
def set_cmd(
    args: list[str] = typer.Argument(None, help="Targets and key=value pairs"),
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
) -> int:
    args = args or []
    targets, raw_assigns = split_assignments(args)
    if not raw_assigns:
        raise EditError("no assignments (expected key=value)")
    ws, pids = resolve_targets_and_workspace(targets, workspace_flag=workspace)
    assignments = {k: coerce_value(v) for k, v in raw_assigns}
    plan = plan_set(ws, pids, **assignments)
    return run_plan(plan, dry_run=dry_run, yes=yes)
