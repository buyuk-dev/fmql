from __future__ import annotations

from dataclasses import dataclass, field

from fmql.types import PacketId


@dataclass(frozen=True)
class SearchHit:
    packet_id: PacketId
    score: float
    snippet: str | None = None


@dataclass(frozen=True)
class IndexStats:
    packets_indexed: int
    packets_skipped: int
    packets_removed: int
    elapsed_seconds: float


@dataclass(frozen=True)
class BackendInfo:
    name: str
    version: str
    kind: str
    metadata: dict = field(default_factory=dict)
