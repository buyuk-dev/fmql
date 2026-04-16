from __future__ import annotations

import warnings
from pathlib import Path
from typing import Iterable

from fmq.errors import ParseError
from fmq.packet import Packet
from fmq.parser import parse_file
from fmq.types import PacketId, Resolver, SearchIndex


class Workspace:
    def __init__(
        self,
        root: str | Path,
        *,
        glob: Iterable[str] = ("**/*.md",),
        resolvers: dict[str, Resolver] | None = None,
        search_indexes: dict[str, SearchIndex] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"workspace root does not exist: {self.root}")
        self.glob: tuple[str, ...] = tuple(glob)
        self.packets: dict[PacketId, Packet] = {}
        self.resolvers: dict[str, Resolver] = dict(resolvers or {})
        self.search_indexes: dict[str, SearchIndex] = dict(search_indexes or {})
        self._scan()

    def _scan(self) -> None:
        seen: set[Path] = set()
        for pattern in self.glob:
            for p in self.root.glob(pattern):
                if not p.is_file():
                    continue
                if p in seen:
                    continue
                seen.add(p)
                pid = p.resolve().relative_to(self.root).as_posix()
                try:
                    packet = parse_file(p, pid=pid)
                except ParseError as e:
                    warnings.warn(f"skipped {pid}: {e}", stacklevel=2)
                    continue
                except OSError as e:
                    warnings.warn(f"skipped {pid}: {e}", stacklevel=2)
                    continue
                self.packets[pid] = packet

    def rescan(self) -> None:
        self.packets.clear()
        self._scan()

    def __len__(self) -> int:
        return len(self.packets)

    def __iter__(self):
        return iter(self.packets.values())

    def __contains__(self, pid: object) -> bool:
        return pid in self.packets

    def get(self, pid: PacketId) -> Packet | None:
        return self.packets.get(pid)
