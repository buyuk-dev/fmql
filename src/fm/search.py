from __future__ import annotations

import io
from typing import Iterable, Iterator

from ruamel.yaml import YAML

from fm.types import PacketId, SearchIndex
from fm.workspace import Workspace


class TextScanIndex:
    name = "text"

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self._yaml = YAML(typ="safe", pure=True)
        self._yaml.default_flow_style = False

    def search(self, query: str) -> Iterator[PacketId]:
        q = query.lower()
        if not q:
            return
        for pid in sorted(self.workspace.packets):
            packet = self.workspace.packets[pid]
            if q in packet.body.lower():
                yield pid
                continue
            if q in self._dump_frontmatter(packet.as_plain()).lower():
                yield pid

    def _dump_frontmatter(self, data: dict) -> str:
        if not data:
            return ""
        buf = io.StringIO()
        try:
            self._yaml.dump(data, buf)
        except Exception:
            return repr(data)
        return buf.getvalue()


def get_or_create_text_index(workspace: Workspace) -> SearchIndex:
    existing = workspace.search_indexes.get("text")
    if existing is not None:
        return existing
    idx = TextScanIndex(workspace)
    workspace.search_indexes["text"] = idx
    return idx


def iter_search(workspace: Workspace, index_name: str, query: str) -> Iterable[PacketId]:
    if index_name == "text" and "text" not in workspace.search_indexes:
        get_or_create_text_index(workspace)
    index = workspace.search_indexes.get(index_name)
    if index is None:
        from fm.errors import QueryError

        raise QueryError(f"unknown search index: {index_name!r}")
    return index.search(query)
