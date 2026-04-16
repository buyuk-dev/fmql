from __future__ import annotations

import typer

from fmq import __version__
from fmq.cli.cmd_append import append_cmd
from fmq.cli.cmd_query import query_cmd
from fmq.cli.cmd_remove import remove_cmd
from fmq.cli.cmd_rename import rename_cmd
from fmq.cli.cmd_set import set_cmd
from fmq.cli.cmd_toggle import toggle_cmd

app = typer.Typer(
    name="fmq",
    help="FrontMatter Utilities — query and edit directories of frontmatter files.",
    no_args_is_help=True,
)

app.command(name="query", help="Query a workspace of frontmatter files.")(query_cmd)
app.command(name="set", help="Set frontmatter fields (key=value).")(set_cmd)
app.command(name="remove", help="Remove frontmatter fields.")(remove_cmd)
app.command(name="rename", help="Rename frontmatter fields (old=new).")(rename_cmd)
app.command(name="append", help="Append to list-valued fields (field=value).")(append_cmd)
app.command(name="toggle", help="Toggle boolean fields.")(toggle_cmd)


@app.command(name="version", help="Print fmq version and exit.")
def version_cmd() -> None:
    typer.echo(__version__)


if __name__ == "__main__":
    app()
