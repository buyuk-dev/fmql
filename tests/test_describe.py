from __future__ import annotations

import json
from datetime import date

from fmql.describe import WorkspaceStats, describe, format_json, format_text


def _field(stats: WorkspaceStats, name: str):
    for f in stats.fields:
        if f.name == name:
            return f
    raise AssertionError(f"field {name!r} not found")


def test_describe_basic_counts(project_pm_ws):
    stats = describe(project_pm_ws)
    assert stats.packet_count == len(project_pm_ws)
    assert stats.files_without_frontmatter == 1


def test_describe_status_field(project_pm_ws):
    stats = describe(project_pm_ws)
    s = _field(stats, "status")
    assert s.present_in == 5
    assert s.types == {"str": 5}
    values = dict(s.top_values)
    assert values["active"] == 4
    assert values["done"] == 1


def test_describe_priority_mixed_types(project_pm_ws):
    stats = describe(project_pm_ws)
    p = _field(stats, "priority")
    assert p.types == {"int": 4, "str": 1}
    # numeric aggregates only over the int values: 3,1,5,2
    assert p.numeric_min == 1
    assert p.numeric_max == 5
    assert p.numeric_avg == (3 + 1 + 5 + 2) / 4


def test_describe_due_date_range(project_pm_ws):
    stats = describe(project_pm_ws)
    d = _field(stats, "due_date")
    assert d.types == {"date": 4}
    assert d.date_min == date(2026, 4, 10)
    assert d.date_max == date(2026, 5, 5)
    assert d.numeric_min is None
    assert d.numeric_avg is None


def test_describe_list_field_has_no_top_values(project_pm_ws):
    stats = describe(project_pm_ws)
    t = _field(stats, "tags")
    assert t.types == {"list": 4}
    assert t.top_values == []


def test_describe_top_n_truncates(project_pm_ws):
    stats = describe(project_pm_ws, top_n=1)
    s = _field(stats, "status")
    assert len(s.top_values) == 1
    assert s.top_values[0][0] == "active"


def test_describe_fields_sorted_by_presence(project_pm_ws):
    stats = describe(project_pm_ws)
    presences = [f.present_in for f in stats.fields]
    assert presences == sorted(presences, reverse=True)


def test_format_text_has_packets_and_field_names(project_pm_ws):
    stats = describe(project_pm_ws)
    text = format_text(stats)
    assert "packets:" in text
    assert "no-frontmatter:" in text
    for name in ("status", "priority", "due_date"):
        assert name in text


def test_format_json_is_parseable(project_pm_ws):
    stats = describe(project_pm_ws)
    payload = json.loads(format_json(stats))
    assert payload["packet_count"] == stats.packet_count
    assert payload["files_without_frontmatter"] == 1
    assert isinstance(payload["fields"], list)
    due = next(f for f in payload["fields"] if f["name"] == "due_date")
    assert due["date_min"] == "2026-04-10"
    assert due["date_max"] == "2026-05-05"


def test_describe_empty_workspace(make_workspace):
    ws = make_workspace({})
    stats = describe(ws)
    assert stats.packet_count == 0
    assert stats.files_without_frontmatter == 0
    assert stats.fields == []
    # format_text still works
    assert "(none)" in format_text(stats)
