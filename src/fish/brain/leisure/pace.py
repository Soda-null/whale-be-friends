"""How much free time a day holds (decision 59): not the same every day.

Every day had at most three free moments, at least three hours apart, from 09:00: her "doing
her own things" fell on the same hours day after day. Now the day draws how many (one fewer,
the usual, or one more: the same on average, so it costs the same), how far apart, and how
late the first may come. The day draws them, so the gate gets the same answer all day and
nothing is stored.
"""

from __future__ import annotations

import random
from datetime import date, time, timedelta

MORE_OR_FEWER = (-1, 0, 0, 1)  # moments added to the usual number; evens out over the days
GAP_HOURS = (2.0, 4.0)  # between two moments
START, START_LATER_MINUTES = time(9, 0), (0, 60)


def _rng(day: date, what: str) -> random.Random:
    return random.Random(f"leisure-{what}:{day.toordinal()}")


def moments_on(day: date, usual: int) -> int:
    """How many free moments this day may hold; `usual` is the setting (0 stays 0)."""
    return max(1, usual + _rng(day, "count").choice(MORE_OR_FEWER)) if usual > 0 else 0


def gap_on(day: date) -> timedelta:
    return timedelta(hours=_rng(day, "gap").uniform(*GAP_HOURS))


def starts_on(day: date) -> time:
    minutes = START.hour * 60 + START.minute + _rng(day, "start").randint(*START_LATER_MINUTES)
    return time(minutes // 60, minutes % 60)
