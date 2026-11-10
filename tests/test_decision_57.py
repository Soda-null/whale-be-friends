"""Decision 57: she has more reasons to text him than chores (a sight of middling importance, his
long silence), each offered at one thought only; a note at his line when he is hurting; one piece
of news noted twice in one chat is one memory."""

import json
from datetime import datetime, timedelta

from fish.brain import Brain, FakeLLM
from fish.brain.closing import ACK_NOTE
from fish.brain.comfort import COMFORT_NOTE, comfort_note
from fish.brain.parse import clean_say
from fish.brain.reach import ReachPolicy
from fish.config import Settings
from fish.memory import MemoryStore
from fish.mood import Mood
from fish.storage import connect
from fish.urges import Scene, about_him

NOON = datetime(2027, 1, 9, 12, 0)
CALM = Mood(energy=70, boredom=10, hunger=20)


def he_wrote(conn, at):
    conn.execute("INSERT INTO messages (ts, role, text, channel) VALUES (?, 'user', '在吗', 'wechat')", (at.isoformat(),))
    conn.commit()


def test_a_sight_of_three_is_worth_telling_and_long_quiet_bores_her(tmp_path):
    conn = connect(tmp_path / "fish.db")
    he_wrote(conn, NOON - timedelta(hours=2))
    MemoryStore(conn).add("world", "有人在冰层底下潜水", importance=3, source="https://x", now=NOON - timedelta(hours=1))
    MemoryStore(conn).add("world", "一条没意思的", importance=2, source="https://y", now=NOON - timedelta(hours=1))
    assert [u.source for u in about_him(Scene(conn, NOON, CALM))] == ["seen"]
    # 10 of 100 bored by herself: seven quiet hours do the rest
    assert [u.source for u in about_him(Scene(conn, NOON + timedelta(hours=3), CALM))] == ["seen"]
    assert [u.source for u in about_him(Scene(conn, NOON + timedelta(hours=5), CALM))] == ["seen", "bored"]


def test_a_sight_and_boredom_are_offered_at_one_thought_each(tmp_path):
    conn = connect(tmp_path / "fish.db")
    he_wrote(conn, NOON - timedelta(hours=7))
    MemoryStore(conn).add("world", "有人在冰层底下潜水", importance=3, source="https://x", now=NOON - timedelta(hours=1))
    policy = ReachPolicy(conn)
    first = policy.triggers(NOON, CALM)
    assert [u.source for u in first.urges] == ["seen", "bored"]
    policy.record_considered(NOON, once=[k for k in map(policy.once_key, first.urges) if k])  # she said no
    assert policy.triggers(NOON + timedelta(minutes=40), CALM).urges == []
    he_wrote(conn, NOON + timedelta(hours=1))  # he writes, then goes quiet again: she may get bored again
    assert [u.source for u in policy.triggers(NOON + timedelta(hours=8), CALM).urges] == ["bored"]


def test_he_is_hurting_is_said_at_his_line_before_only_a_nod(tmp_path):
    for his in ("我好郁闷", "被赶走的感觉很难受", "说出那两个字的时候差点哭出来", "他们会后悔的 气死我了", "[表情：大哭]", "sb"):
        assert comfort_note(his) == COMFORT_NOTE, his
    for his in ("不难受了", "没那么郁闷了哈哈", "今天挺开心的", "嗯嗯", "操场跑了三圈", "usb 坏了"):
        assert comfort_note(his) == "", his
    assert clean_say("在呢\n" + COMFORT_NOTE) == "在呢"
    conn = connect(tmp_path / "fish.db")
    s = Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db", window_size=20)
    llm = FakeLLM(lambda messages, json_mode: json.dumps({"say": "在呢"}, ensure_ascii=False))
    brain = Brain(conn, s, llm, persona_text="你是大肥鱼。")
    brain.respond("[表情：大哭]", now=NOON)
    last = llm.calls[-1][0][-1]["content"]
    assert COMFORT_NOTE in last and ACK_NOTE not in last
    assert not any("（" in t.text for t in brain.window.recent())


def test_one_piece_of_news_noted_twice_in_a_chat_is_one_memory(tmp_path):
    store = MemoryStore(connect(tmp_path / "fish.db"))
    first = store.note("event", "他2027-01-09说学校把交换从一年改成了半年，年底就得回国", importance=5, about="日常",
                       source_episode=3, now=NOON, heard="chat")
    twin = store.note("fact", "他说学校把交换从一年改成了半年，年底就得回国", importance=5, about="日常",
                      source_episode=3, now=NOON + timedelta(minutes=2), heard="chat")
    assert twin.id == first.id and first.times == store.get(first.id).times == 1  # said once: not "好几回"
    # more of it (a date) is news; another chat is another telling; a different thing stays
    more = store.note("fact", "他说学校把交换从一年改成了半年，12月31日的机票回国", importance=5, about="日常",
                      source_episode=3, now=NOON + timedelta(minutes=5), heard="chat")
    other = store.note("fact", "他说学校把交换从一年改成了半年，年底就得回国", importance=5, about="日常",
                       source_episode=4, now=NOON + timedelta(days=1), heard="chat")
    food = store.note("event", "他2027-01-09中午吃了红烧牛肉面", importance=3, about="路过", source_episode=3,
                      now=NOON, heard="chat")
    assert len({first.id, more.id, other.id, food.id}) == 4
