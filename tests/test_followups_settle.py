"""What she means to ask him is asked once (2026-11-10): the same question in other words is one
follow-up, a chat that holds only her own unanswered line writes nothing new to ask, and what he
already told her is settled when the chat closes. Before, she asked for a photo on three mornings,
the last one the day after he sent it."""

import json
from datetime import datetime, timedelta

from fish.brain import Brain, FakeLLM
from fish.config import Settings
from fish.memory import ProspectiveStore
from fish.memory.prospective import same_topic
from fish.msgs import SheSaid
from fish.storage import connect
from fish.urges import Scene, about_him
from fish.mood import Mood

T0 = datetime(2027, 1, 9, 8, 0)


def chat_json(say="嗯") -> str:
    return json.dumps({"say": say, "mood": "平静", "topic": "闲聊", "notes": [], "followups": [],
                       "asked": [], "corrections": []}, ensure_ascii=False)


def make_brain(tmp_path, close: dict):
    """A brain whose chat replies are plain and whose close of a chat answers `close`."""
    conn = connect(tmp_path / "fish.db")
    settings = Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db", window_size=20)
    closes = []

    def answer(messages, json_mode):
        if messages[0]["role"] == "system":
            return chat_json()
        closes.append(messages[0]["content"])
        return json.dumps({"summary": "聊了", "gist": "聊了", "notes": [], **close}, ensure_ascii=False)

    return Brain(conn, settings, FakeLLM(answer), persona_text="你是大肥鱼。"), conn, closes


def test_one_question_in_other_words_is_one_follow_up(tmp_path):
    assert same_topic("问他驾照科目二有没有消息", "科目二那边后来有消息了吗")
    assert same_topic("演示的照片拍到了没", "问问他演示照片到底拍了没")
    assert not same_topic("期末考完去海边了吗", "问问他期末考得怎么样")
    assert not same_topic("问他今天考试考得怎么样", "问他面试怎么样")
    later = ProspectiveStore(connect(tmp_path / "fish.db"))
    assert later.add("问他驾照科目二有没有消息", "2027-01-12", now=T0) is not None
    assert later.add("科目二那边后来有消息了吗", "2027-01-15", now=T0) is None
    assert later.add("问他驾照考过了没", "2027-01-13", source_memory=7, now=T0) is not None
    assert later.add("科目二怎么样了", "2027-01-16", source_memory=7, now=T0) is None  # about the same memory


def test_her_own_unanswered_line_writes_nothing_new_to_ask(tmp_path):
    brain, conn, closes = make_brain(tmp_path, {"summary": "我问他照片拍了没，他还没回", "gist": "他还没回",
                                                "followups": [{"text": "演示的照片到底拍了没", "due": "2027-01-12"}]})
    later = ProspectiveStore(conn)
    asked = later.add("演示的照片拍了没", "2027-01-09", now=T0 - timedelta(days=2))
    brain.keep_her_line(SheSaid("演示的照片拍了没", T0, "wechat", first=True, asked=(asked.id,)))
    brain.respond("昨天不是发你了吗", "wechat", now=T0 + timedelta(hours=1))  # 30 minutes on: her line was a chat of its own
    assert len(closes) == 1 and later.open() == []  # the close's follow-up is her own question again
    first = brain.episodes.closed()[0]
    assert "没回" not in first.gist + first.summary and "演示的照片拍了没" in first.gist


def test_what_he_already_told_her_is_settled_at_the_close(tmp_path):
    brain, conn, closes = make_brain(tmp_path, {"followups_done": [1, 2, 99]})
    later = ProspectiveStore(conn)
    photo = later.add("演示的照片拍了没", "2027-01-11", now=T0)  # not due yet: nobody shows it to her in chat
    brain.respond("演示的照片给你看", "wechat", now=T0)
    brain.close_episode(brain.episodes.open_episode(), T0 + timedelta(hours=2))
    assert f"[#{photo.id}] 演示的照片拍了没" in closes[0]
    assert later.get(photo.id).status == "settled" and later.due(T0 + timedelta(days=3)) == []


def test_a_due_follow_up_says_the_day_it_was_written(tmp_path):
    conn = connect(tmp_path / "fish.db")
    ProspectiveStore(conn).add("问他今天考试考得怎么样", "2027-01-10", now=T0)
    lines = [u.line for u in about_him(Scene(conn, T0 + timedelta(days=1), Mood(50, 0, 0)))]
    assert lines == ["惦记的事到日子了（惦记 #1，1月9日记下的）：问他今天考试考得怎么样"]
