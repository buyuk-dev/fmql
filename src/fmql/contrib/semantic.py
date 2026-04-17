"""Placeholder for the `fmql[semantic]` search index.

The concrete backend (sentence-transformers + vector store) is deferred past
Phase E; see docs/implementation_plan.md §9.
"""

from __future__ import annotations

from typing import Iterable

from fmql.types import PacketId
from fmql.workspace import Workspace


class SemanticIndex:
    name = "semantic"

    def __init__(self, workspace: Workspace) -> None:
        raise NotImplementedError(
            "fmql.contrib.semantic.SemanticIndex is not yet implemented. "
            "Install deps and wire up a real backend (see docs/implementation_plan.md §9)."
        )

    def search(self, query: str) -> Iterable[PacketId]:  # pragma: no cover
        raise NotImplementedError
