from __future__ import annotations

import typer

from fmq import __version__
from fmq.cli.cmd_query import query_cmd

app = typer.Typer(
    name="fmq",
    help="FrontMatter Utilities — query and edit directories of frontmatter files.",
    no_args_is_help=True,
)

app.command(name="query", help="Query a workspace of frontmatter files.")(query_cmd)


@app.command(name="version", help="Print fmq version and exit.")
def version_cmd() -> None:
    typer.echo(__version__)


if __name__ == "__main__":
    app()
