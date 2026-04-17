from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Union

from fmql.filters import _comparable, _is_bool, _is_number, type_name
from fmql.packet import Packet

if TYPE_CHECKING:
    from fmql.query import Query


_MISSING = object()


@dataclass(frozen=True)
class Count:
    field: str | None = None


@dataclass(frozen=True)
class Sum:
    field: str


@dataclass(frozen=True)
class Avg:
    field: str


@dataclass(frozen=True)
class Min:
    field: str


@dataclass(frozen=True)
class Max:
    field: str


Aggregator = Union[Count, Sum, Avg, Min, Max]


def _get(packet: Packet, field: str) -> Any:
    plain = packet.as_plain()
    if field in plain:
        return plain[field]
    return _MISSING


def _is_groupable(value: Any) -> bool:
    if value is _MISSING or value is None:
        return False
    if isinstance(value, (list, dict, set)):
        return False
    try:
        hash(value)
    except TypeError:
        return False
    return True


def _sort_key(value: Any) -> tuple[str, Any]:
    name = type_name(value)
    if name in ("date", "datetime"):
        return (name, value.isoformat())
    if name in ("int", "float", "bool"):
        return (name, float(value))
    return (name, str(value))


def _numeric_values(packets: list[Packet], field: str) -> list[int | float]:
    out: list[int | float] = []
    for p in packets:
        v = _get(p, field)
        if v is _MISSING or _is_bool(v) or not _is_number(v):
            continue
        out.append(v)
    return out


def _comparable_values(packets: list[Packet], field: str) -> list[Any]:
    out: list[Any] = []
    for p in packets:
        v = _get(p, field)
        if v is _MISSING or v is None or _is_bool(v):
            continue
        if out and not _comparable(out[0], v):
            continue
        out.append(v)
    return out


def _count_field(packets: list[Packet], field: str) -> int:
    n = 0
    for p in packets:
        v = _get(p, field)
        if v is _MISSING or v is None:
            continue
        n += 1
    return n


def _apply(agg: Aggregator, packets: list[Packet]) -> tuple[bool, Any]:
    """Return (emit, value). emit=False means 'omit this key from result'."""
    if isinstance(agg, Count):
        if agg.field is None:
            return True, len(packets)
        return True, _count_field(packets, agg.field)
    if isinstance(agg, Sum):
        return True, sum(_numeric_values(packets, agg.field))
    if isinstance(agg, Avg):
        values = _numeric_values(packets, agg.field)
        if not values:
            return False, None
        return True, sum(values) / len(values)
    if isinstance(agg, (Min, Max)):
        values = _comparable_values(packets, agg.field)
        if not values:
            return False, None
        return True, (min(values) if isinstance(agg, Min) else max(values))
    raise TypeError(f"unknown aggregator: {type(agg).__name__}")


@dataclass(frozen=True)
class GroupedQuery:
    query: "Query"
    field: str

    def groups(self) -> dict[Any, list[Packet]]:
        ws = self.query.workspace
        buckets: dict[Any, list[Packet]] = {}
        for pid in self.query.ids():
            packet = ws.packets[pid]
            value = _get(packet, self.field)
            if not _is_groupable(value):
                continue
            buckets.setdefault(value, []).append(packet)
        try:
            items = sorted(buckets.items(), key=lambda kv: _sort_key(kv[0]))
        except TypeError:
            items = list(buckets.items())
        return dict(items)

    def count(self) -> dict[Any, int]:
        return {k: len(v) for k, v in self.groups().items()}

    def sum(self, field: str) -> dict[Any, int | float]:
        out: dict[Any, int | float] = {}
        for k, packets in self.groups().items():
            emit, v = _apply(Sum(field), packets)
            if emit:
                out[k] = v
        return out

    def avg(self, field: str) -> dict[Any, float]:
        out: dict[Any, float] = {}
        for k, packets in self.groups().items():
            emit, v = _apply(Avg(field), packets)
            if emit:
                out[k] = v
        return out

    def min(self, field: str) -> dict[Any, Any]:
        out: dict[Any, Any] = {}
        for k, packets in self.groups().items():
            emit, v = _apply(Min(field), packets)
            if emit:
                out[k] = v
        return out

    def max(self, field: str) -> dict[Any, Any]:
        out: dict[Any, Any] = {}
        for k, packets in self.groups().items():
            emit, v = _apply(Max(field), packets)
            if emit:
                out[k] = v
        return out

    def aggregate(self, **aggs: Aggregator) -> dict[Any, dict[str, Any]]:
        out: dict[Any, dict[str, Any]] = {}
        for k, packets in self.groups().items():
            row: dict[str, Any] = {}
            for name, agg in aggs.items():
                emit, v = _apply(agg, packets)
                if emit:
                    row[name] = v
            out[k] = row
        return out
