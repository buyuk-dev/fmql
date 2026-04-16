from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from fmq.filters import type_name
from fmq.workspace import Workspace


@dataclass
class FieldStat:
    name: str
    present_in: int
    types: dict[str, int] = field(default_factory=dict)
    top_values: list[tuple[Any, int]] = field(default_factory=list)
    numeric_min: Optional[float] = None
    numeric_max: Optional[float] = None
    numeric_avg: Optional[float] = None
    date_min: Optional[date] = None
    date_max: Optional[date] = None


@dataclass
class WorkspaceStats:
    root: Path
    packet_count: int
    files_without_frontmatter: int
    fields: list[FieldStat] = field(default_factory=list)


def _is_scalar(value: Any) -> bool:
    return not isinstance(value, (list, dict, set))


def describe(ws: Workspace, *, top_n: int = 5) -> WorkspaceStats:
    packet_count = len(ws.packets)
    files_without_frontmatter = sum(1 for p in ws.packets.values() if not p.has_frontmatter)

    present: Counter[str] = Counter()
    types: dict[str, Counter[str]] = {}
    scalar_counts: dict[str, Counter[Any]] = {}
    numeric: dict[str, list[float]] = {}
    dates: dict[str, list[date]] = {}

    for packet in ws.packets.values():
        plain = packet.as_plain()
        for key, value in plain.items():
            present[key] += 1
            tn = type_name(value)
            types.setdefault(key, Counter())[tn] += 1
            if tn in ("int", "float") and not isinstance(value, bool):
                numeric.setdefault(key, []).append(float(value))
            if tn in ("date", "datetime"):
                dates.setdefault(key, []).append(value)
            if _is_scalar(value):
                try:
                    scalar_counts.setdefault(key, Counter())[value] += 1
                except TypeError:
                    pass

    fields: list[FieldStat] = []
    for name in present:
        stat = FieldStat(
            name=name,
            present_in=present[name],
            types=dict(types.get(name, {})),
        )
        counts = scalar_counts.get(name)
        if counts:
            stat.top_values = counts.most_common(top_n)
        nums = numeric.get(name)
        if nums:
            stat.numeric_min = min(nums)
            stat.numeric_max = max(nums)
            stat.numeric_avg = sum(nums) / len(nums)
        ds = dates.get(name)
        if ds:
            stat.date_min = min(ds)
            stat.date_max = max(ds)
        fields.append(stat)

    fields.sort(key=lambda s: (-s.present_in, s.name))

    return WorkspaceStats(
        root=ws.root,
        packet_count=packet_count,
        files_without_frontmatter=files_without_frontmatter,
        fields=fields,
    )


def _fmt_scalar(v: Any) -> str:
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, str):
        return v
    return repr(v)


def _fmt_number(v: float) -> str:
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.2f}"


def format_text(stats: WorkspaceStats) -> str:
    lines: list[str] = []
    lines.append(f"workspace: {stats.root}")
    lines.append(f"  packets: {stats.packet_count}")
    lines.append(f"  no-frontmatter: {stats.files_without_frontmatter}")
    lines.append("")
    lines.append("fields:")
    if not stats.fields:
        lines.append("  (none)")
        return "\n".join(lines) + "\n"

    name_width = max(len(s.name) for s in stats.fields)
    for s in stats.fields:
        types_str = "{" + ", ".join(f"{k}: {v}" for k, v in s.types.items()) + "}"
        parts = [f"  {s.name.ljust(name_width)}  present={s.present_in}  types={types_str}"]
        if s.numeric_min is not None:
            parts.append(f"range=[{_fmt_number(s.numeric_min)}..{_fmt_number(s.numeric_max)}]")
            parts.append(f"avg={_fmt_number(s.numeric_avg)}")
        if s.date_min is not None:
            parts.append(f"range=[{s.date_min.isoformat()}..{s.date_max.isoformat()}]")
        if s.top_values:
            top = ", ".join(f"{_fmt_scalar(v)} ({n})" for v, n in s.top_values)
            parts.append(f"top: {top}")
        lines.append("  ".join(parts))
    return "\n".join(lines) + "\n"


def _json_default(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"not JSON-serializable: {type(o).__name__}")


def format_json(stats: WorkspaceStats) -> str:
    payload = {
        "root": str(stats.root),
        "packet_count": stats.packet_count,
        "files_without_frontmatter": stats.files_without_frontmatter,
        "fields": [
            {
                "name": s.name,
                "present_in": s.present_in,
                "types": s.types,
                "top_values": [{"value": v, "count": n} for v, n in s.top_values],
                "numeric_min": s.numeric_min,
                "numeric_max": s.numeric_max,
                "numeric_avg": s.numeric_avg,
                "date_min": s.date_min,
                "date_max": s.date_max,
            }
            for s in stats.fields
        ],
    }
    return json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2)
