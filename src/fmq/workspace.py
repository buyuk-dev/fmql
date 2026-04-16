from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Iterable, Optional

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
        default_resolver: Optional[Resolver] = None,
        search_indexes: dict[str, SearchIndex] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"workspace root does not exist: {self.root}")
        self.glob: tuple[str, ...] = tuple(glob)
        self.packets: dict[PacketId, Packet] = {}
        self.resolvers: dict[str, Resolver] = dict(resolvers or {})
        self.search_indexes: dict[str, SearchIndex] = dict(search_indexes or {})
        if default_resolver is None:
            from fmq.resolvers import RelativePathResolver

            default_resolver = RelativePathResolver()
        self.default_resolver: Resolver = default_resolver
        self._field_index: dict[str, dict[Any, list[PacketId]]] = {}
        self._stem_index: Optional[dict[str, list[PacketId]]] = None
        self._reverse_cache: dict[
            tuple[str, int], dict[PacketId, list[PacketId]]
        ] = {}
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
        self._field_index.clear()
        self._stem_index = None
        self._reverse_cache.clear()
        self._scan()

    def __len__(self) -> int:
        return len(self.packets)

    def __iter__(self):
        return iter(self.packets.values())

    def __contains__(self, pid: object) -> bool:
        return pid in self.packets

    def get(self, pid: PacketId) -> Packet | None:
        return self.packets.get(pid)

    def index_by_field(self, field: str) -> dict[Any, list[PacketId]]:
        """Lazy index of {field_value: [packet_ids]}. Scalar values only."""
        cached = self._field_index.get(field)
        if cached is not None:
            return cached
        idx: dict[Any, list[PacketId]] = {}
        for pid in sorted(self.packets):
            packet = self.packets[pid]
            plain = packet.as_plain()
            if field not in plain:
                continue
            value = plain[field]
            if isinstance(value, (list, tuple, dict)):
                continue
            try:
                idx.setdefault(value, []).append(pid)
            except TypeError:
                continue
        self._field_index[field] = idx
        return idx

    def index_by_stem(self) -> dict[str, list[PacketId]]:
        """Lazy index of {Path(pid).stem: [packet_ids]}."""
        if self._stem_index is not None:
            return self._stem_index
        idx: dict[str, list[PacketId]] = {}
        for pid in sorted(self.packets):
            stem = Path(pid).stem
            idx.setdefault(stem, []).append(pid)
        self._stem_index = idx
        return idx

    def reverse_index(
        self, field: str, resolver: Resolver
    ) -> dict[PacketId, list[PacketId]]:
        """Lazy reverse adjacency: {target_pid: [source_pids]} for `field` via `resolver`."""
        key = (field, id(resolver))
        cached = self._reverse_cache.get(key)
        if cached is not None:
            return cached
        idx: dict[PacketId, list[PacketId]] = {}
        for src in sorted(self.packets):
            packet = self.packets[src]
            raw = packet.as_plain().get(field)
            if raw is None:
                continue
            items = raw if isinstance(raw, (list, tuple)) else [raw]
            for item in items:
                tgt = resolver.resolve(item, origin=src, workspace=self)
                if tgt is None:
                    continue
                bucket = idx.setdefault(tgt, [])
                if src not in bucket:
                    bucket.append(src)
        self._reverse_cache[key] = idx
        return idx
