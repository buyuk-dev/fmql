from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Optional

import typer

from fmql.filters import type_name
from fmql.resolvers import name_for
from fmql.types import PacketId, Resolver
from fmql.wikilinks import (
    MENTIONS_FIELD,
    match_whole_value_wikilink,
    resolve_wikilink,
)
from fmql.workspace import Workspace

_SUGGESTION_BY_KIND: dict[str, str] = {
    "int": "id",
    "float": "id",
    "str": "uuid",
}


@dataclass(frozen=True)
class FieldMismatch:
    field: str
    populated_packets: int
    total_values: int
    resolved_values: int
    sample_unresolved: tuple[Any, ...]
    resolver_name: str
    suggested_resolver: Optional[str]


@dataclass(frozen=True)
class WikilinkDiagnostic:
    kind: Literal["ambiguous", "unresolved"]
    source: PacketId
    field: str
    raw: str
    candidates: tuple[PacketId, ...]


def diagnose_field(workspace: Workspace, field: str, resolver: Resolver) -> Optional[FieldMismatch]:
    populated_packets = 0
    total_values = 0
    resolved_values = 0
    unresolved_samples: list[Any] = []
    first_kind: Optional[str] = None
    kinds_uniform = True
    for pid, packet in workspace.packets.items():
        raw = packet.as_plain().get(field)
        if raw is None:
            continue
        populated_packets += 1
        items = raw if isinstance(raw, (list, tuple)) else [raw]
        for item in items:
            # Wikilink-shaped items are diagnosed by diagnose_wikilinks; they
            # don't contribute to the resolver-mismatch counters at all.
            if match_whole_value_wikilink(item) is not None:
                continue
            total_values += 1
            if resolver.resolve(item, origin=pid, workspace=workspace) is not None:
                resolved_values += 1
                continue
            if len(unresolved_samples) < 3:
                unresolved_samples.append(item)
            kind = type_name(item)
            if first_kind is None:
                first_kind = kind
            elif kind != first_kind:
                kinds_uniform = False

    if populated_packets == 0 or resolved_values == total_values:
        return None

    suggested = _SUGGESTION_BY_KIND.get(first_kind) if kinds_uniform and first_kind else None
    return FieldMismatch(
        field=field,
        populated_packets=populated_packets,
        total_values=total_values,
        resolved_values=resolved_values,
        sample_unresolved=tuple(unresolved_samples),
        resolver_name=name_for(resolver),
        suggested_resolver=suggested,
    )


def diagnose_wikilinks(workspace: Workspace, fields: Iterable[str]) -> list[WikilinkDiagnostic]:
    """Collect ambiguous and unresolved wikilink diagnostics for the given fields.

    For ``field == "mentions"``: scans body wikilinks on every packet.
    For any field: scans frontmatter items wholly wrapped in ``[[]]``.
    """
    seen_fields: set[str] = set()
    out: list[WikilinkDiagnostic] = []

    def _record(src: PacketId, field: str, link) -> None:
        res = resolve_wikilink(link, workspace)
        if not res.candidates:
            out.append(WikilinkDiagnostic("unresolved", src, field, link.raw, ()))
        elif len(res.candidates) > 1:
            out.append(WikilinkDiagnostic("ambiguous", src, field, link.raw, res.candidates))

    for field in fields:
        if field in seen_fields:
            continue
        seen_fields.add(field)
        for src in sorted(workspace.packets):
            packet = workspace.packets[src]
            if field == MENTIONS_FIELD:
                for link in workspace.body_wikilinks(src):
                    _record(src, field, link)
            raw = packet.as_plain().get(field)
            if raw is None:
                continue
            items = raw if isinstance(raw, (list, tuple)) else [raw]
            for item in items:
                link = match_whole_value_wikilink(item)
                if link is not None:
                    _record(src, field, link)
    return out


def format_warning(mismatch: FieldMismatch) -> str:
    unresolved = mismatch.total_values - mismatch.resolved_values
    sample = ", ".join(repr(v) for v in mismatch.sample_unresolved)
    lines = [
        (
            f"warning: field {mismatch.field!r} has {unresolved} unresolved "
            f"value(s) across {mismatch.populated_packets} packet(s)"
        ),
        f"  sample: {sample}",
        f"  bound resolver: {mismatch.resolver_name}",
    ]
    if mismatch.suggested_resolver and mismatch.suggested_resolver != mismatch.resolver_name:
        lines.append("  fix: add to WORKSPACE.md frontmatter:")
        lines.append("    fmql:")
        lines.append("      resolvers:")
        lines.append(f"        {mismatch.field}: {mismatch.suggested_resolver}")
    return "\n".join(lines)


def format_wikilink_warning(d: WikilinkDiagnostic) -> str:
    if d.kind == "unresolved":
        return (
            f"warning: wikilink [[{d.raw}]] in {d.source} " f"(field {d.field!r}) matches no packet"
        )
    chosen, *alternates = d.candidates
    alts = ", ".join(alternates)
    return (
        f"warning: wikilink [[{d.raw}]] in {d.source} "
        f"(field {d.field!r}) is ambiguous; picked {chosen} (alternates: {alts})"
    )


def emit_resolver_warnings(
    workspace: Workspace,
    fields: Iterable[str],
    resolver: Optional[Resolver] = None,
) -> None:
    field_list = list(fields)
    seen: set[str] = set()
    for field in field_list:
        if field in seen:
            continue
        seen.add(field)
        eff_resolver = resolver or workspace.resolvers.get(field) or workspace.default_resolver
        mismatch = diagnose_field(workspace, field, eff_resolver)
        if mismatch is not None:
            typer.echo(format_warning(mismatch), err=True)
    for diagnostic in diagnose_wikilinks(workspace, field_list):
        typer.echo(format_wikilink_warning(diagnostic), err=True)


def maybe_emit_warnings(
    workspace: Workspace,
    fields: Iterable[str],
    *,
    diagnose: bool,
    resolver: Optional[Resolver] = None,
) -> None:
    """Emit resolver + wikilink warnings only when CLI flag or workspace default opts in."""
    if diagnose or workspace.diagnose_default:
        emit_resolver_warnings(workspace, fields, resolver=resolver)
