"""When she texts first (2026-11-10): not in her nap, not on the stroke of eight, and her one rice
cooker is one pot in the sink. The real chats had "醒了" at the minute she lay down and a message
at 08:00:0x every morning."""

import json
import random
from datetime import datetime, timedelta

from fish.brain import Brain, FakeLLM
from fish.brain.reach import ReachPolicy
from fish.config import Settings
from fish.cottage import Cottage
from fish.memory import ProspectiveStore, Relationship
from fish.storage import connect

MON = datetime(2026, 11, 2, 10, 0)


def home(tmp_path) -> Cottage:
    c = Cottage(tmp_path / "cottage" / "now.json")
    c.load(MON)
    return c


def test_a_nap_is_not_news_and_she_does_not_text_in_her_sleep(tmp_path):
    """11-07 and 11-08: "睡了个午觉" was written as she lay down and was a reason to text him, so at
    15:00 she texted "醒了" while the room said she slept until 16:00."""
    conn = connect(tmp_path / "fish.db")
    s = Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db", cottage=True)
    asked = []

    def respond(messages, json_mode):
        asked.append(messages[-1]["content"])
        return json.dumps({"say": "醒了", "asked": [], "shared": []}, ensure_ascii=False)

    brain = Brain(conn, s, FakeLLM(respond), persona_text="你是大肥鱼。")
    at = datetime(2026, 11, 2, 15, 0)
    brain.window.append("user", "在吗", "wechat", None, at - timedelta(hours=2))
    Relationship(conn).note_active_day(at - timedelta(hours=2))
    ProspectiveStore(conn).add("问他演示怎么样", "2026-11-02", now=at - timedelta(days=1))  # a reason is there
    brain.cottage.load(at)
    assert brain.cottage.act("nap", at).lines == ["躺下睡午觉了"]
    assert brain.home_lately(at + timedelta(minutes=1)) == [] and brain.room.napping(at + timedelta(minutes=1))
    assert brain.consider_reach_out(at + timedelta(minutes=1)) is None and asked == []
    assert brain.consider_reach_out(at + timedelta(minutes=59)) is None  # every poll of the nap puts the thought off
    assert brain.cottage.advance(at + timedelta(minutes=61)).lines == ["午觉睡醒了"]
    assert brain.home_lately(at + timedelta(minutes=62)) == [] and not brain.room.napping(at + timedelta(minutes=62))
    assert brain.consider_reach_out(at + timedelta(minutes=62)) is None  # not on the second she wakes
    assert brain.consider_reach_out(at + timedelta(minutes=125)).text == "醒了"  # awake, and the follow-up is due


def test_the_first_thought_of_the_day_is_not_on_the_stroke_of_eight(tmp_path):
    """Every morning she texted at 08:00:0x: the gate had stood open since last night."""
    conn = connect(tmp_path / "fish.db")
    policy = ReachPolicy(conn, rng=random.Random(1))
    eight = datetime(2026, 11, 3, 8, 0, 7)
    Relationship(conn).set("reach_next_think", "2026-11-02T21:10:00", eight)
    Relationship(conn).set("reach_think_base", "2026-11-02T20:40:00", eight)
    conn.execute("INSERT INTO messages (ts, role, text, channel) VALUES ('2026-11-02T20:00:00', 'user', '晚安', 'wechat')")
    conn.commit()
    assert policy.refused(eight) == "not yet"
    assert policy.refused(eight.replace(minute=19)) == "not yet" and policy.refused(eight.replace(hour=9, minute=1)) is None


def test_she_has_one_rice_cooker(tmp_path):
    c = home(tmp_path)
    for day in range(3):
        c.act("rice", MON + timedelta(days=day, hours=1))
        c.advance(MON + timedelta(days=day, hours=3))
    assert c.load(MON + timedelta(days=3)).sink == ["电饭煲内胆"]


def test_a_home_event_in_the_minute_of_a_thought_is_offered_once(tmp_path):
    conn = connect(tmp_path / "fish.db")
    policy = ReachPolicy(conn, rng=random.Random(1))
    first, second = datetime(2026, 11, 3, 10, 0, 7), datetime(2026, 11, 3, 10, 48, 37)
    assert policy.fresh(["10:00 青菜放坏了，扔了"], first) == ["10:00 青菜放坏了，扔了"]
    policy.record_considered(first, ["10:00 青菜放坏了，扔了"])
    # the same line again, and one the room wrote later in that same minute
    assert policy.fresh(["10:00 青菜放坏了，扔了", "10:00 小葱蔫了"], second) == ["10:00 小葱蔫了"]
