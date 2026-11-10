"""Two notes said right at his line (2026-11-10): his line is only a nod or a goodbye
(brain/closing.py), and how long ago the last line of today's chat was (brain/gap.py). Also that
WeChat's emoji codes reach her as what the face shows (channels/emoji.py)."""

import json
from datetime import datetime, timedelta

from fish.brain import Brain, FakeLLM
from fish.brain.closing import ACK_NOTE, BYE_NOTE, closing_note
from fish.brain.gap import gap_note
from fish.brain.prompt import HOME_WORDS
from fish.channels.emoji import FACES, readable
from fish.config import Settings
from fish.storage import connect

T0 = datetime(2027, 1, 9, 9, 20)


def test_a_nod_is_a_nod_and_an_answer_is_an_answer():
    for his in ("嗯嗯", "哈哈好的好的", "okok", "是的诶", "[表情：狗头，在开玩笑]", "[Doge][Doge]", "好滴～", "👌"):
        assert closing_note(his, "去吧\n学累了歇会") == ACK_NOTE, his
    for his in ("拜拜～", "嗯嗯那晚安吧好的好的", "先下了哈"):
        assert closing_note(his, "去吧") == BYE_NOTE, his
    # he answers what she asked: not a nod
    assert closing_note("是的", "那今晚还学不学") == "" and closing_note("可以", "周末来吗") == ""
    assert closing_note("晚安", "明天几点起？") == BYE_NOTE  # a goodbye is one whatever she asked
    for his in ("演示过了", "我去", "好的 我明天考试", "吃啦吃啦", "为啥", "嗯？", "[图片]", "[文件：作业.pdf]", ""):
        assert closing_note(his, "去吧") == "", his


def test_the_gap_is_said_in_words_only_when_it_is_long():
    assert gap_note(None, T0) == "" and gap_note(T0 - timedelta(minutes=29), T0) == ""
    assert "过了45 分钟" in gap_note(T0 - timedelta(minutes=45), T0)
    assert "过了3 个多小时" in gap_note(T0 - timedelta(hours=3, minutes=30), T0)
    assert "过了2 个小时" in gap_note(T0 - timedelta(hours=2, minutes=3), T0)


def test_both_notes_stand_at_his_line_and_are_not_stored(tmp_path):
    conn = connect(tmp_path / "fish.db")
    s = Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db", window_size=20)
    llm = FakeLLM(lambda messages, json_mode: json.dumps({"say": "去吧", "mood": "平静", "topic": "上课"},
                                                         ensure_ascii=False))
    brain = Brain(conn, s, llm, persona_text="你是大肥鱼。")
    brain.respond("我上课去了", now=T0)
    brain.respond("嗯嗯", now=T0 + timedelta(minutes=1))
    last = llm.calls[-1][0][-1]["content"]
    assert last.startswith("嗯嗯\n" + ACK_NOTE) and "已经过了" not in last
    brain.respond("下课了，老师拖堂", now=T0 + timedelta(minutes=25))  # same chat, 24 minutes on: no gap said
    assert "已经过了" not in llm.calls[-1][0][-1]["content"] and ACK_NOTE not in llm.calls[-1][0][-1]["content"]
    brain.respond("我回来了", now=T0 + timedelta(hours=4))  # a new chat: the old lines are hours old
    last = llm.calls[-1][0][-1]["content"]
    assert last.startswith("我回来了\n（离上面最后一句话已经过了3 个多小时") and last.rstrip().endswith("）")
    stored = [t.text for t in brain.window.recent()]
    assert "嗯嗯" in stored and not any("（" in t for t in stored)


def test_wechat_faces_become_what_they_show():
    assert readable("[Doge][Doge]") == "[表情：狗头，在开玩笑][表情：狗头，在开玩笑]"
    assert readable("哈哈[Sob] 伤心") == "哈哈[表情：大哭] 伤心"
    assert readable("[图片]") == "[图片]" and readable("[TODO] 明天交") == "[TODO] 明天交"
    assert readable("[表情包：比心]") == "[表情包：比心]"
    assert not any(HOME_WORDS.search(words) for words in FACES.values())  # a face is never a question about her room
