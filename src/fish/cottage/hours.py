"""Her hours, a little different every day (decision 59).

She used to fall asleep at 00:00:00 and get up at 08:00:00 every day of the year, and eat on
the stroke of 11:30 and 17:30. Now each day draws its own bedtime, getting-up time and
mealtimes around those hours (the numbers are in rules.py), later still on a weekend morning.
The day draws them, so every question about one day gets the same answer, however often and
in whatever order it is asked: nothing is stored, and the room's record stays the only state.

Everything that needs to know when she sleeps, wakes or eats asks here. The goldfish keeps its
own fixed night (rules.asleep_hours): it has no weekends.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from fish.cottage.rules import (BED_LATER_MINUTES, ENERGY_PER_HOUR, LIE_IN_MINUTES, MEAL_LATER_MINUTES, MEALS,
                                SLEEP_FROM, WAKE_AT, WAKE_SHIFT_MINUTES)


def _drawn(day: date, what: str, span: tuple[int, int]) -> timedelta:
    return timedelta(minutes=random.Random(f"{what}:{day.toordinal()}").randint(*span))


def bed_at(day: date) -> datetime:
    """When she fell asleep in the small hours of `day`."""
    return datetime.combine(day, SLEEP_FROM) + _drawn(day, "bed", BED_LATER_MINUTES)


def wake_at(day: date) -> datetime:
    """When she gets up on `day`: a lie-in on Saturday and Sunday."""
    lie_in = timedelta(minutes=LIE_IN_MINUTES if day.weekday() >= 5 else 0)
    return datetime.combine(day, WAKE_AT) + _drawn(day, "wake", WAKE_SHIFT_MINUTES) + lie_in


def woke(now: datetime) -> datetime:
    """The last time she got up: this morning, or yesterday's when today's has not come yet."""
    today = wake_at(now.date())
    return today if today <= now else wake_at(now.date() - timedelta(days=1))


def asleep_hours(t: datetime) -> bool:
    return bed_at(t.date()) <= t < wake_at(t.date())


def meals(day: date) -> tuple[tuple[str, time, time], ...]:
    """(name, from, until) for `day`: she gets hungry for each a little later or not, the
    window closes when it always did."""
    return tuple((name, (datetime.combine(day, start) + _drawn(day, name, MEAL_LATER_MINUTES)).time(), end)
                 for name, start, end in MEALS)


def mealtime(now: datetime) -> str | None:
    return next((name for name, start, end in meals(now.date()) if start <= now.time() < end), None)


def rested(energy: float, at: datetime) -> float:
    """Her energy at `at` with the ordinary tiredness of the hours since she woke put back: what
    is left says how the day went (a nap, a long walk), not what time it is. The night reads her
    day with this (decision 58): the plain average of a day is always below the morning's, and
    fed back night after night it sank her drive to 0.38 and stayed there."""
    up = max(0.0, (at - wake_at(at.date())).total_seconds() / 3600)
    return min(100.0, energy + ENERGY_PER_HOUR * up)
