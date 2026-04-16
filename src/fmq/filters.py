from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Iterable

from fmq.errors import FilterError
from fmq.packet import Packet

_MISSING = object()

_TYPE_NAMES: dict[str, type | tuple[type, ...] | None] = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "map": dict,
    "dict": dict,
    "null": type(None),
    "none": type(None),
    "date": date,
    "datetime": datetime,
}


@dataclass(frozen=True)
class Predicate:
    field: str
    op: str
    value: Any


def parse_kwargs(kwargs: dict[str, Any]) -> list[Predicate]:
    preds: list[Predicate] = []
    for key, value in kwargs.items():
        if "__" in key:
            field, _, op = key.rpartition("__")
        else:
            field, op = key, "eq"
        if not field:
            raise FilterError(f"empty field in predicate: {key!r}")
        if op not in _OPS:
            raise FilterError(f"unknown operator: {op!r}")
        preds.append(Predicate(field=field, op=op, value=value))
    return preds


def _get(packet: Packet, field: str) -> Any:
    fm = packet.frontmatter
    if field in fm:
        return fm[field]
    return _MISSING


def _is_bool(v: Any) -> bool:
    return isinstance(v, bool)


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not _is_bool(v)


def _comparable(a: Any, b: Any) -> bool:
    if _is_number(a) and _is_number(b):
        return True
    if isinstance(a, datetime) and isinstance(b, datetime):
        return True
    if isinstance(a, date) and isinstance(b, date) and not isinstance(a, datetime) and not isinstance(b, datetime):
        return True
    if isinstance(a, str) and isinstance(b, str):
        return True
    return False


def _as_plain(v: Any) -> Any:
    from fmq.packet import _to_plain

    return _to_plain(v)


def _eq(got: Any, expected: Any) -> bool:
    if got is _MISSING:
        return False
    if _is_bool(got) != _is_bool(expected):
        return False
    return _as_plain(got) == expected


def _ne(got: Any, expected: Any) -> bool:
    if got is _MISSING:
        return False
    return not _eq(got, expected)


def _cmp(got: Any, expected: Any, fn: Callable[[Any, Any], bool]) -> bool:
    if got is _MISSING:
        return False
    if _is_bool(got) or _is_bool(expected):
        return False
    if not _comparable(got, expected):
        return False
    try:
        return fn(got, expected)
    except TypeError:
        return False


def _in(got: Any, expected: Any) -> bool:
    if got is _MISSING:
        return False
    if not isinstance(expected, (list, tuple, set)):
        raise FilterError("`in` operator requires a list/tuple/set")
    return _as_plain(got) in expected


def _contains(got: Any, expected: Any) -> bool:
    if got is _MISSING:
        return False
    if isinstance(got, str) and isinstance(expected, str):
        return expected in got
    plain = _as_plain(got)
    if isinstance(plain, list):
        return expected in plain
    return False


def _icontains(got: Any, expected: Any) -> bool:
    if got is _MISSING:
        return False
    if isinstance(got, str) and isinstance(expected, str):
        return expected.lower() in got.lower()
    return False


def _startswith(got: Any, expected: Any) -> bool:
    if got is _MISSING:
        return False
    return isinstance(got, str) and isinstance(expected, str) and got.startswith(expected)


def _endswith(got: Any, expected: Any) -> bool:
    if got is _MISSING:
        return False
    return isinstance(got, str) and isinstance(expected, str) and got.endswith(expected)


def _matches(got: Any, expected: Any) -> bool:
    if got is _MISSING:
        return False
    if not isinstance(got, str) or not isinstance(expected, str):
        return False
    try:
        return re.search(expected, got) is not None
    except re.error as e:
        raise FilterError(f"invalid regex {expected!r}: {e}") from e


def _exists(got: Any, expected: Any) -> bool:
    present = got is not _MISSING
    return present if bool(expected) else not present


def _is_null(got: Any, expected: Any) -> bool:
    is_null = got is not _MISSING and got is None
    return is_null if bool(expected) else not is_null


def _not_empty(got: Any, expected: Any) -> bool:
    if got is _MISSING or got is None:
        empty = True
    else:
        plain = _as_plain(got)
        if plain == "" or plain == [] or plain == {}:
            empty = True
        else:
            empty = False
    return (not empty) if bool(expected) else empty


def _type(got: Any, expected: Any) -> bool:
    if got is _MISSING:
        return False
    if not isinstance(expected, str):
        raise FilterError("`type` operator requires a string type name")
    t = _TYPE_NAMES.get(expected.lower())
    if t is None and expected.lower() not in _TYPE_NAMES:
        raise FilterError(f"unknown type name: {expected!r}")
    plain = _as_plain(got)
    if expected.lower() in ("int", "float") and _is_bool(plain):
        return False
    if expected.lower() == "int":
        return isinstance(plain, int) and not isinstance(plain, bool)
    if expected.lower() == "float":
        return isinstance(plain, float)
    if expected.lower() == "bool":
        return isinstance(plain, bool)
    if expected.lower() == "str":
        return isinstance(plain, str)
    if expected.lower() in ("list",):
        return isinstance(plain, list)
    if expected.lower() in ("map", "dict"):
        return isinstance(plain, dict)
    if expected.lower() in ("null", "none"):
        return plain is None
    if expected.lower() == "date":
        return isinstance(plain, date) and not isinstance(plain, datetime)
    if expected.lower() == "datetime":
        return isinstance(plain, datetime)
    return False


_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": _eq,
    "ne": _ne,
    "not": _ne,
    "gt": lambda g, e: _cmp(g, e, lambda a, b: a > b),
    "gte": lambda g, e: _cmp(g, e, lambda a, b: a >= b),
    "lt": lambda g, e: _cmp(g, e, lambda a, b: a < b),
    "lte": lambda g, e: _cmp(g, e, lambda a, b: a <= b),
    "in": _in,
    "not_in": lambda g, e: (g is not _MISSING) and not _in(g, e),
    "contains": _contains,
    "icontains": _icontains,
    "startswith": _startswith,
    "endswith": _endswith,
    "matches": _matches,
    "exists": _exists,
    "not_empty": _not_empty,
    "is_null": _is_null,
    "type": _type,
}


def match(packet: Packet, pred: Predicate) -> bool:
    got = _get(packet, pred.field)
    return _OPS[pred.op](got, pred.value)


def match_all(packet: Packet, preds: Iterable[Predicate]) -> bool:
    return all(match(packet, p) for p in preds)
