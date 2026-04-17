from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Protocol, runtime_checkable

from fmql.search.types import BackendInfo, IndexStats, SearchHit

if TYPE_CHECKING:
    from fmql.packet import Packet
    from fmql.workspace import Workspace


@runtime_checkable
class ScanSearch(Protocol):
    """Backend that scans the workspace at query time. No build step."""

    name: str

    def query(
        self,
        text: str,
        workspace: "Workspace",
        *,
        k: int = 10,
        options: dict | None = None,
    ) -> list[SearchHit]: ...

    def info(self) -> BackendInfo: ...


@runtime_checkable
class IndexedSearch(Protocol):
    """Backend that builds a persistent index."""

    name: str

    def parse_location(self, location: str) -> object:
        """Validate and normalise an index location string. Raises ValueError."""

    def default_location(self, workspace: "Workspace") -> str | None:
        """Suggested default location, or None if --out is required."""

    def build(
        self,
        packets: Iterable["Packet"],
        location: str,
        *,
        options: dict | None = None,
    ) -> IndexStats: ...

    def query(
        self,
        text: str,
        location: str,
        *,
        k: int = 10,
        options: dict | None = None,
    ) -> list[SearchHit]: ...

    def info(self, location: str | None = None) -> BackendInfo:
        """Must not raise on missing/unreadable indexes — return what it can."""
