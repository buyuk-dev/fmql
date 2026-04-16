from __future__ import annotations

from datetime import date, timedelta

from fmq.dates import is_sentinel, now, resolve_sentinel, today


def test_today_is_date():
    assert isinstance(today(), date)


def test_resolve_plain_today():
    assert resolve_sentinel("today") == today()


def test_resolve_yesterday_tomorrow():
    assert resolve_sentinel("yesterday") == today() - timedelta(days=1)
    assert resolve_sentinel("tomorrow") == today() + timedelta(days=1)


def test_resolve_offset_days():
    assert resolve_sentinel("today-7d") == today() - timedelta(days=7)
    assert resolve_sentinel("today+3d") == today() + timedelta(days=3)


def test_resolve_offset_weeks():
    assert resolve_sentinel("today-2w") == today() - timedelta(weeks=2)


def test_now_is_datetime_like():
    n = now()
    assert n.year >= 2026 or n.year > 1970


def test_is_sentinel_accepts():
    assert is_sentinel("today")
    assert is_sentinel("today-7d")
    assert is_sentinel("now+1h")
    assert not is_sentinel("foo")
