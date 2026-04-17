from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from fmql.workspace import Workspace

PacketId = str


@runtime_checkable
class Resolver(Protocol):
    def resolve(
        self, raw: Any, *, origin: PacketId, workspace: "Workspace"
    ) -> Optional[PacketId]: ...
