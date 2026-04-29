from __future__ import annotations

import re
from datetime import date
from typing import Any

from fmql.errors import EditError

_INT = re.compile(r"^-?\d+$")
_FLOAT = re.compile(r"^-?\d+\.\d+$")
_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def coerce_value(raw: str) -> Any:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    if raw[:1] in ("[", "{"):
        raise EditError(
            f"list/dict-shaped value {raw!r} — use ':=' for JSON parsing, " "or quote the string"
        )
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in ("null", "none"):
        return None
    if _INT.match(raw):
        return int(raw)
    if _FLOAT.match(raw):
        return float(raw)
    m = _DATE.match(raw)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return raw
