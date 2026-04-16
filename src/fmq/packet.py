from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from fmq.types import PacketId


@dataclass
class Packet:
    id: PacketId
    abspath: Path
    frontmatter: CommentedMap
    body: str
    raw_prefix: str
    fence_style: tuple[str, str]
    eol: str
    newline_at_eof: bool
    has_frontmatter: bool

    def as_plain(self) -> dict[str, Any]:
        return _to_plain(self.frontmatter)


def _to_plain(value: Any) -> Any:
    if isinstance(value, CommentedMap) or isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, CommentedSeq) or isinstance(value, list):
        return [_to_plain(v) for v in value]
    return value
