"""Placeholder for the `fmq[sqlite]` FTS5-backed search index.

The concrete backend is deferred past Phase E; see docs/implementation_plan.md §9.
"""

from __future__ import annotations

from typing import Iterable

from fmq.types import PacketId
from fmq.workspace import Workspace


class SqliteFtsIndex:
    name = "sqlite"

    def __init__(self, workspace: Workspace) -> None:
        raise NotImplementedError(
            "fmq.contrib.sqlite.SqliteFtsIndex is not yet implemented. "
            "Install deps and wire up a real backend (see docs/implementation_plan.md §9)."
        )

    def search(self, query: str) -> Iterable[PacketId]:  # pragma: no cover
        raise NotImplementedError
