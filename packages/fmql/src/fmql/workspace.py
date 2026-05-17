from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Iterable, Optional

from fmql.config import (
    build_resolvers_from_config,
    load_workspace_config,
    read_diagnose_flag,
)
from fmql.edges import iter_body_wikilink_targets, resolve_item
from fmql.errors import ParseError
from fmql.packet import Packet
from fmql.parser import parse_file
from fmql.resolvers import RelativePathResolver
from fmql.types import PacketId, Resolver
from fmql.wikilinks import (
    MENTIONS_FIELD,
    WikilinkTarget,
    parse_body_wikilinks,
)


class Workspace:
    def __init__(
        self,
        root: str | Path,
        *,
        glob: Iterable[str] = ("**/*.md",),
        resolvers: dict[str, Resolver] | None = None,
        default_resolver: Optional[Resolver] = None,
    ) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"workspace root does not exist: {self.root}")
        self.glob: tuple[str, ...] = tuple(glob)
        self.packets: dict[PacketId, Packet] = {}

        file_cfg = load_workspace_config(self.root)
        file_resolvers, file_default = build_resolvers_from_config(file_cfg)
        self.resolvers: dict[str, Resolver] = {**file_resolvers, **(resolvers or {})}
        if default_resolver is None:
            default_resolver = file_default or RelativePathResolver()
        self.default_resolver: Resolver = default_resolver
        self.diagnose_default: bool = read_diagnose_flag(file_cfg)
        self._field_index: dict[str, dict[Any, list[PacketId]]] = {}
        self._stem_index: Optional[dict[str, list[PacketId]]] = None
        self._reverse_cache: dict[tuple[str, int], dict[PacketId, list[PacketId]]] = {}
        self._body_wikilinks: dict[PacketId, list[WikilinkTarget]] = {}
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
                self._body_wikilinks[pid] = parse_body_wikilinks(packet.body)

    def rescan(self) -> None:
        self.packets.clear()
        self._field_index.clear()
        self._stem_index = None
        self._reverse_cache.clear()
        self._body_wikilinks.clear()
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

    def reverse_index(self, field: str, resolver: Resolver) -> dict[PacketId, list[PacketId]]:
        """Lazy reverse adjacency: ``{target_pid: [source_pids]}`` for ``field``.

        Fuses wikilink-derived sources with resolver-derived sources. For
        ``field == "mentions"``, body-wikilink sources contribute in addition
        to frontmatter ``mentions`` items. For any field, frontmatter items
        wholly wrapped in ``[[]]`` resolve as wikilinks; remaining items go
        through ``resolver``. Sources are deduped per target.
        """
        key = (field, id(resolver))
        cached = self._reverse_cache.get(key)
        if cached is not None:
            return cached
        idx: dict[PacketId, list[PacketId]] = {}

        def _add(target: PacketId, src: PacketId) -> None:
            bucket = idx.setdefault(target, [])
            if src not in bucket:
                bucket.append(src)

        for src in sorted(self.packets):
            packet = self.packets[src]
            if field == MENTIONS_FIELD:
                for tgt in iter_body_wikilink_targets(self, src):
                    _add(tgt, src)
            raw = packet.as_plain().get(field)
            if raw is None:
                continue
            items = raw if isinstance(raw, (list, tuple)) else [raw]
            for item in items:
                tgt = resolve_item(self, src, item, resolver)
                if tgt is not None:
                    _add(tgt, src)
        self._reverse_cache[key] = idx
        return idx

    def body_wikilinks(self, pid: PacketId) -> list[WikilinkTarget]:
        """Cached body wikilinks for a packet, populated during scan."""
        return self._body_wikilinks.get(pid, [])
