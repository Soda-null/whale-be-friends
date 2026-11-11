"""Something of his from a while back crosses her mind (decision 58): one thing, the same one
all day, a reason to text him once; not every day, never a promise or what already ended."""

from datetime import datetime, timedelta

from fish.brain.reach import ReachPolicy
from fish.memory import MemoryStore, old_things
from fish.mood import Mood
from fish.storage import connect
from fish.urges import Scene, about_him
from fish.urges.him import old_day
from fish.urges.rules import OLD_AFTER_DAYS, OLD_CHANCE, OLD_IMPORTANCE

DAYS = [datetime(2027, 3, 1, 15, 0) + timedelta(days=i) for i in range(300)]
DAY = next(d for d in DAYS if old_day(d.toordinal()) and not old_day(d.toordinal() + 1))
LONG_AGO = DAY - timedelta(days=20)


def olds(conn, now):
    return [u for u in about_him(Scene(conn, now, Mood(50, 0, 0))) if u.source == "old"]


def test_an_old_thing_of_his_is_a_reason_once(tmp_path):
    conn = connect(tmp_path / "fish.db")
    store = MemoryStore(conn)
    race = store.add("event", "他报了四月的半程马拉松", importance=6, now=LONG_AGO)
    store.add("event", "他中午吃了牛肉面", importance=2, now=LONG_AGO)  # too small to come back to
    store.add("event", "他昨天搬了宿舍", importance=6, now=DAY - timedelta(days=1))  # not old
    (u,) = olds(conn, DAY)
    assert u.ref.id == race.id and "半程马拉松" in u.line and "记下的" in u.line
    assert olds(conn, DAY + timedelta(hours=3))[0].ref.id == race.id  # the same thought all day
    assert olds(conn, DAY + timedelta(days=1)) == []  # not every day
    such = [old_day(d.toordinal()) for d in DAYS]
    assert abs(sum(such) / len(such) - OLD_CHANCE) < 0.1  # about one day in three
    assert "".join("x" if x else "." for x in such[:60]).count("x..x..x..x") == 0  # and on no calendar
    policy = ReachPolicy(conn)
    assert policy.once_key(u) == f"old:{race.id}"
    policy.record_considered(DAY, once=[policy.once_key(u)])
    assert [x for x in policy.triggers(DAY + timedelta(hours=1), Mood(50, 0, 0)).urges if x.source == "old"] == []


def test_what_ended_or_was_thought_of_lately_does_not_come_back(tmp_path):
    store = MemoryStore(connect(tmp_path / "fish.db"))
    done = store.add("event", "他去考了驾照科目二", importance=6, now=LONG_AGO)
    lately = store.add("event", "他在准备研究生复试", importance=6, now=LONG_AGO)
    open_ = store.add("event", "他说想学吉他", importance=5, now=LONG_AGO)
    store.set_outcome(done.id, "过了", DAY - timedelta(days=10))
    store.touch(lately.id, DAY - timedelta(days=2))
    found = old_things(store, DAY, after_days=OLD_AFTER_DAYS, importance=OLD_IMPORTANCE)
    assert [m.id for m in found] == [open_.id]
