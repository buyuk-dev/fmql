from typing import TYPE_CHECKING, Any, Iterable, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from fm.workspace import Workspace

PacketId = str


@runtime_checkable
class Resolver(Protocol):
    def resolve(
        self, raw: Any, *, origin: PacketId, workspace: "Workspace"
    ) -> Optional[PacketId]: ...


@runtime_checkable
class SearchIndex(Protocol):
    name: str

    def search(self, query: str) -> Iterable[PacketId]: ...
