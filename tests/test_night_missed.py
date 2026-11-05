"""A night the model failed: try again, leave a trace, make up for it the next night (decision 53)."""

import json
from datetime import date, datetime

from fish.brain import Brain, FakeLLM
from fish.brain.consolidate import ASK_TRIES, Consolidator
from fish.config import Settings
from fish.memory import Diary, EpisodeManager, MemoryStore
from fish.routines import problems, run_nightly
from fish.routines.night.missed import days_without_diary, last_night_failed
from fish.routines.runs import last_run
from fish.storage import connect

FIRST_NIGHT = datetime(2026, 10, 27, 3, 30)  # closes 10-26
SECOND_NIGHT = datetime(2026, 10, 28, 3, 30)  # closes 10-27
PLENTY = 500.0  # GB free: the disk is not what these tests are about


class Model:
    """Answers the night's prompts; `down` is the set of prompt words it fails on."""

    def __init__(self):
        self.down: set[str] = set()
        self.calls: list[str] = []

    def __call__(self, messages, json_mode):
        content = messages[-1]["content"]
        self.calls.append(content)
        if any(word in content for word in self.down):
            raise TimeoutError("the model did not answer")
        if "你在写日记" in content:
            day = content.split("今天是 ")[1][:10]
            return json.dumps({"diary": f"{day} 的日记", "self_notes": [{"text": "我想数米粒", "importance": 4}]},
                              ensure_ascii=False)
        if "想看出点规律" in content:
            return json.dumps({"insights": [{"text": "他爱吃面", "importance": 6}]}, ensure_ascii=False)
        if "这次和他的聊天结束了" in content:
            return json.dumps({"summary": "聊了面", "gist": "聊了面", "importance": 5, "valence": 0, "notes": [],
                               "followups": []}, ensure_ascii=False)
        return json.dumps({"merges": [], "updates": [], "rewrites": []})


def make(tmp_path):
    model = Model()
    conn = connect(tmp_path / "fish.db")
    settings = Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db")
    return conn, Brain(conn, settings, FakeLLM(model), persona_text="你是大肥鱼。"), model


def chatted(conn, at: datetime, gist="聊了面"):
    em = EpisodeManager(conn)
    ep = em.start("wechat", at)
    conn.execute("INSERT INTO messages (ts, role, text, channel, episode_id) VALUES (?, 'user', '吃了吗', 'wechat', ?)",
                 (at.isoformat(), ep.id))
    conn.commit()
    em.close(ep.id, summary=gist, gist=gist, importance=5, valence=0.0, now=at)


def test_a_call_that_fails_once_is_tried_again_and_not_counted():
    replies = iter([TimeoutError("slow"), "不是 json", json.dumps({"diary": "好了"})])

    def respond(messages, json_mode):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    thinker = Consolidator(FakeLLM(respond), "你是大肥鱼。")
    assert thinker.diary("2026-10-26", "平静", [], [], "")[0] == "好了"
    assert thinker.failed == []


def test_when_the_model_stays_down_the_rest_of_the_night_tries_once(capsys):
    llm = FakeLLM(lambda m, j: (_ for _ in ()).throw(TimeoutError("down")))
    thinker = Consolidator(llm, "你是大肥鱼。")
    assert thinker.diary("2026-10-26", "平静", [], [], "")[0] == ""
    assert len(llm.calls) == ASK_TRIES
    assert thinker.letter("2026-10-26", "平静", [], [], "日记") == ""
    assert len(llm.calls) == ASK_TRIES + 1
    assert thinker.failed == ["diary", "letter"]
    assert "diary failed after 3 tries: TimeoutError: down" in capsys.readouterr().err


