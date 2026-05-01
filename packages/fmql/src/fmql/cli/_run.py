from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import Callable, Optional, Union

import typer

from fmql.edits import EditPlan
from fmql.errors import FmqlError


def parse_depth(depth: str) -> Union[int, str]:
    if depth in ("*", "all"):
        return "*"
    try:
        n = int(depth)
    except ValueError as e:
        raise FmqlError(f"invalid --depth {depth!r}: expected integer or '*'") from e
    if n < 0:
        raise FmqlError(f"invalid --depth {depth!r}: must be non-negative")
    return n


def resolve_workspace(flag: Optional[Path]) -> Path:
    """Pick the workspace root.

    `--workspace/-w` takes precedence; otherwise the current working directory.
    Errors cleanly if the flag points at a missing path or a file (no walk-up).
    """
    if flag is None:
        return Path.cwd().resolve()
    p = flag.expanduser()
    if not p.exists():
        raise FmqlError(f"workspace not found: {p}")
    if not p.is_dir():
        raise FmqlError(f"expected directory, got file: {p}")
    return p.resolve()


def confirm_prompt(msg: str = "Apply these changes? [y/N] ") -> bool:
    try:
        with open("/dev/tty", "r") as tty:
            sys.stderr.write(msg)
            sys.stderr.flush()
            ans = tty.readline().strip().lower()
            return ans in ("y", "yes")
    except OSError:
        sys.stderr.write("error: no terminal for confirmation; use --yes\n")
        return False


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
