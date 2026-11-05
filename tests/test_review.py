"""The weekly review (scripts/review.py): it counts right on a made-up week, it never writes, it
runs piped with nothing of ours importable, and its copies of what she knows have not drifted."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

from fish.brain.leisure import default_activities
from fish.cottage import Cottage
from fish.cottage.rules import ACTIONS, PLANTS
from fish.routines.nightly import NIGHT_BOUNDARY
from fish.storage import connect

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("review", ROOT / "scripts" / "review.py")
review = importlib.util.module_from_spec(spec)
sys.modules["review"] = review  # dataclasses look the module up by name
spec.loader.exec_module(review)  # type: ignore[union-attr]

NOW = datetime(2026, 3, 8, 20, 0)  # a Sunday evening: her day 03-08 is today, not yet closed


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "data" / "fish.db"
    connect(path).close()
    return path


def turn(conn, ts: str, his: str, hers: str) -> None:
    conn.execute("INSERT INTO messages (ts, role, text, channel) VALUES (?, 'user', ?, 'wechat')", (ts, his))
    conn.execute("INSERT INTO messages (ts, role, text, channel) VALUES (?, 'fish', ?, 'wechat')", (ts, hers))


def first(conn, ts: str, hers: str) -> None:
    conn.execute("INSERT INTO messages (ts, role, text, channel) VALUES (?, 'fish', ?, 'wechat')", (ts, hers))


def msgs(db_path: Path) -> list:
    conn = review.open_readonly(db_path)
    try:
        return review.load_messages(conn)
    finally:
        conn.close()


def lines_of(texts: list[str], day: date = date(2026, 3, 8)) -> list[tuple[date, str]]:
    return [(day, t) for t in texts]


# --- never writes, runs alone ---------------------------------------------------------------


def test_the_database_is_read_only(db: Path) -> None:
    conn = review.open_readonly(db)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO diary (day, text) VALUES ('2026-01-01', 'x')")
    conn.close()


def test_a_report_leaves_the_folder_exactly_as_it_was(db: Path) -> None:
    conn = connect(db)
    turn(conn, "2026-03-08T10:00:00", "早", "早呀")
    conn.commit()
    conn.close()
    before = {p.name: (hashlib.sha1(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in db.parent.iterdir()}
    review.report(db, NOW)
    after = {p.name: (hashlib.sha1(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in db.parent.iterdir()}
    assert after == before


def test_it_runs_piped_like_over_ssh_with_nothing_of_ours_to_import(db: Path, tmp_path: Path) -> None:
    conn = connect(db)
    turn(conn, "2026-03-08T10:00:00", "早", "早呀")
    conn.commit()
    conn.close()
    script = (ROOT / "scripts" / "review.py").read_bytes()
    done = subprocess.run([sys.executable, "-I", "-", "3", "--db", str(db)], input=script, cwd=tmp_path,
                          capture_output=True, check=True, env={"PYTHONIOENCODING": "utf-8"})
    assert "先看这几条" in done.stdout.decode("utf-8")


def test_the_script_imports_nothing_of_ours_and_the_short_command_pipes_it() -> None:
    src = (ROOT / "scripts" / "review.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(?:from|import)\s+fish\b", src, re.M)
    wiring = (ROOT / "scripts" / "fish.sh").read_text(encoding="utf-8")
    assert re.search(r'review\)\s+ssh "\$BOX" ".*python - \$\{2:-7\}" < scripts/review\.py', wiring)


def test_no_database_is_a_plain_message_not_a_traceback(tmp_path: Path, capsys) -> None:
    assert review.main(["--db", str(tmp_path / "nothing.db")]) == 2
    assert "找不到" in capsys.readouterr().err
    assert not (tmp_path / "nothing.db").exists()


# --- its copies of what she knows ------------------------------------------------------------


def test_her_day_ends_when_the_nights_say() -> None:
    assert review.NIGHT_BOUNDARY == NIGHT_BOUNDARY


def test_it_knows_every_thing_on_her_menu() -> None:
    real = {a.key for a in default_activities(cottage=object())} | {"nothing"}
    assert set(review.PICKS) == real


def test_it_knows_every_thing_she_can_do_at_home_and_the_vegetables() -> None:
    assert set(review.DEED_NAME) == set(ACTIONS)
    assert set(review.VEGETABLES) == set(PLANTS)


def test_real_lines_from_her_room_are_read_as_the_right_deed(tmp_path: Path) -> None:
    """The words are the room's own: do each thing in a real room, and see the record is understood."""
    room = Cottage(tmp_path / "now.json")
    now = datetime(2026, 3, 8, 9, 0)
    room.load(now)
    state = room.load(now)
    state.pots = [{}, {}]
    state.tank = {"name": "小黑", "since": "2026-03-01", "fed": "", "water": "2026-03-01"}
    assert room._tank_apply(state, "feed", now, "") and review.deed_of(room._tank_apply(state, "feed", now, "")) == "feed"
    assert review.deed_of(room._tank_apply(state, "change", now, "")) == "change"
    assert review.deed_of(room._garden_apply(state, "sow", now, "小葱")) == "sow"
    assert review.deed_of(room._garden_apply(state, "water", now, "")) == "water"
    assert review.deed_of(room._lake_apply(state, "lake", now, "")) == "lake"
    assert review.deed_of(room._florist_apply(state, "florist", now, "多肉")) == "florist"


