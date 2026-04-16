from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fmq.errors import FmqError
from fmq.types import PacketId, Resolver


class RelativePathResolver:
    """Default resolver. Treats raw as a workspace-relative path from origin's directory."""

    def resolve(
        self, raw: Any, *, origin: PacketId, workspace: "Workspace"  # type: ignore[name-defined]  # noqa: F821
    ) -> Optional[PacketId]:
        if not isinstance(raw, str):
            return None
        candidate = (workspace.root / Path(origin).parent / raw).resolve()
        try:
            pid = candidate.relative_to(workspace.root).as_posix()
        except ValueError:
            return None
        return pid if pid in workspace.packets else None


class UuidResolver:
    """Looks up a packet by a frontmatter field (default: `uuid`)."""

    def __init__(self, field: str = "uuid") -> None:
        self.field = field

    def resolve(
        self, raw: Any, *, origin: PacketId, workspace: "Workspace"  # type: ignore[name-defined]  # noqa: F821
    ) -> Optional[PacketId]:
        if not isinstance(raw, str):
            return None
        ids = workspace.index_by_field(self.field).get(raw)
        return ids[0] if ids else None


class SlugResolver:
    """Looks up by frontmatter `slug` field, falling back to file stem."""

    def __init__(self, field: str = "slug") -> None:
        self.field = field

    def resolve(
        self, raw: Any, *, origin: PacketId, workspace: "Workspace"  # type: ignore[name-defined]  # noqa: F821
    ) -> Optional[PacketId]:
        if not isinstance(raw, str):
            return None
        idx = workspace.index_by_field(self.field)
        if raw in idx:
            return idx[raw][0]
        stem = workspace.index_by_stem().get(raw)
        return stem[0] if stem else None


_BY_NAME: dict[str, type] = {
    "path": RelativePathResolver,
    "uuid": UuidResolver,
    "slug": SlugResolver,
}


def resolver_by_name(name: str) -> Resolver:
    try:
        return _BY_NAME[name]()
    except KeyError as e:
        raise FmqError(f"unknown resolver: {name!r}") from e
