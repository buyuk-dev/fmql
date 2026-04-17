from __future__ import annotations

import dataclasses
import json
import os
import time
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from fmql.cli._coerce import coerce_value
from fmql.errors import FmqlError
from fmql.packet import Packet
from fmql.qlang import compile_query
from fmql.search import (
    BackendInfo,
    BackendKindError,
    BackendNotFoundError,
    IndexStats,
    SearchHit,
    discover_backends,
    get_backend,
    is_indexed,
    is_scan,
)
from fmql.workspace import Workspace


class StatsFormat(str, Enum):
    text = "text"
    json = "json"


class HitsFormat(str, Enum):
    paths = "paths"
    json = "json"
    rows = "rows"


def _parse_options(pairs: Optional[list[str]]) -> dict:
    out: dict = {}
    if not pairs:
        return out
    for item in pairs:
        if "=" not in item:
            raise FmqlError(f"invalid --option {item!r}: expected KEY=VALUE")
        k, _, v = item.partition("=")
        k = k.strip()
        if not k:
            raise FmqlError(f"invalid --option {item!r}: empty key")
        out[k] = coerce_value(v)
    return out


def _emit_hits(hits: list[SearchHit], fmt: HitsFormat) -> None:
    if fmt is HitsFormat.paths:
        for h in hits:
            typer.echo(h.packet_id)
        return
    if fmt is HitsFormat.rows:
        for h in hits:
            snip = (h.snippet or "").replace("\t", " ").replace("\n", " ")
            typer.echo(f"{h.packet_id}\t{h.score:.6f}\t{snip}")
        return
    for h in hits:
        typer.echo(
            json.dumps(
                {"id": h.packet_id, "score": h.score, "snippet": h.snippet},
                ensure_ascii=False,
            )
        )


def _handle_cli_error(e: BaseException) -> None:
    if os.environ.get("FMQL_DEBUG"):
        raise e
    typer.echo(f"error: {e}", err=True)
    raise typer.Exit(code=2)


def index_cmd(
    workspace: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Workspace to index.",
    ),
    backend: str = typer.Option(
        ..., "--backend", help="Backend name (must be an indexed backend)."
    ),
    out: Optional[str] = typer.Option(None, "--out", help="Index location (backend-defined)."),
    filter_query: Optional[str] = typer.Option(
        None, "--filter", help="qlang expression restricting which packets are indexed."
    ),
    field: Optional[list[str]] = typer.Option(
        None, "--field", help="Field to embed. Repeatable. Backend-defined default."
    ),
    force: bool = typer.Option(False, "--force", help="Rebuild from scratch."),
    option: Optional[list[str]] = typer.Option(
        None, "--option", help="Backend-specific option (KEY=VALUE). Repeatable."
    ),
    fmt: StatsFormat = typer.Option(
        StatsFormat.text, "--format", "-f", help="Stats output format."
    ),
) -> None:
    """Build an index for WORKSPACE using BACKEND."""
    try:
        be = get_backend(backend)
        if is_scan(be):
            raise BackendKindError(
                f"backend {backend!r} is a scan backend; nothing to build. "
                f"Use `fmql search --backend {backend} ...` instead."
            )
        opts = _parse_options(option)
        if field:
            opts.setdefault("fields", list(field))
        if force:
            opts.setdefault("force", True)

        ws = Workspace(workspace)
        if filter_query is not None:
            q = compile_query(filter_query, ws)
            pids = set(q.ids())
            packets: list[Packet] = [ws.packets[pid] for pid in sorted(pids)]
        else:
            packets = [ws.packets[pid] for pid in sorted(ws.packets)]

        location = out or be.default_location(ws)
        if location is None:
            raise BackendKindError(
                f"backend {backend!r} has no default location; pass --out explicitly"
            )
        be.parse_location(location)
        start = time.monotonic()
        stats = be.build(packets, location, options=opts)
        elapsed = time.monotonic() - start

        if fmt is StatsFormat.json:
            payload = _stats_to_dict(stats)
            payload["elapsed_seconds"] = payload.get("elapsed_seconds") or elapsed
            payload["location"] = str(location)
            typer.echo(json.dumps(payload, ensure_ascii=False))
        else:
            typer.echo(f"indexed {stats.packets_indexed} packet(s)")
            typer.echo(f"skipped {stats.packets_skipped} packet(s)")
            typer.echo(f"removed {stats.packets_removed} packet(s)")
            typer.echo(f"elapsed {stats.elapsed_seconds or elapsed:.3f}s")
            typer.echo(f"location {location}")
    except FmqlError as e:
        _handle_cli_error(e)
    except ValueError as e:
        _handle_cli_error(FmqlError(str(e)))