def test_coming_home_and_his_doing_are_not_deeds() -> None:
    assert review.deed_of("从花店回来了，买了多肉，摆在窗台上，浇了水") is None
    assert review.deed_of("从菜店回来了，买了鸡蛋，放进冰箱") is None
    assert review.deed_of("他往冰箱里放了吃的") is None
    assert review.deed_of("从菜店回来了，买了鸡蛋；给小黑喂了鱼食") == "feed"


# --- the chat --------------------------------------------------------------------------------


def test_one_at_night_still_belongs_to_yesterday() -> None:
    assert review.fish_day(datetime(2026, 3, 8, 1, 0)) == date(2026, 3, 7)
    assert review.fish_day(datetime(2026, 3, 8, 3, 30)) == date(2026, 3, 8)


def test_a_reply_has_his_time_and_anything_else_she_said_first(db: Path) -> None:
    conn = connect(db)
    turn(conn, "2026-03-08T10:00:00", "早", "早呀")
    first(conn, "2026-03-08T11:00:00", "在吗")
    conn.execute("INSERT INTO messages (ts, role, text, channel) VALUES ('2026-03-08T12:00:00', 'user', '嗯', 'wechat')")
    first(conn, "2026-03-08T13:00:00", "他没等到回的那句之后她又说")
    conn.commit()
    conn.close()
    assert [m.first for m in msgs(db)] == [False, False, True, False, True]


def test_runs_she_kept_texting_with_him_silent(db: Path) -> None:
    conn = connect(db)
    turn(conn, "2026-03-07T10:00:00", "早", "早呀")
    for hour in (11, 12, 13):
        first(conn, f"2026-03-07T{hour}:00:00", "在吗")
    turn(conn, "2026-03-07T14:00:00", "刚才在忙", "好")
    first(conn, "2026-03-07T15:00:00", "吃了吗")  # alone, and he answers
    turn(conn, "2026-03-07T16:00:00", "吃了", "好")
    first(conn, "2026-03-07T17:00:00", "晚上呢")  # the last two: nobody answered yet
    first(conn, "2026-03-07T18:00:00", "睡了？")
    conn.commit()
    conn.close()
    out, loud = review.speaking_first(msgs(db))
    text = "\n".join(out)
    assert "主动发了 6 回，他接话 2 回" in text
    assert "连发没人回（他没说话、她连着发两回以上）：2 次，最长一串 3 回" in text
    assert any("连发没人回 2 次" in x for x in loud)


def test_a_day_of_many_first_messages_is_called_out(db: Path) -> None:
    conn = connect(db)
    for minute in range(review.LOUD_FIRST_A_DAY):
        first(conn, f"2026-03-07T10:{minute:02d}:00", "纪念日快乐")
    conn.commit()
    conn.close()
    _, loud = review.speaking_first(msgs(db))
    assert any("03-07 周六" in x and f"{review.LOUD_FIRST_A_DAY} 回" in x for x in loud)


def test_each_line_is_a_bubble_and_stickers_have_no_words() -> None:
    assert review.bubbles("早呀\n吃了吗") == ["早呀", "吃了吗"]
    assert review.bubbles("[表情包：一只猫]") == []
    assert review.bubbles("哈哈[Doge]") == ["哈哈"]


def test_the_daily_table_counts_bubbles_and_averages_words(db: Path) -> None:
    conn = connect(db)
    turn(conn, "2026-03-08T10:00:00", "早上好", "早\n吃了吗")
    conn.commit()
    conn.close()
    table = review.daily(msgs(db), [date(2026, 3, 7), date(2026, 3, 8)])
    today = next(line for line in table if "今天" in line)
    assert today.split()[2:] == ["1", "3.0", "2", "2.0", "0"]


