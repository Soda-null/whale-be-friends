"""An ordinary day does not wear her drive down (decision 58). With her cottage every awake hour
tires her, so the plain average of a day's energy is always below the morning's; fed back each
night it sank her drive to 0.38 ("有点蔫") in a week and held it there, and from mid-afternoon she
was told she was too sleepy to type. The night now reads the day with the hour taken out."""

from datetime import datetime, timedelta

import pytest

from fish.cottage import rested
from fish.cottage.rules import ENERGY_PER_HOUR
from fish.memory import PhaseStore
from fish.mood import Mood, MoodStore
from fish.storage import connect

DAY = datetime(2027, 3, 1)


def ordinary_day(store: MoodStore, day: datetime, morning: float) -> None:
    """A turn every two hours from nine to eleven at night; nothing but time moves her."""
    for hour in range(9, 24, 2):
        store.log(Mood(morning - ENERGY_PER_HOUR * (hour - 8), 20, 40), "平静", day.replace(hour=hour))


def test_the_hour_of_day_is_taken_out_of_her_energy():
    assert rested(40.0, DAY.replace(hour=8)) == 40.0
    assert rested(40.0, DAY.replace(hour=18)) == 40.0 + 10 * ENERGY_PER_HOUR
    assert rested(95.0, DAY.replace(hour=20)) == 100.0


def test_ordinary_days_leave_her_drive_where_her_mornings_are(tmp_path):
    conn = connect(tmp_path / "fish.db")
    moods, phases = MoodStore(conn), PhaseStore(conn)
    plain, read = [], []
    for i in range(30):
        day = DAY + timedelta(days=i)
        morning = 30 + 60 * phases.current().drive  # where she wakes (MoodStore.rest)
        ordinary_day(moods, day, morning)
        _, raw = moods.day_tone(day, day + timedelta(days=1))
        _, without_hours = moods.day_tone(day, day + timedelta(days=1), rested=rested)
        plain.append(raw)
        read.append(without_hours)
        assert without_hours == pytest.approx(morning)  # the day is read as the morning it began with
        phases.update(day.date().isoformat(), tone_today=0.1, drive_today=without_hours / 100)
    assert all(r < m - 15 for r, m in zip(plain, read))  # the plain average: every day reads as a tired one
    assert phases.current().drive >= 0.6 and phases.current().drive_word != "有点蔫"
