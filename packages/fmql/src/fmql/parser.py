from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from fmql.errors import ParseError
from fmql.packet import Packet
from fmql.types import PacketId

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
        raise ParseError(f"frontmatter must be a YAML mapping, got {type(data).__name__}")
    return data


def _fence_pattern(eol: str) -> re.Pattern[str]:
    esc_fence = re.escape(FENCE)
    esc_eol = re.escape(eol)
    return re.compile(
        rf"^{esc_fence}{esc_eol}((?:.*?{esc_eol})?){esc_fence}(?:{esc_eol}|\Z)",
        re.DOTALL,
    )


def parse(text: str, *, abspath: Path, pid: Optional[PacketId] = None) -> Packet:
    """Parse a frontmatter+markdown string into a :class:`Packet`.

    Splits a leading YAML frontmatter block (delimited by ``---`` fences) from
    the markdown body. The returned packet preserves enough state to round-trip
    losslessly via :func:`serialize_packet`: BOM prefix, line-ending style
    (``\\n`` vs ``\\r\\n``), fence delimiters, EOF newline, and YAML quoting /
    key order on untouched fields.

    Args:
        text: Raw file contents.
        abspath: Filesystem path the text logically lives at. Stored on the
            returned :class:`Packet` and used as the default packet id.
        pid: Stable identifier for the packet. Defaults to ``abspath.as_posix()``
            when omitted.

    Raises:
        ParseError: When the frontmatter is not valid YAML or is not a mapping.
    """
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
        id=pid if pid is not None else abspath.as_posix(),
        abspath=abspath,
        frontmatter=frontmatter,
        body=body,
        raw_prefix=raw_prefix,
        fence_style=fence_style,
        eol=eol,
        newline_at_eof=newline_at_eof,
        has_frontmatter=has_fm,
    )


def parse_file(path: Path, *, pid: Optional[PacketId] = None) -> Packet:
    """Read a file from disk and parse it into a :class:`Packet`.

    Convenience wrapper around :func:`parse` that opens ``path`` in text mode
    with newline translation disabled, so the original line endings survive
    into the returned packet. The same round-trip guarantees as :func:`parse`
    apply.

    Args:
        path: Path to the file to read.
        pid: Stable identifier for the packet. Defaults to ``path.as_posix()``
            when omitted, which is suitable for standalone parser use; pass an
            explicit workspace-relative id when loading inside a
            :class:`~fmql.workspace.Workspace`.

    Raises:
        ParseError: When the frontmatter is not valid YAML or is not a mapping.
        OSError: When the file cannot be opened.
    """
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    return parse(text, abspath=path, pid=pid)


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
    """Serialize a :class:`Packet` back to a string.

    Round-trips byte-exactly when ``packet`` is unmodified: BOM prefix, line
    endings, fence delimiters, EOF newline, and YAML quoting / key order on
    untouched fields are all preserved. Re-exported at the top level as
    :func:`fmql.serialize`.

    Args:
        packet: The packet to serialize.
        frontmatter: Optional override for the frontmatter mapping. When
            provided, the original ``packet.frontmatter`` is ignored. Useful
            when applying an in-place edit without mutating the parsed packet.
        body: Optional override for the markdown body. When provided, the
            original ``packet.body`` is ignored.
        force_frontmatter: Override the heuristic that decides whether to emit
            a frontmatter block at all. ``None`` (default) emits a block when
            the source had one or when the (effective) frontmatter is
            non-empty; ``True`` always emits; ``False`` never emits.
    """
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
        out = packet.raw_prefix + FENCE + eol + yaml_text + FENCE + eol + body_out

    if packet.newline_at_eof:
        if not out.endswith(eol):
            out += eol
    else:
        if out.endswith(eol):
            out = out[: -len(eol)]

    return out
