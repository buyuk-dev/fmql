"""Round-trip a frontmatter document through a structured ``{header, body}`` shape.

Powers the ``fmql serialize`` / ``fmql deserialize`` CLI commands. The
canonical structured form is::

    {
      "header": { "title": "Today", "tags": ["inbox"] },
      "body": "# Today\\n\\nSome notes...\\n"
    }

``header`` is a YAML-mapping-shaped object (or absent / null when the source
had no frontmatter at all). ``body`` is the raw markdown body string.
"""

from __future__ import annotations

import io
import json
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scalarstring import LiteralScalarString

from fmql.errors import FmqlError, ParseError
from fmql.packet import Packet
from fmql.parser import serialize_packet
from fmql.serialization import json_default

_DEFAULT_ABSPATH = Path("<deserialized>")


class SerializeFormat(str, Enum):
    json = "json"
    yaml = "yaml"


def _make_io_yaml() -> YAML:
    yaml = YAML(typ="rt", pure=True)
    yaml.preserve_quotes = True
    yaml.width = 10_000
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


_IO_YAML = _make_io_yaml()


def to_obj(packet: Packet) -> dict[str, Any]:
    """``{header, body}`` mapping. Omits ``header`` when the source had no fence pair;
    emits ``header: {}`` for an empty fence pair."""
    out: dict[str, Any] = {}
    if packet.has_frontmatter:
        out["header"] = packet.as_plain()
    out["body"] = packet.body
    return out


def to_json(packet: Packet) -> str:
    return json.dumps(to_obj(packet), default=json_default, indent=2, ensure_ascii=False) + "\n"


def to_yaml(packet: Packet) -> str:
    obj = to_obj(packet)
    body = obj.get("body", "")
    if isinstance(body, str) and "\n" in body:
        obj["body"] = LiteralScalarString(body)
    buf = io.StringIO()
    _IO_YAML.dump(obj, buf)
    return buf.getvalue()


def from_obj(obj: Any, *, abspath: Optional[Path] = None) -> Packet:
    """Synthesize a :class:`Packet` from a ``{header, body}`` mapping. ``header``
    absent / ``null`` round-trips as no fence pair; ``{}`` round-trips as an
    empty fence pair."""
    if not isinstance(obj, dict):
        raise FmqlError(f"expected mapping with 'header' and 'body', got {type(obj).__name__}")
    unknown = set(obj) - {"header", "body"}
    if unknown:
        raise FmqlError(f"unexpected key(s): {sorted(unknown)}")

    header = obj.get("header", None)
    has_frontmatter = "header" in obj and header is not None
    if header is not None and not isinstance(header, dict):
        raise FmqlError(f"'header' must be a mapping or null, got {type(header).__name__}")

    body = obj.get("body", "")
    if not isinstance(body, str):
        raise FmqlError(f"'body' must be a string, got {type(body).__name__}")

    fm = CommentedMap()
    if isinstance(header, dict):
        for k, v in header.items():
            fm[str(k)] = _to_commented(v)

    path = abspath if abspath is not None else _DEFAULT_ABSPATH
    return Packet(
        id=path.as_posix(),
        abspath=path,
        frontmatter=fm,
        body=body,
        raw_prefix="",
        fence_style=("---", "---"),
        eol="\n",
        newline_at_eof=body.endswith("\n") or body == "",
        has_frontmatter=has_frontmatter,
    )


def from_json(text: str, *, abspath: Optional[Path] = None) -> Packet:
    try:
        obj = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError as e:
        raise ParseError(f"invalid JSON: {e}") from e
    return from_obj(obj, abspath=abspath)


def from_yaml(text: str, *, abspath: Optional[Path] = None) -> Packet:
    try:
        obj = _IO_YAML.load(text) if text.strip() else {}
    except YAMLError as e:
        raise ParseError(f"invalid YAML: {e}") from e
    if obj is None:
        obj = {}
    return from_obj(obj, abspath=abspath)


def deserialize_to_markdown(text: str, *, fmt: SerializeFormat) -> str:
    if fmt is SerializeFormat.json:
        packet = from_json(text)
    elif fmt is SerializeFormat.yaml:
        packet = from_yaml(text)
    else:
        raise FmqlError(f"unknown format: {fmt!r}")
    return serialize_packet(packet)


def serialize_packet_to(packet: Packet, *, fmt: SerializeFormat) -> str:
    if fmt is SerializeFormat.json:
        return to_json(packet)
    if fmt is SerializeFormat.yaml:
        return to_yaml(packet)
    raise FmqlError(f"unknown format: {fmt!r}")


def _to_commented(value: Any) -> Any:
    # CommentedMap/CommentedSeq are already in the right form — return as-is so
    # source style metadata (block vs flow, quote style) survives YAML round-trip.
    if isinstance(value, (CommentedMap, CommentedSeq)):
        return value
    if isinstance(value, dict):
        m = CommentedMap()
        for k, v in value.items():
            m[str(k)] = _to_commented(v)
        return m
    if isinstance(value, list):
        seq = CommentedSeq()
        for v in value:
            seq.append(_to_commented(v))
        return seq
    return value
