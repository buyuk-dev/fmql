from __future__ import annotations

from typing import Optional

from fmql.types import Resolver
from fmql.workspace import Workspace


def diagnose_resolver_mismatch(
    workspace: Workspace, field: str, resolver: Resolver
) -> Optional[str]:
    populated = 0
    resolved = 0
    for pid, packet in workspace.packets.items():
        raw = packet.as_plain().get(field)
        if raw is None:
            continue
        populated += 1
        items = raw if isinstance(raw, (list, tuple)) else [raw]
        for item in items:
            if resolver.resolve(item, origin=pid, workspace=workspace) is not None:
                resolved += 1
                break
    if populated > 0 and resolved == 0:
        return (
            f"hint: field {field!r} is set on {populated} packet(s) but no values resolve; "
            f"possible resolver mismatch (try --resolver uuid|slug|path)"
        )
    return None