def test_a_lost_diary_is_written_the_next_night_in_order_and_says_so(tmp_path):
    conn, brain, model = make(tmp_path)
    chatted(conn, datetime(2026, 10, 26, 20, 0))
    model.down = {"你在写日记"}
    report = run_nightly(conn, FIRST_NIGHT, brain=brain, export_path=tmp_path / "n.md")
    assert report["failed"] == ["diary"]
    assert Diary(conn).get("2026-10-26") == ""
    assert last_night_failed(conn) == (date(2026, 10, 26), {"diary"})
    said = problems(conn, tmp_path, datetime(2026, 10, 27, 12, 0), disk_free_gb=PLENTY)
    assert any("没做成：日记" in line for line in said)
    assert any("还缺这几天的日记：2026-10-26" in line for line in said)

    model.down = set()
    chatted(conn, datetime(2026, 10, 27, 20, 0))
    report = run_nightly(conn, SECOND_NIGHT, brain=brain, export_path=tmp_path / "n.md")
    assert report["caught_up"] == ["2026-10-26"]
    assert "failed" not in report
    assert Diary(conn).get("2026-10-26") == "2026-10-26 的日记"
    assert Diary(conn).get("2026-10-27") == "2026-10-27 的日记"
    tonight = next(c for c in model.calls if "今天是 2026-10-27" in c)
    assert "2026-10-26 的日记" in tonight  # tonight's "yesterday" is the one just made up
    assert problems(conn, tmp_path, datetime(2026, 10, 28, 12, 0), disk_free_gb=PLENTY) == []


def test_catching_up_leaves_her_threads_alone(tmp_path):
    conn, brain, model = make(tmp_path)
    chatted(conn, datetime(2026, 10, 26, 20, 0))
    model.down = {"你在写日记"}
    run_nightly(conn, FIRST_NIGHT, brain=brain, export_path=tmp_path / "n.md")
    model.down = set()
    report = run_nightly(conn, SECOND_NIGHT, brain=brain, export_path=tmp_path / "n.md")
    assert report["caught_up"] == ["2026-10-26"]
    assert len(MemoryStore(conn).alive("self")) == 1  # tonight's diary adds one; the made-up one adds none
    made_up = next(c for c in model.calls if "今天是 2026-10-26" in c and "（那天的心情记不太清了）" in c)
    assert "聊了面" in made_up


def test_a_failed_look_back_does_not_count_as_done(tmp_path):
    conn, brain, model = make(tmp_path)
    chatted(conn, datetime(2026, 10, 26, 20, 0))
    model.down = {"想看出点规律"}
    assert run_nightly(conn, FIRST_NIGHT, brain=brain, export_path=tmp_path / "n.md")["failed"] == ["reflect"]
    assert last_run(conn, "reflect") is None
    model.down = set()
    assert run_nightly(conn, SECOND_NIGHT, brain=brain, export_path=tmp_path / "n.md")["insights"] == 1
    assert last_run(conn, "reflect") == "2026-10-27"


def test_only_a_week_is_looked_back_and_quiet_days_need_no_diary(tmp_path):
    conn, _, _ = make(tmp_path)
    chatted(conn, datetime(2026, 10, 10, 20, 0))  # too long ago
    chatted(conn, datetime(2026, 10, 25, 20, 0))
    Diary(conn).write("2026-10-25", "写了")
    chatted(conn, datetime(2026, 10, 26, 20, 0))
    assert days_without_diary(conn, date(2026, 10, 28)) == [date(2026, 10, 26)]


def test_problems_says_nothing_when_all_is_well_and_speaks_up_when_not(tmp_path):
    conn, _, _ = make(tmp_path)
    now = datetime(2026, 10, 28, 12, 0)
    assert problems(conn, tmp_path, now, disk_free_gb=PLENTY) == []
    assert "硬盘只剩 6 GB" in problems(conn, tmp_path, now, disk_free_gb=6.0)[0]
    conn.execute("INSERT INTO routine_runs (name, last_run) VALUES ('nightly', '2026-10-25')")
    conn.execute("INSERT INTO routine_runs (name, last_run) VALUES ('night_failed', '2026-10-25|night.upkeep_x')")
    said = problems(conn, tmp_path, now, disk_free_gb=PLENTY)
    assert "只跑到 2026-10-25" in said[0]
    assert "程序出错：upkeep_x" in said[1]
