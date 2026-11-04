"""His status (decision 51): she can see where he is, how they are talking and what he says he
is up to; and with him in her room she talks to him, she does not text him."""

import json
from datetime import datetime, timedelta

from fish.__main__ import main
from fish.brain import Brain, FakeLLM
from fish.brain.prompt import FACE_NOW
from fish.config import Settings
from fish.cottage import Cottage
from fish.messages import Incoming
from fish.storage import connect

MON = datetime(2026, 11, 2, 18, 0)  # a Monday
TEXTING = "像年轻人发微信"
TALKING = "这是当面说话"


def home(tmp_path) -> Cottage:
    c = Cottage(tmp_path / "cottage" / "now.json")
    c.load(MON)
    return c


def make_brain(tmp_path, *replies):
    """A brain whose model answers with `replies` in turn; `prompts` collects each turn's messages."""
    conn = connect(tmp_path / "fish.db")
    s = Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db", cottage=True)
    left = iter(replies)
    prompts = []

    def respond(messages, json_mode):
        last = messages[-1]["content"] if isinstance(messages[-1]["content"], str) else ""
        if "你是检查员" in last:
            return json.dumps({"ok": True})
        if messages[0]["role"] != "system":  # the close of a chat that went quiet, and such
            return json.dumps({"summary": "聊了", "gist": "聊了", "notes": []}, ensure_ascii=False)
        prompts.append(messages)
        return json.dumps(next(left), ensure_ascii=False)

    return Brain(conn, s, FakeLLM(respond), persona_text="你是大肥鱼。"), prompts


def test_away_she_knows_it_is_by_phone(tmp_path):
    status = home(tmp_path).him_status(MON)
    assert not status.together
    assert "他不在你这儿" in status.text and "手机上发消息" in status.text


def test_coming_later_is_still_by_phone(tmp_path):
    c = home(tmp_path)
    c.expect(MON.replace(hour=16), MON, MON.replace(hour=21), "吃晚饭")
    status = c.him_status(MON.replace(hour=16))
    assert not status.together and "他说 18:00 过来" in status.text and "手机上发消息" in status.text


def test_in_her_room_it_is_face_to_face(tmp_path):
    c = home(tmp_path)
    c.expect(MON, why="吃晚饭")
    status = c.him_status(MON)
    assert status.together
    assert "他这会儿就在你屋里" in status.text and "当面说话" in status.text


def test_when_she_goes_out_he_is_in_her_room_but_it_is_by_phone_again(tmp_path):
    """He stays while she walks to the pier: they can't be talking across the room."""
    c = home(tmp_path)
    c.expect(MON)
    assert c.act("lake", MON) is not None
    status = c.him_status(MON + timedelta(minutes=5))
    assert not status.together
    assert "他这会儿就在你屋里" in status.text and "你这会儿不在屋里" in status.text and "手机上发消息" in status.text
    c.advance(MON + timedelta(hours=1))  # she is back
    assert c.him_status(MON + timedelta(hours=1)).together


def test_what_he_is_up_to_goes_stale_and_ends_when_he_moves(tmp_path):
    c = home(tmp_path)
    c.he_is_doing("在图书馆", MON)
    assert "在干嘛：在图书馆（18:00 他说的）" in c.him_status(MON + timedelta(hours=1)).text
    assert "在干嘛" not in c.him_status(MON + timedelta(hours=3)).text  # noon's library says nothing about tonight
    c.expect(MON + timedelta(minutes=30))  # he came over: he is not in the library now
    assert "在干嘛" not in c.him_status(MON + timedelta(minutes=31)).text
    c.he_is_doing("躺在沙发上", MON + timedelta(minutes=40))
    assert "躺在沙发上" in c.him_status(MON + timedelta(minutes=41)).text
    c.send_off(MON + timedelta(minutes=50))
    assert "沙发" not in c.him_status(MON + timedelta(minutes=51)).text
    assert all("沙发" not in e["line"] for e in c.load(MON).events)  # not news from her house


