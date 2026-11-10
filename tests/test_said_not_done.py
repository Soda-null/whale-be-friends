"""Saying she is off to do a chore while she cannot start it (2026-11-10). Walking back from the
flower shop she said "这就去喂" three times and no fish was fed: the room refused in silence. Now she
is told nothing else can start, and the checker is told when a chore she named did not."""

import json
from datetime import datetime, timedelta

from fish.brain import Brain, FakeLLM
from fish.config import Settings
from fish.storage import connect

MON = datetime(2026, 11, 2, 10, 0)


def test_a_chore_the_room_refused_is_cut_from_her_line(tmp_path):
    conn = connect(tmp_path / "fish.db")
    s = Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db", cottage=True)
    checks, chats = [], []

    def respond(messages, json_mode):
        last = messages[-1]["content"]
        if "你是检查员" in last:
            checks.append(last)
            return json.dumps({"ok": False, "fixed": "在码头呢", "why": "叠被子没开始"}, ensure_ascii=False)
        chats.append(messages[0]["content"])
        return json.dumps({"say": "在码头呢\n我这就去叠被子", "mood": "平静", "topic": "家务", "do": "bed"},
                          ensure_ascii=False)

    brain = Brain(conn, s, FakeLLM(respond), persona_text="你是大肥鱼。")
    brain.cottage.load(MON)
    assert brain.room.act("lake", MON)  # she is out on the pier for half an hour
    said = brain.respond("被子叠了没", "wechat", now=MON + timedelta(minutes=5))
    assert "这件事没完之前，屋里别的事开始不了" in chats[-1]
    assert checks[-1].count("这一轮她说要去做「叠被子」，屋里没让她开始") == 1
    events = [e["line"] for e in brain.cottage.load(MON + timedelta(minutes=6)).events]
    assert said == "在码头呢" and events == ["出门去湖边码头坐一会儿"]
    assert brain.home_fixes[-1]["why"] == "叠被子没开始"
