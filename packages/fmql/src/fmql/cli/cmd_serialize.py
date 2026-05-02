from __future__ import annotations

import sys
from pathlib import Path

import typer

from fmql.document_io import (
    SerializeFormat,
    deserialize_to_markdown,
    serialize_packet_to,
)
from fmql.errors import FmqlError
from fmql.parser import parse_file


def serialize_cmd(
    path: Path = typer.Argument(..., help="Markdown file to serialize."),
    fmt: SerializeFormat = typer.Option(
        SerializeFormat.json,
        "--format",
        "-f",
        help="Output format: json (default) | yaml.",
    ),
) -> None:
    try:
        packet = parse_file(path)
        output = serialize_packet_to(packet, fmt=fmt)
    except (FmqlError, OSError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2)
    typer.echo(output, nl=False)


def deserialize_cmd(
    fmt: SerializeFormat = typer.Option(
        SerializeFormat.json,
        "--format",
        "-f",
        help="Input format: json (default) | yaml.",
    ),
) -> None:
    text = sys.stdin.read()
    try:
        output = deserialize_to_markdown(text, fmt=fmt)
    except FmqlError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2)
    typer.echo(output, nl=False)
