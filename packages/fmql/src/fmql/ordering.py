from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fmql.filters import type_name

_NULLS_AUTO = "auto"
_NULLS_FIRST = "first"
_NULLS_LAST = "last"
_NULLS_CHOICES = (_NULLS_AUTO, _NULLS_FIRST, _NULLS_LAST)


@dataclass(frozen=True)
class OrderKey:
    field: str
    desc: bool = False
    nulls: str = _NULLS_AUTO

    def __post_init__(self) -> None:
        if self.nulls not in _NULLS_CHOICES:
            raise ValueError(f"OrderKey.nulls must be one of {_NULLS_CHOICES}, got {self.nulls!r}")


class _Reverse:
    __slots__ = ("obj",)

    def __init__(self, obj: Any) -> None:
        self.obj = obj

    def __lt__(self, other: "_Reverse") -> bool:
        return other.obj < self.obj

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _Reverse):
            return self.obj == other.obj
        return NotImplemented


def _type_rank(value: Any) -> int:
    name = type_name(value)
    if name == "bool":
        return 1
    if name in ("int", "float"):
        return 2
    if name in ("date", "datetime"):
        return 3
    if name == "str":
        return 4
    return 9


def _typed_value(value: Any) -> Any:
    name = type_name(value)
    if name in ("date", "datetime"):
        return value.isoformat()
    if name == "bool":
        return int(value)
    if name in ("int", "float"):
        return float(value)
    if name == "str":
        return value
    return repr(value)


def _nulls_first(key: OrderKey) -> bool:
    if key.nulls == _NULLS_FIRST:
        return True
    if key.nulls == _NULLS_LAST:
        return False
    return key.desc


def sort_key_for(value: Any, key: OrderKey, *, missing: bool = False) -> tuple:
    """Build a composite sort key for `value` under `key`.

    The returned tuple always starts with a null-rank (0 or 1) that is
    independent of `key.desc`, so that sorting with `reverse=False` places
    nulls consistently under `NULLS FIRST`/`LAST`. The payload portion is
    wrapped in `_Reverse` when `desc` is set, inverting the comparison for
    that key alone.
    """
    is_null = missing or value is None
    nulls_first = _nulls_first(key)
    if is_null:
        null_rank = 0 if nulls_first else 1
        return (null_rank,)
    null_rank = 1 if nulls_first else 0
    payload = (_type_rank(value), _typed_value(value))
    if key.desc:
        return (null_rank, _Reverse(payload))
    return (null_rank, payload)


def apply_order(
    items: list,
    keys: tuple[OrderKey, ...],
    extract,
) -> list:
    """Stable multi-key sort.

    `extract(item, key)` must return `(value, missing)` where `missing` is
    True when the field is absent. Sort is applied right-to-left over keys
    so Python's stable sort yields the correct multi-key ordering.
    """
    result = list(items)
    for key in reversed(keys):

        def _sk(item, k=key):
            value, missing = extract(item, k)
            return sort_key_for(value, k, missing=missing)

        result.sort(key=_sk)
    return result
