"""Shared forward + reverse edge enumeration.

Single source of truth used by ``traversal``, ``subgraph``, and
``cypher/executor``. Honors two edge sources:

- Body wikilinks (``[[Note]]`` / ``[[Note|alias]]``) for the special field
  name ``"mentions"``.
- Frontmatter values: items whose whole-value matches ``[[X]]`` resolve as
  wikilinks; all other items go through the configured resolver. The two paths
  are mutually exclusive per item, so the ``[[]]`` form wins for that item and
  the resolver is not called for it.

Targets are deduped per call so a body + frontmatter overlap (or a duplicated
wikilink) yields a single edge.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator, Optional

from fmql.types import PacketId, Resolver
from fmql.wikilinks import MENTIONS_FIELD, match_whole_value_wikilink, resolve_wikilink

if TYPE_CHECKING:
    from fmql.workspace import Workspace


def _iter_raw(raw: Any) -> Iterator[Any]:
    if raw is None:
        return
    if isinstance(raw, (list, tuple)):
        yield from raw
    else:
        yield raw


def iter_body_wikilink_targets(workspace: "Workspace", pid: PacketId) -> Iterator[PacketId]:
    """Resolved body-wikilink targets for a packet, dropping danglers."""
    for link in workspace.body_wikilinks(pid):
        tgt = resolve_wikilink(link, workspace).target
        if tgt is not None:
            yield tgt


def resolve_item(
    workspace: "Workspace",
    src: PacketId,
    item: Any,
    resolver: Resolver,
) -> Optional[PacketId]:
    """Resolve a single frontmatter item to a target pid.

    Wikilink-shaped items (whole value wrapped in ``[[]]``) win over the
    resolver: the resolver is not called for them.
    """
    link = match_whole_value_wikilink(item)
    if link is not None:
        return resolve_wikilink(link, workspace).target
    return resolver.resolve(item, origin=src, workspace=workspace)


def iter_forward_targets(
    workspace: "Workspace",
    pid: PacketId,
    field: str,
    resolver: Resolver,
) -> Iterator[PacketId]:
    packet = workspace.packets.get(pid)
    if packet is None:
        return

    seen: set[PacketId] = set()

    if field == MENTIONS_FIELD:
        for tgt in iter_body_wikilink_targets(workspace, pid):
            if tgt not in seen:
                seen.add(tgt)
                yield tgt

    raw = packet.as_plain().get(field)
    for item in _iter_raw(raw):
        tgt = resolve_item(workspace, pid, item, resolver)
        if tgt is not None and tgt not in seen:
            seen.add(tgt)
            yield tgt


def iter_reverse_sources(
    workspace: "Workspace",
    pid: PacketId,
    field: str,
    resolver: Resolver,
) -> Iterator[PacketId]:
    yield from workspace.reverse_index(field, resolver).get(pid, ())
