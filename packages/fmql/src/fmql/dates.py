from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from fmql.errors import FilterError


def today() -> date:
    return datetime.now().date()


def now() -> datetime:
    return datetime.now().astimezone()


_OFFSET_RE = re.compile(r"^\s*(today|now|yesterday|tomorrow)\s*(?:([+-])\s*(\d+)([smhdw]))?\s*$")

_UNITS = {
    "s": "seconds",
    "m": "minutes",
    "h": "hours",
    "d": "days",
    "w": "weeks",
}


def resolve_sentinel(name: str) -> date | datetime:
    m = _OFFSET_RE.match(name)
    if not m:
        raise FilterError(f"unknown date sentinel: {name!r}")
    base, sign, amount, unit = m.group(1), m.group(2), m.group(3), m.group(4)

    value: date | datetime
    if base == "today":
        value = today()
    elif base == "yesterday":
        value = today() - timedelta(days=1)
    elif base == "tomorrow":
        value = today() + timedelta(days=1)
    elif base == "now":
        value = now()
    else:
        raise FilterError(f"unknown date sentinel: {name!r}")

    if sign is None:
        return value

    delta = timedelta(**{_UNITS[unit]: int(amount)})
    if unit in ("s", "m", "h") and isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    if sign == "-":
        delta = -delta
    return value + delta


def is_sentinel(name: str) -> bool:
    return bool(_OFFSET_RE.match(name))
