"""No two of her days run on the same clock (decision 59): bedtime, getting up, meals and her
free moments are drawn day by day; her mood is told in steps and in more than one wording; a
chat she enjoys keeps her up a little."""

from datetime import date, datetime, time, timedelta

import pytest

from fish.brain.leisure import pace
from fish.cottage import Cottage, asleep_hours, hours
from fish.cottage.rules import ENERGY_PER_HOUR
from fish.mood import Mood, MoodStore

DAYS = [date(2027, 3, 1) + timedelta(days=i) for i in range(60)]  # 2027-03-01 is a Monday

pytestmark = pytest.mark.drawn_hours


def test_each_day_draws_its_own_hours_and_keeps_them():
    wakes = {hours.wake_at(d).time() for d in DAYS}
    beds = {hours.bed_at(d).time() for d in DAYS}
    lunches = {hours.meals(d)[0][1] for d in DAYS}
    assert len(wakes) > 20 and len(beds) > 15 and len(lunches) > 15
    assert all(time(7, 40) <= hours.wake_at(d).time() <= time(9, 10) for d in DAYS)
    assert all(hours.bed_at(d).time() <= time(0, 45) for d in DAYS)
    assert all(time(11, 30) <= hours.meals(d)[0][1] <= time(12, 10) and hours.meals(d)[0][2] == time(13, 30)
               for d in DAYS)
    assert hours.wake_at(DAYS[3]) == hours.wake_at(DAYS[3])  # asked twice: the same day
    weekdays = [hours.wake_at(d) - datetime.combine(d, time(8)) for d in DAYS if d.weekday() < 5]
    weekends = [hours.wake_at(d) - datetime.combine(d, time(8)) for d in DAYS if d.weekday() >= 5]
    assert sum(weekends, timedelta()) / len(weekends) > sum(weekdays, timedelta()) / len(weekdays)  # a lie-in


def test_she_is_asleep_between_that_days_bedtime_and_getting_up():
    d = DAYS[0]
    bed, up = hours.bed_at(d), hours.wake_at(d)
    assert not asleep_hours(bed - timedelta(minutes=1)) and asleep_hours(bed) and asleep_hours(up - timedelta(minutes=1))
    assert not asleep_hours(up) and hours.woke(up + timedelta(hours=3)) == up
    assert hours.woke(up - timedelta(hours=1)) == hours.wake_at(d - timedelta(days=1))


def test_the_room_sleeps_wakes_and_eats_by_the_days_own_hours(tmp_path):
    d = DAYS[1]
    c = Cottage(tmp_path / "now.json")
    c.load(datetime.combine(d - timedelta(days=1), time(22, 0)))
    up = hours.wake_at(d)
    c.advance(up - timedelta(minutes=5))
    assert c.load().doing == "睡觉"
    change = c.advance(up + timedelta(minutes=1))
    assert c.load().doing == "" and change.slept == [(hours.bed_at(d), up)]
    lunch = datetime.combine(d, hours.meals(d)[0][1])
    c.advance(lunch - timedelta(minutes=2))
    assert not any(m.endswith("午饭") for m in c.load().meals)
    c.advance(lunch + timedelta(minutes=1))
    assert c.load().meals[-1] == f"{d.isoformat()} 午饭"
    # the hours awake tire her from when she really got up
    assert hours.rested(50.0, up + timedelta(hours=2)) == 50.0 + 2 * ENERGY_PER_HOUR


def test_free_time_is_not_the_same_every_day():
    counts = [pace.moments_on(d, 3) for d in DAYS]
    assert set(counts) == {2, 3, 4} and abs(sum(counts) / len(counts) - 3) < 0.35  # the same on average
    assert pace.moments_on(DAYS[0], 0) == 0 and all(pace.moments_on(d, 1) >= 1 for d in DAYS)
    gaps = [pace.gap_on(d) for d in DAYS]
    assert min(gaps) >= timedelta(hours=2) and max(gaps) <= timedelta(hours=4) and len(set(gaps)) > 50
    assert all(time(9, 0) <= pace.starts_on(d) <= time(10, 0) for d in DAYS) and len({pace.starts_on(d) for d in DAYS}) > 15


def test_her_mood_is_told_in_steps_and_in_more_than_one_way():
    said = {e: Mood(e, 0, 0).describe() for e in range(0, 101)}
    assert said[60] == "状态一般" and ("精神" in said[90] or "劲头" in said[90])
    assert all("不太想打字" not in said[e] and "懒得说" not in said[e] and "睡着" not in said[e] for e in range(15, 101))
    assert len({said[e] for e in range(0, 15)}) == 3 and len({said[e] for e in range(15, 30)}) == 3
    assert said[35] != "状态一般" and said[35] != said[20] != said[5]  # a little tired is not sleepy is not gone
    assert Mood(60, 0, 60).describe() != "状态一般" and Mood(60, 0, 90).describe() != Mood(60, 0, 75).describe()
    assert Mood(60, 85, 0).describe() != Mood(60, 65, 0).describe()


def test_a_chat_she_enjoys_keeps_her_up_a_little():
    flat = MoodStore.after_turn(Mood(40, 20, 40), "嗯", "嗯", reported="平静", kitchen=True)
    glad = MoodStore.after_turn(Mood(40, 20, 40), "哈哈", "笑死", reported="开心", kitchen=True)
    assert flat.energy == 40 and 40 < glad.energy <= 41
