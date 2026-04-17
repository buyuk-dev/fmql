from __future__ import annotations

import hashlib
import warnings
from typing import Iterable, Iterator

from fmql.packet import Packet


def pick_frontmatter_field(packet: Packet, fields: Iterable[str]) -> tuple[str | None, str | None]:
    """Return (field_name, stringified_value) of the first present, non-empty field."""
    data = packet.as_plain()
    for f in fields:
        if f in data:
            value = data[f]
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return f, text
    return None, None


def _truncate_chars(text: str, max_tokens: int) -> tuple[str, bool]:
    """Cheap proxy for token truncation: assume ~4 chars/token."""
    limit = max_tokens * 4
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def build_document(packet: Packet, fields: Iterable[str], max_tokens: int) -> tuple[str, bool]:
    field_name, field_value = pick_frontmatter_field(packet, fields)
    parts: list[str] = []
    if field_value:
        parts.append(field_value)
    if packet.body:
        parts.append(packet.body.strip())
    doc = "\n\n".join(p for p in parts if p)
    return _truncate_chars(doc, max_tokens)


def content_hash(packet: Packet, fields: Iterable[str], max_tokens: int) -> str:
    doc, _ = build_document(packet, fields, max_tokens)
    fields_tuple = tuple(fields)
    h = hashlib.sha256()
    h.update("|".join(fields_tuple).encode("utf-8"))
    h.update(b"\n")
    h.update(doc.encode("utf-8"))
    return h.hexdigest()


def build_rows(
    packets: Iterable[Packet],
    fields: Iterable[str],
    max_tokens: int,
) -> Iterator[tuple[str, str, str]]:
    """Yield (packet_id, content_hash, document_text). Warns once if any row was truncated."""
    fields_tuple = tuple(fields)
    warned = False
    for packet in packets:
        doc, truncated = build_document(packet, fields_tuple, max_tokens)
        if truncated and not warned:
            warnings.warn(
                f"fmql-semantic: truncated packet {packet.id!r} to {max_tokens} tokens "
                f"(~{max_tokens * 4} chars). Raise --option max_tokens=N to change.",
                stacklevel=2,
            )
            warned = True
        h = hashlib.sha256()
        h.update("|".join(fields_tuple).encode("utf-8"))
        h.update(b"\n")
        h.update(doc.encode("utf-8"))
        yield packet.id, h.hexdigest(), doc
