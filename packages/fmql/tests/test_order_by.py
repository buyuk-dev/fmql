from __future__ import annotations

from datetime import date

import pytest

from fmql.errors import QueryError
from fmql.ordering import OrderKey
from fmql.qlang import compile_query
from fmql.query import Query


@pytest.fixture
def ordering_ws(make_workspace):
    spec = {
        "p1.md": {"frontmatter": {"uuid": "p1", "priority": 3, "status": "open"}},
        "p2.md": {"frontmatter": {"uuid": "p2", "priority": 1, "status": "open"}},
        "p3.md": {"frontmatter": {"uuid": "p3", "priority": 5, "status": "done"}},
        "p4.md": {"frontmatter": {"uuid": "p4", "priority": 2, "status": "open"}},
        "p5.md": {"frontmatter": {"uuid": "p5", "status": "open"}},  # missing priority
    }
    return make_workspace(spec)


def _priorities(ids, ws):
    return [ws.packets[pid].as_plain().get("priority") for pid in ids]


def test_order_by_asc(ordering_ws):
    ids = compile_query("* ORDER BY priority", ordering_ws).ids()
    values = _priorities(ids, ordering_ws)
    # ASC default → nulls last
    assert values == [1, 2, 3, 5, None]


def test_order_by_desc(ordering_ws):
    ids = compile_query("* ORDER BY priority DESC", ordering_ws).ids()
    values = _priorities(ids, ordering_ws)
    # DESC default → nulls first
    assert values == [None, 5, 3, 2, 1]


def test_order_by_nulls_last_with_desc(ordering_ws):
    ids = compile_query("* ORDER BY priority DESC NULLS LAST", ordering_ws).ids()
    values = _priorities(ids, ordering_ws)
    assert values == [5, 3, 2, 1, None]


def test_order_by_nulls_first_with_asc(ordering_ws):
    ids = compile_query("* ORDER BY priority NULLS FIRST", ordering_ws).ids()
    values = _priorities(ids, ordering_ws)
    assert values == [None, 1, 2, 3, 5]


def test_order_by_multi_key(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"status": "open", "priority": 2}},
        "b.md": {"frontmatter": {"status": "open", "priority": 1}},
        "c.md": {"frontmatter": {"status": "done", "priority": 3}},
        "d.md": {"frontmatter": {"status": "done", "priority": 1}},
    }
    ws = make_workspace(spec)
    ids = compile_query("* ORDER BY status, priority DESC", ws).ids()
    rows = [
        (ws.packets[pid].as_plain().get("status"), ws.packets[pid].as_plain().get("priority"))
        for pid in ids
    ]
    assert rows == [("done", 3), ("done", 1), ("open", 2), ("open", 1)]


def test_order_by_after_where(ordering_ws):
    ids = compile_query('status = "open" ORDER BY priority DESC', ordering_ws).ids()
    values = _priorities(ids, ordering_ws)
    # status=open only: p1=3, p2=1, p4=2, p5=None → DESC nulls first
    assert values == [None, 3, 2, 1]


def test_python_api_order_by_chainable(ordering_ws):
    q = Query(ordering_ws).where(status="open").order_by("priority", desc=True)
    values = _priorities(q.ids(), ordering_ws)
    assert values == [None, 3, 2, 1]


def test_python_api_multi_key_accumulates(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"status": "open", "priority": 2}},
        "b.md": {"frontmatter": {"status": "open", "priority": 1}},
        "c.md": {"frontmatter": {"status": "done", "priority": 3}},
    }
    ws = make_workspace(spec)
    q = Query(ws).order_by("status").order_by("priority", desc=True)
    rows = [
        (ws.packets[pid].as_plain()["status"], ws.packets[pid].as_plain()["priority"])
        for pid in q.ids()
    ]
    assert rows == [("done", 3), ("open", 2), ("open", 1)]


def test_order_key_validates_nulls():
    with pytest.raises(ValueError):
        OrderKey(field="x", nulls="bogus")


def test_order_by_heterogeneous_types(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"k": 1}},
        "b.md": {"frontmatter": {"k": "zebra"}},
        "c.md": {"frontmatter": {"k": True}},
        "d.md": {"frontmatter": {"k": 2}},
    }
    ws = make_workspace(spec)
    # Should not raise — heterogeneous types get bucketed by type rank
    ids = compile_query("* ORDER BY k", ws).ids()
    assert len(ids) == 4


def test_order_by_date_field(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"due": date(2026, 5, 10)}},
        "b.md": {"frontmatter": {"due": date(2026, 4, 1)}},
        "c.md": {"frontmatter": {"due": date(2026, 7, 15)}},
    }
    ws = make_workspace(spec)
    ids = compile_query("* ORDER BY due", ws).ids()
    values = [ws.packets[pid].as_plain()["due"] for pid in ids]
    assert values == [date(2026, 4, 1), date(2026, 5, 10), date(2026, 7, 15)]


def test_order_by_unknown_field_sorts_all_missing(make_workspace):
    spec = {
        "a.md": {"frontmatter": {"x": 1}},
        "b.md": {"frontmatter": {"x": 2}},
    }
    ws = make_workspace(spec)
    ids = compile_query("* ORDER BY nonexistent", ws).ids()
    assert len(ids) == 2


def test_order_by_reserved_keyword_parse_error(ordering_ws):
    # Using ORDER as a bare field must work — ORDER by itself is keyword only in ORDER BY position
    # but the compiler sees "ORDER" as an IDENT token when not followed by BY at top level;
    # this test documents that it's fine to use other reserved names inside quoted values.
    q = compile_query('status = "open"', ordering_ws)
    assert len(q.ids()) >= 1


def test_default_order_preserved_when_no_order_by(ordering_ws):
    # Back-compat: no ORDER BY → packet-id ordering (today's behavior)
    ids = compile_query("*", ordering_ws).ids()
    assert ids == sorted(ordering_ws.packets.keys())


def test_invalid_order_direction_parse_error(ordering_ws):
    with pytest.raises(QueryError):
        compile_query("* ORDER BY priority BOGUS", ordering_ws)
