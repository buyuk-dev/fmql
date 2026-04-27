from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

import typer

from fmql.filters import type_name
from fmql.resolvers import name_for
from fmql.types import Resolver
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


def emit_resolver_warnings(
    workspace: Workspace,
    fields: Iterable[str],
    resolver: Optional[Resolver] = None,
) -> None:
    seen: set[str] = set()
    for field in fields:
        if field in seen:
            continue
        seen.add(field)
        eff_resolver = resolver or workspace.resolvers.get(field) or workspace.default_resolver
        mismatch = diagnose_field(workspace, field, eff_resolver)
        if mismatch is not None:
            typer.echo(format_warning(mismatch), err=True)


def maybe_emit_warnings(
    workspace: Workspace,
    fields: Iterable[str],
    *,
    diagnose: bool,
    resolver: Optional[Resolver] = None,
) -> None:
    """Emit resolver warnings only when CLI flag or workspace default opts in."""
    if diagnose or workspace.diagnose_default:
        emit_resolver_warnings(workspace, fields, resolver=resolver)
