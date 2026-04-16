from __future__ import annotations

import re
from datetime import date
from typing import Any

_INT = re.compile(r"^-?\d+$")
_FLOAT = re.compile(r"^-?\d+\.\d+$")
_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def coerce_value(raw: str) -> Any:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
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


def split_assignments(
    tokens: list[str],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Split a mixed positional list into (non_assignments, assignments).

    Assignments are tokens containing '='. Returns raw (key, value) pairs;
    value is the raw string — the caller decides whether to coerce.
    """
    non: list[str] = []
    assigns: list[tuple[str, str]] = []
    for t in tokens:
        if "=" in t:
            k, _, v = t.partition("=")
            assigns.append((k, v))
        else:
            non.append(t)
    return non, assigns
