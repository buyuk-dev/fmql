from __future__ import annotations

import typer

from fmql import __version__
from fmql.cli.cmd_cypher import cypher_cmd
from fmql.cli.cmd_describe import describe_cmd
from fmql.cli.cmd_index import index_cmd, list_backends_cmd, search_cmd
from fmql.cli.cmd_query import query_cmd
from fmql.cli.cmd_subgraph import subgraph_cmd
from fmql.cli.cmd_update import update_cmd

app = typer.Typer(
    name="fmql",
    help="FrontMatter Utilities — query and edit directories of frontmatter files.",
    no_args_is_help=True,
)

app.command(name="query", help="Query a workspace of frontmatter files.")(query_cmd)
app.command(name="describe", help="Describe a workspace of frontmatter files.")(describe_cmd)
app.command(name="cypher", help="Run a Cypher-subset pattern query.")(cypher_cmd)
app.command(name="update", help="Pattern-match and edit packets (MATCH ... [SET|REMOVE]).")(
    update_cmd
)
app.command(name="subgraph", help="Collect a reachability subgraph around seeds.")(subgraph_cmd)
app.command(name="search", help="Search a workspace or index.")(search_cmd)
app.command(name="index", help="Build a search index for a workspace.")(index_cmd)
app.command(name="list-backends", help="List discovered search backends.")(list_backends_cmd)


@app.command(name="version", help="Print fmql version and exit.")
def version_cmd() -> None:
    typer.echo(__version__)


if __name__ == "__main__":
    app()
