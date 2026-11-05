"""What a night did not get done, so the next night can make up for it and `fish life` can say so.

A model call that fails must not stop the night (brain/consolidate.py), but until 11-04 it also
left no trace: 11-02's diary was simply never written. `record` keeps the last night's list in
routine_runs; `chat_days` and `days_without_diary` are worked out from what is really there,
so a day is caught up however it came to be missing.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from fish.memory import Diary, EpisodeManager
from fish.routines.night.context import Night, fish_day
from fish.routines.runs import last_run, mark_run

LOOK_BACK_DAYS = 7  # a diary missing for longer than this stays missing
EPISODES_LOOKED_AT = 200  # plenty for a week of chats
FAILED_RUN = "night_failed"  # routine_runs: "2026-11-02|diary,letter"; nothing after | = a clean night
CRASHED = "night."  # a step that raised has this in front of its name; the rest are model calls


def record(night: Night, crashed: list[str]) -> None:
    failed = sorted(set(night.thinker.failed)) if night.thinker else []
    failed += crashed
    if failed:
        night.report["failed"] = failed
    mark_run(night.conn, FAILED_RUN, f"{night.day.isoformat()}|{','.join(failed)}")


def last_night_failed(conn: sqlite3.Connection) -> tuple[date | None, set[str]]:
    """The last night done and what failed in it; (None, empty) before the first."""
    value = last_run(conn, FAILED_RUN)
    if not value:
        return None, set()
    day, _, names = value.partition("|")
    return date.fromisoformat(day), {n for n in names.split(",") if n}


def chat_days(conn: sqlite3.Connection, before: date) -> list[date]:
    """The days in the last week before `before` they talked, oldest first."""
    days = {fish_day(datetime.fromisoformat(e.started)) for e in EpisodeManager(conn).recent(EPISODES_LOOKED_AT)}
    return sorted(d for d in days if before - timedelta(days=LOOK_BACK_DAYS) <= d < before)


def days_without_diary(conn: sqlite3.Connection, before: date) -> list[date]:
    written = Diary(conn).days()
    return [d for d in chat_days(conn, before) if d.isoformat() not in written]