def test_a_room_file_from_before_this_still_loads(tmp_path):
    c = home(tmp_path)
    c.save(c.load(MON))
    data = json.loads(c.path.read_text(encoding="utf-8"))
    del data["him"]
    c.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert "他不在你这儿" in c.him_status(MON).text


def test_the_prompt_changes_from_texting_to_talking_and_back(tmp_path):
    brain, prompts = make_brain(tmp_path, {"say": "门没锁", "guest": "arrive"}, {"say": "你坐"}, {"say": "到了说一声", "guest": "leave"},
                                {"say": "嗯"})
    brain.album.add(b"\x89PNG", "image/png", "狗头", now=MON)
    brain.respond("我到你家门口了", now=MON)
    brain.respond("饭好了没", now=MON + timedelta(minutes=5))
    brain.respond("我先回去了", now=MON + timedelta(hours=1))
    brain.respond("到学校了", now=MON + timedelta(hours=2))

    before, face, leaving, after = (p[0]["content"] for p in prompts)
    assert TEXTING in before and TALKING not in before and "## 他的状态" in before
    assert TALKING in face and TEXTING not in face and "他这会儿就在你屋里" in face
    assert face.count("他这会儿就在你屋里（") == 1  # shown as his status, not among the room's lines again
    assert "用手机回他" not in face and "用手机回他" in before
    assert TEXTING in after and TALKING not in after and "他不在你这儿" in after
    assert TALKING in leaving  # goodbye is still said to his face


def test_face_to_face_there_are_no_stickers(tmp_path):
    """Not offered, no word about having none, and one she names anyway is not sent."""
    brain, prompts = make_brain(tmp_path, {"say": "嗯", "guest": "arrive"}, {"say": "你坐", "sticker": 1})
    assert brain.album.add(b"\x89PNG", "image/png", "狗头", now=MON).id == 1
    brain.respond("我进来了", now=MON)
    assert "## 你的表情包" in prompts[0][0]["content"]  # still at the door: still by phone
    out = brain.handle(Incoming("你看", None), now=MON + timedelta(minutes=1))
    system = prompts[-1][0]["content"]
    assert out.sticker is None
    assert "## 你的表情包" not in system and "你爱发表情包" not in system and "你还没有表情包" not in system


def test_said_to_her_face_is_said_at_his_line_but_never_kept(tmp_path):
    brain, prompts = make_brain(tmp_path, {"say": "嗯", "guest": "arrive"}, {"say": "你坐"})
    brain.respond("我进来了", now=MON)
    brain.respond("坐哪", now=MON + timedelta(minutes=1))
    assert FACE_NOW in prompts[-1][-1]["content"]
    assert FACE_NOW not in prompts[0][-1]["content"]
    stored = [r["text"] for r in brain.conn.execute("SELECT text FROM messages")]
    assert "坐哪" in stored and not any(FACE_NOW in t for t in stored)


def test_her_reply_keeps_what_he_says_he_is_up_to(tmp_path):
    brain, prompts = make_brain(tmp_path, {"say": "你倒是舒服", "guest": "arrive", "he_doing": "躺在沙发上"}, {"say": "嗯"})
    brain.respond("（推门进来，躺到沙发上）", now=MON)
    brain.respond("真舒服", now=MON + timedelta(minutes=1))
    assert "在干嘛：躺在沙发上（18:00 他说的）" in prompts[-1][0]["content"]


def test_a_broken_room_file_leaves_his_status_out(tmp_path):
    brain, prompts = make_brain(tmp_path, {"say": "嗯"})
    brain.cottage.path.parent.mkdir(parents=True)
    brain.cottage.path.write_text("{ 床: 乱", encoding="utf-8")
    assert brain.respond("在吗", now=MON) == "嗯"
    assert "## 他的状态" not in prompts[-1][0]["content"]


def test_fish_me_shows_and_sets_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FISH_DB_PATH", str(tmp_path / "fish.db"))
    main(["me"])
    assert "他不在她这儿" in capsys.readouterr().out
    main(["me", "在她", "沙发上躺着"])
    out = capsys.readouterr().out
    assert "在她 沙发上躺着" in out and "他说的" in out