def test_a_phrase_counts_once_a_bubble_and_needs_three() -> None:
    said = review.phrases(lines_of(["好的好的好的"] + ["慢慢来吧呀"] * 3 + ["春天来了呀"] * 2))
    names = {p for p, _, _ in said}
    assert "慢慢来吧" in names and "春天来了" not in names
    assert ("慢慢来吧", 3, 1) in said


def test_one_sentence_said_again_is_one_phrase_not_a_dozen() -> None:
    said = review.phrases(lines_of(["今天天气真不错啊"] * 5))
    assert len(said) <= 2  # the sentence, not its every overlapping slice


def test_a_fragment_starting_on_a_particle_is_not_a_phrase() -> None:
    assert not review.phrases(lines_of(["了一下子"] * 5))


def test_word_for_word_repeats_ignore_the_last_punctuation_and_span_days() -> None:
    lines = [(date(2026, 3, 7), "真不错。"), (date(2026, 3, 8), "真不错"), (date(2026, 3, 8), "真不错！"), (date(2026, 3, 8), "再见")]
    assert review.repeats(lines) == [("真不错", 3, 2)]


def test_a_short_answer_needs_many_repeats_to_reach_the_top(db: Path) -> None:
    conn = connect(db)
    for n in range(review.LOUD_SHORT_REPEAT):
        turn(conn, f"2026-03-08T10:{n:02d}:00", "我走了", "好呀")
    for n in range(review.LOUD_SHORT_REPEAT - 1):
        turn(conn, f"2026-03-08T11:{n:02d}:00", "睡了", "再会")
    conn.commit()
    conn.close()
    _, loud = review.tics(msgs(db))
    assert any("好呀" in x for x in loud) and not any("再会" in x for x in loud)


# --- what she did ----------------------------------------------------------------------------


def moment(conn, ts: str, choice: str | None, line: str = "", result: str = "") -> None:
    conn.execute("INSERT INTO leisure_log (ts, choice, line, result) VALUES (?, ?, ?, ?)", (ts, choice, line, result))


def with_moments(db: Path) -> None:
    conn = connect(db)
    moment(conn, "2026-03-05T09:00:00", "cottage", "喂点鱼食", "给小黑喂了鱼食")
    moment(conn, "2026-03-05T12:00:00", "bilibili", "刷 B 站", "刷了")
    moment(conn, "2026-03-05T15:00:00", "nothing", "什么都不干", "")
    moment(conn, "2026-03-06T09:00:00", "cottage", "去码头", "想去码头，没弄成")
    moment(conn, "2026-03-06T12:00:00", None)
    moment(conn, "2026-02-01T12:00:00", "news", "翻新闻", "翻了")  # long before the week
    conn.commit()
    conn.close()


def moments_of(db: Path, days: list[date]) -> list:
    conn = review.open_readonly(db)
    try:
        return review.leisure(conn, days)
    finally:
        conn.close()


WEEK = [date(2026, 3, d) for d in range(2, 9)]


def test_free_time_counts_what_she_picked_and_names_what_she_never_did(db: Path) -> None:
    with_moments(db)
    out, loud = review.free_time(moments_of(db, WEEK))
    text = "\n".join(out)
    assert "一共 5 段" in text
    assert "屋里的事 2 回：喂鱼 1" in text and "刷 B 站 1 回" in text
    assert "开了头没选成（模型没回好）：1 段" in text
    assert "想做没弄成：去码头" in text
    assert "一次都没选：翻新闻、读书、查好奇的；" in text and "码头" in text.split("屋里的事里：")[1]
    assert loud == ["空闲时一次都没选：翻新闻、读书、查好奇的"]


def test_what_did_not_work_out_is_not_a_time_she_did_it(db: Path) -> None:
    with_moments(db)
    out, loud = review.things(moments_of(db, WEEK), {}, WEEK)
    text = "\n".join(out)
    assert "养鱼 1 回（喂鱼 1、换水 0、起名 0）" in text
    assert "码头 0 回" in text
    assert loud == ["这段时间一回都没做：种菜、码头、花店"]


