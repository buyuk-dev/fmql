from __future__ import annotations

from datetime import date
from pathlib import Path

from ruamel.yaml.comments import CommentedMap

from fmq.filters import Predicate, match, parse_kwargs
from fmq.packet import Packet


def _pkt(fm: dict) -> Packet:
    cm = CommentedMap()
    for k, v in fm.items():
        cm[k] = v
    return Packet(
        id="x.md",
        abspath=Path("/tmp/x.md"),
        frontmatter=cm,
        body="",
        raw_prefix="",
        fence_style=("---", "---"),
        eol="\n",
        newline_at_eof=True,
        has_frontmatter=True,
    )


def _match(fm: dict, **kwargs) -> bool:
    preds = parse_kwargs(kwargs)
    p = _pkt(fm)
    return all(match(p, pr) for pr in preds)


def test_eq_default():
    assert _match({"status": "active"}, status="active")
    assert not _match({"status": "done"}, status="active")


def test_ne():
    assert _match({"status": "active"}, status__ne="done")
    assert not _match({"status": "active"}, status__ne="active")


def test_gt_numeric():
    assert _match({"priority": 3}, priority__gt=2)
    assert not _match({"priority": 1}, priority__gt=2)


def test_gt_excludes_string_priority():
    # type-honest: string vs int doesn't compare, silently excluded
    assert not _match({"priority": "high"}, priority__gt=2)


def test_gt_excludes_missing():
    assert not _match({}, priority__gt=0)


def test_date_comparison():
    assert _match({"due_date": date(2026, 4, 10)}, due_date__lt=date(2026, 5, 1))
    assert not _match({"due_date": date(2026, 4, 10)}, due_date__gt=date(2026, 5, 1))


def test_in_membership():
    assert _match({"status": "active"}, status__in=["active", "blocked"])
    assert not _match({"status": "done"}, status__in=["active", "blocked"])


def test_not_in():
    assert _match({"status": "active"}, status__not_in=["done"])
    assert not _match({"status": "done"}, status__not_in=["done"])


def test_contains_list():
    assert _match({"tags": ["backend", "urgent"]}, tags__contains="urgent")
    assert not _match({"tags": ["backend"]}, tags__contains="urgent")


def test_contains_string_substring():
    assert _match({"title": "hello world"}, title__contains="world")


def test_icontains():
    assert _match({"title": "Hello World"}, title__icontains="hello")


def test_startswith_endswith():
    assert _match({"title": "task-42"}, title__startswith="task-")
    assert _match({"title": "task-42"}, title__endswith="42")


def test_matches_regex():
    assert _match({"uuid": "task-42"}, uuid__matches=r"^task-\d+$")
    assert not _match({"uuid": "task-xyz"}, uuid__matches=r"^task-\d+$")


def test_exists():
    assert _match({"a": 1}, a__exists=True)
    assert _match({}, a__exists=False)


def test_not_empty():
    assert _match({"tags": ["a"]}, tags__not_empty=True)
    assert not _match({"tags": []}, tags__not_empty=True)
    assert not _match({"tags": ""}, tags__not_empty=True)
    assert not _match({}, tags__not_empty=True)


def test_is_null():
    assert _match({"x": None}, x__is_null=True)
    assert not _match({"x": 0}, x__is_null=True)
    assert not _match({}, x__is_null=True)


def test_type():
    assert _match({"priority": 3}, priority__type="int")
    assert _match({"priority": "high"}, priority__type="str")
    assert not _match({"priority": 3}, priority__type="str")
    assert _match({"x": [1, 2]}, x__type="list")
    assert _match({"x": {"a": 1}}, x__type="map")


def test_parse_kwargs_structure():
    preds = parse_kwargs({"status": "active", "priority__gt": 2})
    assert Predicate("status", "eq", "active") in preds
    assert Predicate("priority", "gt", 2) in preds


def test_bool_not_treated_as_int():
    assert not _match({"flag": True}, flag__gt=0)
    assert _match({"flag": True}, flag__eq=True)
    assert not _match({"flag": 1}, flag__eq=True)
