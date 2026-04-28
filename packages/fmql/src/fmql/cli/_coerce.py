from __future__ import annotations

import json
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


def coerce_json_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise EditError(f"invalid JSON for ':=': {e.msg} (in {raw!r})") from e


def split_assignments(
    tokens: list[str],
) -> tuple[list[str], list[tuple[str, str, bool]]]:
    """Split a mixed positional list into (non_assignments, assignments).

    Assignments use either '=' (string-coerced) or ':=' (JSON-parsed). The
    earliest-occurring separator wins, so a '=' inside a JSON value following
    ':=' does not get mis-split. Returns (key, value, is_json) triples; the
    caller decides how to coerce.
    """
    non: list[str] = []
    assigns: list[tuple[str, str, bool]] = []
    for t in tokens:
        i_json = t.find(":=")
        i_eq = t.find("=")
        if i_json == -1 and i_eq == -1:
            non.append(t)
            continue
        if i_json != -1 and (i_eq == -1 or i_json <= i_eq):
            k, v = t[:i_json], t[i_json + 2 :]
            assigns.append((k, v, True))
        else:
            k, v = t[:i_eq], t[i_eq + 1 :]
            assigns.append((k, v, False))
    return non, assigns