def test_the_rooms_record_adds_what_she_did_mid_chat_and_counts_a_pick_once(db: Path) -> None:
    with_moments(db)
    room = {"events": [{"ts": "2026-03-05T09:00", "line": "给小黑喂了鱼食", "routine": True},  # that pick, again
                       {"ts": "2026-03-07T19:00", "line": "给小黑喂了鱼食", "routine": True},  # mid-chat
                       {"ts": "2026-03-07T20:00", "line": "出门去湖边码头坐一会儿"},
                       {"ts": "2026-03-07T20:30", "line": "从湖边码头回来了，坐了半个钟头"},
                       {"ts": "2026-01-07T20:30", "line": "出门去镇上的花店"}],  # outside the week
            "tank": {"name": "小黑", "fed": "2026-03-07"}, "been": {"lake": "2026-03-07T20:30"}, "pots": [{}, {}]}
    out, _ = review.things(moments_of(db, WEEK), room, WEEK)
    text = "\n".join(out)
    assert "养鱼 2 回" in text and "现在：小黑，上次喂是 03-07" in text
    assert "码头 1 回  上次是 03-07" in text
    assert "花店 0 回" in text
    assert "现在：2 个花盆都空着" in text


def test_watering_only_flowers_is_not_growing_vegetables() -> None:
    room = {"events": [{"ts": "2026-03-07T09:00", "line": "给多肉浇了水", "routine": True},
                       {"ts": "2026-03-08T09:00", "line": "给小葱、多肉浇了水", "routine": True}],
            "pots": [{"plant": "小葱"}, {}]}
    out, _ = review.things([], room, WEEK)
    text = "\n".join(out)
    assert "种菜 1 回（种下 0、浇水 1、摘菜 0）" in text and "种着小葱，空着 1 盆" in text


# --- the nights and the follow-ups ------------------------------------------------------------


def night_rows(conn, days: dict[str, tuple[bool, bool]]) -> None:
    for day, (diary, phase) in days.items():
        if diary:
            conn.execute("INSERT INTO diary (day, text) VALUES (?, 'x')", (day,))
        if phase:
            conn.execute("INSERT INTO phase (day, tone, drive) VALUES (?, 0, 0.5)", (day,))


def nights_of(db: Path, days: list[date], born: date | None) -> tuple[list[str], list[str]]:
    conn = review.open_readonly(db)
    try:
        return review.nights(conn, db, days, born)
    finally:
        conn.close()


def test_a_missing_diary_is_named_and_says_whether_the_night_ran(db: Path) -> None:
    conn = connect(db)
    night_rows(conn, {"2026-03-05": (True, True), "2026-03-06": (False, True), "2026-03-07": (False, False)})
    conn.execute("INSERT INTO routine_runs (name, last_run) VALUES ('nightly', '2026-03-07')")
    conn.commit()
    conn.close()
    out, loud = nights_of(db, [date(2026, 3, d) for d in (5, 6, 7, 8)], date(2026, 3, 5))
    assert loud == ["03-06 周五 没有日记：整理跑了，日记没写出来（多半是模型那次没回好）",
                    "03-07 周六 没有日记：那晚的整理整个没跑"]
    assert any(line.startswith("  03-05 周四  日记有  这阵子有") for line in out)


def test_today_has_no_night_yet_and_days_before_she_met_him_have_none_either(db: Path) -> None:
    conn = connect(db)
    night_rows(conn, {"2026-03-07": (True, True)})
    conn.execute("INSERT INTO routine_runs (name, last_run) VALUES ('nightly', '2026-03-07')")
    conn.commit()
    conn.close()
    out, loud = nights_of(db, [date(2026, 3, d) for d in (5, 6, 7, 8)], date(2026, 3, 7))
    assert loud == []
    assert not any("03-08" in line or "03-05" in line or "03-06" in line for line in out)


def test_last_night_not_running_at_all_is_called_out(db: Path) -> None:
    conn = connect(db)
    night_rows(conn, {"2026-03-06": (True, True), "2026-03-07": (True, True)})
    conn.execute("INSERT INTO routine_runs (name, last_run) VALUES ('nightly', '2026-03-06')")
    conn.commit()
    conn.close()
    _, loud = nights_of(db, [date(2026, 3, d) for d in (6, 7, 8)], date(2026, 3, 6))
    assert loud == ["昨晚的整理没跑：上次整理管的是 03-06，该是 03-07"]


