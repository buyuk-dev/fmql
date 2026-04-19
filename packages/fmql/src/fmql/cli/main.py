from __future__ import annotations

import typer

from fmql import __version__
from fmql.cli.cmd_append import append_cmd
from fmql.cli.cmd_cypher import cypher_cmd
from fmql.cli.cmd_describe import describe_cmd
from fmql.cli.cmd_index import index_cmd, list_backends_cmd, search_cmd
from fmql.cli.cmd_query import query_cmd
from fmql.cli.cmd_remove import remove_cmd
from fmql.cli.cmd_rename import rename_cmd
from fmql.cli.cmd_set import set_cmd
from fmql.cli.cmd_subgraph import subgraph_cmd
from fmql.cli.cmd_toggle import toggle_cmd

app = typer.Typer(
    name="fmql",
    help="FrontMatter Utilities — query and edit directories of frontmatter files.",
    no_args_is_help=True,
)

app.command(name="query", help="Query a workspace of frontmatter files.")(query_cmd)
app.command(name="set", help="Set frontmatter fields (key=value).")(set_cmd)
app.command(name="remove", help="Remove frontmatter fields.")(remove_cmd)
app.command(name="rename", help="Rename frontmatter fields (old=new).")(rename_cmd)
app.command(name="append", help="Append to list-valued fields (field=value).")(append_cmd)
app.command(name="toggle", help="Toggle boolean fields.")(toggle_cmd)
app.command(name="describe", help="Describe a workspace of frontmatter files.")(describe_cmd)
app.command(name="cypher", help="Run a Cypher-subset pattern query.")(cypher_cmd)
app.command(name="subgraph", help="Collect a reachability subgraph around seeds.")(subgraph_cmd)
app.command(name="search", help="Search a workspace or index.")(search_cmd)
app.command(name="index", help="Build a search index for a workspace.")(index_cmd)
app.command(name="list-backends", help="List discovered search backends.")(list_backends_cmd)


@app.command(name="version", help="Print fmql version and exit.")
def version_cmd() -> None:
    typer.echo(__version__)


if __name__ == "__main__":
    app()
