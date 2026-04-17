from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from fmql.search.types import BackendInfo, SearchHit

if TYPE_CHECKING:
    from fmql.workspace import Workspace

_ALLOWED_OPTIONS = frozenset({"regex", "case_sensitive"})


class GrepBackend:
    """Scan-based text search. No index, no build step."""

    name = "grep"

    def __init__(self) -> None:
        self._yaml = YAML(typ="safe", pure=True)
        self._yaml.default_flow_style = False

    def query(
        self,
        text: str,
        workspace: "Workspace",
        *,
        k: int = 10,
        options: dict | None = None,
    ) -> list[SearchHit]:
        options = options or {}
        unknown = set(options) - _ALLOWED_OPTIONS
        if unknown:
            raise ValueError(
                f"unknown grep options: {sorted(unknown)}. " f"Allowed: {sorted(_ALLOWED_OPTIONS)}."
            )
        if not text:
            return []

        use_regex = bool(options.get("regex", False))
        case_sensitive = bool(options.get("case_sensitive", False))

        if use_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                matcher = re.compile(text, flags)
            except re.error as e:
                raise ValueError(f"invalid regex {text!r}: {e}") from e
            predicate = lambda s: matcher.search(s) is not None  # noqa: E731
        else:
            needle = text if case_sensitive else text.lower()

            def predicate(s: str) -> bool:
                haystack = s if case_sensitive else s.lower()
                return needle in haystack

        hits: list[SearchHit] = []
        for pid in sorted(workspace.packets):
            packet = workspace.packets[pid]
            body = packet.body
            if predicate(body):
                hits.append(SearchHit(packet_id=pid, score=1.0))
                if len(hits) >= k:
                    break
                continue
            fm = self._dump_frontmatter(packet.as_plain())
            if predicate(fm):
                hits.append(SearchHit(packet_id=pid, score=1.0))
                if len(hits) >= k:
                    break
        return hits

    def info(self) -> BackendInfo:
        from fmql import __version__

        return BackendInfo(name=self.name, version=__version__, kind="scan")

    def _dump_frontmatter(self, data: dict) -> str:
        if not data:
            return ""
        buf = io.StringIO()
        try:
            self._yaml.dump(data, buf)
        except Exception:
            return repr(data)
        return buf.getvalue()
