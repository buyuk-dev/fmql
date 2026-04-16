from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from fmq.errors import ParseError
from fmq.packet import Packet
from fmq.types import PacketId

BOM = "\ufeff"
FENCE = "---"


def _make_yaml() -> YAML:
    yaml = YAML(typ="rt", pure=True)
    yaml.preserve_quotes = True
    yaml.width = 10_000
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


_YAML = _make_yaml()


def _detect_eol(text: str) -> str:
    crlf = text.find("\r\n")
    lf = text.find("\n")
    if crlf != -1 and (lf == -1 or crlf <= lf):
        return "\r\n"
    return "\n"


def _load_yaml(text: str) -> CommentedMap:
    try:
        data = _YAML.load(text) if text.strip() else CommentedMap()
    except YAMLError as e:
        raise ParseError(f"invalid YAML frontmatter: {e}") from e
    if data is None:
        return CommentedMap()
    if not isinstance(data, CommentedMap):
        raise ParseError(
            f"frontmatter must be a YAML mapping, got {type(data).__name__}"
        )
    return data


def _fence_pattern(eol: str) -> re.Pattern[str]:
    esc_fence = re.escape(FENCE)
    esc_eol = re.escape(eol)
    return re.compile(
        rf"^{esc_fence}{esc_eol}((?:.*?{esc_eol})?){esc_fence}(?:{esc_eol}|\Z)",
        re.DOTALL,
    )


def parse(text: str, *, pid: PacketId, abspath: Path) -> Packet:
    raw_prefix = ""
    if text.startswith(BOM):
        raw_prefix = BOM
        text = text[len(BOM) :]

    eol = _detect_eol(text)
    newline_at_eof = text.endswith(eol)

    has_fm = False
    fm_text = ""
    body = text
    fence_style = (FENCE, FENCE)

    m = _fence_pattern(eol).match(text)
    if m:
        fm_text = m.group(1) or ""
        body = text[m.end() :]
        has_fm = True

    frontmatter = _load_yaml(fm_text) if has_fm else CommentedMap()

    return Packet(
        id=pid,
        abspath=abspath,
        frontmatter=frontmatter,
        body=body,
        raw_prefix=raw_prefix,
        fence_style=fence_style,
        eol=eol,
        newline_at_eof=newline_at_eof,
        has_frontmatter=has_fm,
    )


def parse_file(path: Path, *, pid: PacketId) -> Packet:
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    return parse(text, pid=pid, abspath=path)


def dump_yaml(data: CommentedMap) -> str:
    buf = io.StringIO()
    _YAML.dump(data, buf)
    return buf.getvalue()


def serialize_packet(
    packet: Packet,
    *,
    frontmatter: Optional[CommentedMap] = None,
    body: Optional[str] = None,
    force_frontmatter: Optional[bool] = None,
) -> str:
    fm = packet.frontmatter if frontmatter is None else frontmatter
    b = packet.body if body is None else body
    eol = packet.eol

    if force_frontmatter is None:
        emit_fm = len(fm) > 0 or packet.has_frontmatter
    else:
        emit_fm = force_frontmatter

    if not emit_fm:
        out = packet.raw_prefix + b
    else:
        if len(fm) == 0:
            yaml_text = ""
        else:
            yaml_text = dump_yaml(fm)
            if eol != "\n":
                yaml_text = yaml_text.replace("\n", eol)
        body_out = b
        if not packet.has_frontmatter and body_out.startswith(FENCE + eol):
            body_out = eol + body_out
        out = (
            packet.raw_prefix
            + FENCE
            + eol
            + yaml_text
            + FENCE
            + eol
            + body_out
        )

    if packet.newline_at_eof:
        if not out.endswith(eol):
            out += eol
    else:
        if out.endswith(eol):
            out = out[: -len(eol)]

    return out