def test_a_letter_is_only_expected_since_she_began_writing_them(db: Path) -> None:
    drawer = db.parent / "cottage" / "抽屉"
    drawer.mkdir(parents=True)
    (drawer / "2026-03-06.md").write_text("x", encoding="utf-8")
    conn = connect(db)
    night_rows(conn, {f"2026-03-0{d}": (True, True) for d in (5, 6, 7)})
    conn.execute("INSERT INTO routine_runs (name, last_run) VALUES ('nightly', '2026-03-07')")
    conn.commit()
    conn.close()
    out, _ = nights_of(db, [date(2026, 3, d) for d in (5, 6, 7, 8)], date(2026, 3, 5))
    assert "给他的信（那时还没有）" in out[1]
    assert "给他的信有" in out[2]
    assert "给他的信没有" in out[3] and "信没写出来" in out[3]


def test_chats_left_without_a_summary_show_on_their_night(db: Path) -> None:
    conn = connect(db)
    night_rows(conn, {"2026-03-07": (True, True)})
    conn.execute("INSERT INTO episodes (started, last_active, channel) VALUES ('2026-03-07T10:00:00', '2026-03-07T10:00:00', 'wechat')")
    conn.execute("INSERT INTO routine_runs (name, last_run) VALUES ('nightly', '2026-03-07')")
    conn.commit()
    conn.close()
    out, _ = nights_of(db, [date(2026, 3, 7), date(2026, 3, 8)], date(2026, 3, 7))
    assert "1 段聊天没写摘要" in out[1]


def followup(conn, text: str, due: str, created: str, status: str, asked_episode: int | None = None) -> None:
    conn.execute("INSERT INTO prospective (text, due, created, status, asked_episode) VALUES (?, ?, ?, ?, ?)",
                 (text, due, created, status, asked_episode))


def test_followups_count_asked_lapsed_and_still_waiting(db: Path) -> None:
    conn = connect(db)
    conn.execute("INSERT INTO episodes (id, started, last_active, channel) VALUES (7, '2026-03-06T10:00:00', '2026-03-06T10:00:00', 'wechat')")
    followup(conn, "问面试", "2026-03-20", "2026-03-05T10:00:00", "asked", 7)  # asked early, this week
    followup(conn, "问考试", "2026-03-04", "2026-02-20T10:00:00", "asked")  # no episode: its due day
    followup(conn, "问牙医", "2026-03-03", "2026-02-20T10:00:00", "expired")
    followup(conn, "更早的", "2026-01-03", "2026-01-01T10:00:00", "expired")  # before the week
    followup(conn, "问出差", "2026-03-30", "2026-03-07T10:00:00", "open")
    conn.commit()
    conn.close()
    conn = review.open_readonly(db)
    out, loud = review.followups(conn, WEEK)
    conn.close()
    text = "\n".join(out)
    assert "新记下 2 条，问了 2 条，到期没问就放下了 1 条" in text
    assert "现在还挂着 1 条，最早 03-30 到期" in text
    assert "没问成（03-03 到期）：问牙医" in text and "更早的" not in text
    assert loud == ["惦记的事有 1 条到期没问就放下了"]


# --- the whole report ------------------------------------------------------------------------


def test_a_quiet_empty_database_reports_without_falling_over(db: Path) -> None:
    text = review.report(db, NOW)
    assert "先看这几条" in text and "没有要紧的" in text
    assert "这段时间还没有整理过的日子" in text


def test_a_database_from_before_a_table_existed_still_reports(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, ts TEXT, role TEXT, text TEXT)")
    conn.execute("INSERT INTO messages (ts, role, text) VALUES ('2026-03-08T10:00:00', 'user', '早')")
    conn.commit()
    conn.close()
    assert "每天聊了多少" in review.report(path, NOW)


def test_the_top_of_the_report_gathers_what_is_wrong(db: Path) -> None:
    conn = connect(db)
    turn(conn, "2026-03-02T10:00:00", "早", "早呀")
    night_rows(conn, {f"2026-03-0{d}": (d != 6, True) for d in range(2, 8)})
    conn.execute("INSERT INTO routine_runs (name, last_run) VALUES ('nightly', '2026-03-07')")
    moment(conn, "2026-03-05T15:00:00", "nothing", "什么都不干", "")
    conn.commit()
    conn.close()
    (db.parent / "cottage").mkdir()
    (db.parent / "cottage" / "now.json").write_text(json.dumps({"pots": [{}, {}]}), encoding="utf-8")
    text = review.report(db, NOW)
    top = text.split("== 每天聊了多少")[0]
    assert "! 03-06 周五 没有日记" in top
    assert "! 这段时间一回都没做：种菜、养鱼、码头、花店" in top
    assert "没有要紧的" not in top
    assert text.index("== 每天聊了多少") < text.index("== 每晚整理") < text.index("== 惦记的事")