def _stats_to_dict(stats: IndexStats) -> dict:
    return dataclasses.asdict(stats)


def _info_to_dict(info: BackendInfo) -> dict:
    return dataclasses.asdict(info)


def list_backends_cmd(
    fmt: StatsFormat = typer.Option(StatsFormat.text, "--format", "-f", help="Output format."),
) -> None:
    backends = discover_backends()
    if fmt is StatsFormat.json:
        rows = []
        for name in sorted(backends):
            entry: dict = {"name": name, "class": _qualname(backends[name])}
            try:
                instance = backends[name]()
                info = instance.info() if not is_indexed(instance) else instance.info(None)
                entry["loaded"] = True
                entry["kind"] = info.kind
                entry["version"] = info.version
            except Exception as e:
                entry["loaded"] = False
                entry["error"] = f"{type(e).__name__}: {e}"
            rows.append(entry)
        typer.echo(json.dumps(rows, ensure_ascii=False))
        return
    if not backends:
        typer.echo("(no backends registered)")
        return
    for name in sorted(backends):
        cls = backends[name]
        try:
            instance = cls()
            info = instance.info() if not is_indexed(instance) else instance.info(None)
            typer.echo(f"{name}\t{info.kind}\t{info.version}\t{_qualname(cls)}")
        except Exception as e:
            typer.echo(f"{name}\t(unloadable: {type(e).__name__}: {e})\t{_qualname(cls)}")


def _qualname(cls: type) -> str:
    return f"{cls.__module__}:{cls.__qualname__}"


def search_cmd(
    query: str = typer.Argument(..., help="Search query string."),
    backend: str = typer.Option("grep", "--backend", help="Backend name. Default: grep."),
    workspace: Optional[Path] = typer.Option(
        None,
        "--workspace",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Workspace (required for scan backends or to derive default index location).",
    ),
    index_location: Optional[str] = typer.Option(
        None, "--index", help="Explicit index location (for indexed backends)."
    ),
    k: int = typer.Option(10, "-k", help="Max results. Default: 10."),
    fmt: HitsFormat = typer.Option(HitsFormat.paths, "--format", "-f", help="Output format."),
    option: Optional[list[str]] = typer.Option(
        None, "--option", help="Backend-specific option (KEY=VALUE). Repeatable."
    ),
) -> None:
    """Search a workspace or index using BACKEND."""
    try:
        be = get_backend(backend)
        opts = _parse_options(option)
        if is_indexed(be):
            location = index_location
            if location is None and workspace is not None:
                ws = Workspace(workspace)
                location = be.default_location(ws)
            if location is None:
                raise BackendKindError(
                    f"backend {backend!r} is indexed; pass --index LOCATION "
                    f"or --workspace (for the backend to derive a default location)"
                )
            hits = be.query(query, location, k=k, options=opts)
        else:
            if workspace is None:
                raise BackendKindError(
                    f"backend {backend!r} is a scan backend; --workspace is required"
                )
            ws = Workspace(workspace)
            hits = be.query(query, ws, k=k, options=opts)
        _emit_hits(hits, fmt)
    except BackendNotFoundError as e:
        _handle_cli_error(e)
    except FmqlError as e:
        _handle_cli_error(e)
    except ValueError as e:
        _handle_cli_error(FmqlError(str(e)))
