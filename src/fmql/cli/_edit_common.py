from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import Callable, Optional

import typer

from fmql.cli.stdin import StdinResult, confirm_prompt, read_stdin_targets
from fmql.edits import EditPlan
from fmql.errors import EditError, FmqlError
from fmql.types import PacketId
from fmql.workspace import Workspace


def _compute_lcp(paths: list[Path]) -> Optional[Path]:
    import os

    if not paths:
        return None
    if len(paths) == 1:
        p = paths[0]
        return p.parent if p.is_file() else p
    common = Path(os.path.commonpath([str(p) for p in paths]))
    return common.parent if common.is_file() else common


def resolve_targets_and_workspace(
    positional_tokens: list[str],
    *,
    workspace_flag: Optional[Path],
) -> tuple[Workspace, list[PacketId]]:
    """Turn mixed positionals (paths + literal '-') into a (workspace, pids) pair.

    Rules:
    - If '-' appears in positionals, or stdin is piped and no file positionals are
      given, read stdin. stdin can emit either newline-separated paths or JSONL.
    - Workspace precedence: --workspace > a directory positional > LCP of files
      (positional files only, not stdin — stdin paths may be workspace-relative).
    - Stdin paths: if workspace is known, try resolving them against it first,
      else fall back to CWD.
    - JSONL mode requires an explicit workspace (--workspace or dir positional).
    """
    stdin_result: Optional[StdinResult] = None
    pos_paths: list[Path] = []
    has_stdin_token = False
    for tok in positional_tokens:
        if tok == "-":
            has_stdin_token = True
        else:
            pos_paths.append(Path(tok))

    stdin_is_pipe = not sys.stdin.isatty()
    read_from_stdin = has_stdin_token or (stdin_is_pipe and not pos_paths)
    if read_from_stdin:
        try:
            stdin_result = read_stdin_targets()
        except ValueError as e:
            raise EditError(str(e)) from e

    explicit_ws: Optional[Path] = None
    if workspace_flag is not None:
        explicit_ws = workspace_flag.resolve()

    dir_positionals = [p for p in pos_paths if p.exists() and p.is_dir()]
    file_positionals = [p for p in pos_paths if p.is_file() or not p.exists()]

    if explicit_ws is None and dir_positionals:
        explicit_ws = dir_positionals[0].resolve()

    positional_files_abs: list[Path] = [p.resolve() for p in file_positionals]

    ws_root: Optional[Path] = explicit_ws
    if ws_root is None:
        if positional_files_abs:
            root = _compute_lcp(positional_files_abs)
            if root is None or len(root.parts) < 2:
                raise EditError("paths span unrelated roots; pass --workspace")
            ws_root = root

    if ws_root is None and stdin_result is not None and stdin_result.mode == "paths":
        stdin_abs = [Path(s).resolve() for s in stdin_result.raw_paths]
        if stdin_abs:
            root = _compute_lcp(stdin_abs)
            if root is None or len(root.parts) < 2:
                raise EditError("paths span unrelated roots; pass --workspace")
            ws_root = root

    if ws_root is None:
        if stdin_result is not None and stdin_result.mode == "jsonl":
            raise EditError("JSONL stdin requires --workspace or a directory argument")
        raise EditError("no workspace (pass --workspace or a directory argument)")

    ws = Workspace(ws_root)

    pids: list[PacketId] = []

    for p in positional_files_abs:
        try:
            pid = p.resolve().relative_to(ws.root).as_posix()
        except ValueError as e:
            raise EditError(f"path not inside workspace {ws.root}: {p}") from e
        if pid not in ws.packets:
            raise EditError(f"file not in workspace scan: {pid}")
        pids.append(pid)

    if stdin_result is not None:
        if stdin_result.mode == "empty" and not positional_files_abs:
            raise EditError("no targets (stdin empty, no file arguments)")
        if stdin_result.mode == "jsonl":
            for pid in stdin_result.pids:
                if pid not in ws.packets:
                    raise EditError(f"packet id not in workspace: {pid}")
                pids.append(pid)
        elif stdin_result.mode == "paths":
            for raw in stdin_result.raw_paths:
                pid = _resolve_stdin_path(raw, ws)
                if pid not in ws.packets:
                    raise EditError(f"stdin path not in workspace: {raw}")
                pids.append(pid)

    if not pids:
        raise EditError("no target files")

    seen: set[str] = set()
    unique: list[PacketId] = []
    for pid in pids:
        if pid not in seen:
            seen.add(pid)
            unique.append(pid)
    return ws, unique


def _resolve_stdin_path(raw: str, ws: Workspace) -> PacketId:
    """Resolve a raw stdin path to a workspace-relative PacketId.

    Try (a) workspace-relative first (covers `fmql query` output), then
    (b) absolute or CWD-relative resolution.
    """
    # (a) workspace-relative
    ws_candidate = (ws.root / raw).resolve()
    if ws_candidate.is_file():
        try:
            return ws_candidate.relative_to(ws.root).as_posix()
        except ValueError:
            pass
    # (b) absolute / CWD-relative
    p = Path(raw).resolve()
    try:
        return p.relative_to(ws.root).as_posix()
    except ValueError:
        raise EditError(f"stdin path not inside workspace {ws.root}: {raw}")


def run_plan(plan: EditPlan, *, dry_run: bool, yes: bool) -> int:
    """Render preview/apply and return an exit code.

    Exit codes:
      0 — applied (or dry-run rendered).
      1 — all files errored; nothing written.
      2 — user aborted at confirm.
    """
    errors_text = plan.preview_errors()
    diff_text = plan.preview_diff()
    summary = plan.summary()

    if errors_text:
        typer.echo(errors_text, nl=False, err=True)

    if dry_run:
        if diff_text:
            typer.echo(diff_text, nl=False)
        typer.echo(summary, err=True)
        return 0

    if not plan.has_changes():
        if diff_text:
            typer.echo(diff_text, nl=False)
        typer.echo(summary, err=True)
        has_errors = any(c.error is not None for c in plan.compile())
        return 1 if has_errors else 0

    confirm = not yes

    def _confirm_fn(msg: str) -> bool:
        return confirm_prompt(msg)

    report = plan.apply(
        confirm=confirm,
        confirm_fn=_confirm_fn if confirm else None,
        preview_out=(lambda t: typer.echo(t, nl=False)) if confirm else None,
    )
    if report.aborted:
        typer.echo("aborted.", err=True)
        return 2
    typer.echo(plan.summary(), err=True)
    if report.errors and not report.written:
        return 1
    return 0


def cli_guard(func: Callable[..., int]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> None:
        try:
            code = func(*args, **kwargs)
        except FmqlError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=2)
        if code != 0:
            raise typer.Exit(code=code)

    return wrapper
