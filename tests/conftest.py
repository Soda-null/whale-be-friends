"""Tests open hundreds of throwaway databases. Skip waiting for the disk on every commit:
on Windows that wait made the suite take 13 minutes instead of seconds. Only tests load this
file; her real database keeps SQLite's safe default."""

import sqlite3

_connect = sqlite3.connect


def _connect_without_fsync(*args, **kwargs):
    conn = _connect(*args, **kwargs)
    conn.execute("PRAGMA synchronous = OFF")
    return conn


sqlite3.connect = _connect_without_fsync


# A failed night call is tried again after a wait; tests do not wait.
from fish.brain import consolidate  # noqa: E402

consolidate.ASK_WAIT_SECONDS = 0


# Her hours and her free time are drawn anew each day (decision 59, cottage/hours.py and
# brain/leisure/pace.py). The older tests were written with the plain numbers (asleep 00:00-08:00,
# meals from 11:30 and 17:30, three free moments three hours apart from 09:00) and are about what
# she does, not about when a day's draw falls, so they run with the draw switched off. A test
# that is about the draw itself asks for the real numbers with @pytest.mark.drawn_hours.
import pytest  # noqa: E402

from fish.brain.leisure import pace  # noqa: E402
from fish.cottage import hours  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "drawn_hours: her hours are drawn day by day, as in real life")


@pytest.fixture(autouse=True)
def plain_hours(request, monkeypatch):
    if request.node.get_closest_marker("drawn_hours"):
        return
    monkeypatch.setattr(hours, "BED_LATER_MINUTES", (0, 0))
    monkeypatch.setattr(hours, "WAKE_SHIFT_MINUTES", (0, 0))
    monkeypatch.setattr(hours, "LIE_IN_MINUTES", 0)
    monkeypatch.setattr(hours, "MEAL_LATER_MINUTES", (0, 0))
    monkeypatch.setattr(pace, "MORE_OR_FEWER", (0,))
    monkeypatch.setattr(pace, "GAP_HOURS", (3.0, 3.0))
    monkeypatch.setattr(pace, "START_LATER_MINUTES", (0, 0))
