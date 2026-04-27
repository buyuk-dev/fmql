from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Optional

from fmql.errors import FmqlError
from fmql.types import PacketId, Resolver


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


def _id_candidates(raw: Any) -> Iterator[Any]:
    yield raw
    if isinstance(raw, str):
        try:
            yield int(raw)
        except (TypeError, ValueError):
            return
    else:
        yield str(raw)


class IdResolver:
    """Looks up by frontmatter `id` field; accepts int or str, with str/int cross-coercion."""

    def __init__(self, field: str = "id") -> None:
        self.field = field

    def resolve(
        self, raw: Any, *, origin: PacketId, workspace: "Workspace"  # type: ignore[name-defined]  # noqa: F821
    ) -> Optional[PacketId]:
        if raw is None or isinstance(raw, (list, tuple, dict, bool)):
            return None
        idx = workspace.index_by_field(self.field)
        for candidate in _id_candidates(raw):
            hit = idx.get(candidate)
            if hit:
                return hit[0]
        return None


_BY_NAME: dict[str, type] = {
    "path": RelativePathResolver,
    "uuid": UuidResolver,
    "slug": SlugResolver,
    "id": IdResolver,
}

_NAME_BY_CLASS: dict[type, str] = {cls: name for name, cls in _BY_NAME.items()}


def resolver_by_name(name: str) -> Resolver:
    try:
        return _BY_NAME[name]()
    except KeyError as e:
        raise FmqlError(f"unknown resolver: {name!r}") from e


def name_for(resolver: Resolver) -> str:
    """Public name of a resolver instance (e.g. "uuid"); falls back to class name."""
    return _NAME_BY_CLASS.get(type(resolver), type(resolver).__name__)
