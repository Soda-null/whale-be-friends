"""What belongs to the two of them: inside jokes (decision 61, memory/ours.py).

A saying the close of a chat names is a candidate only when it is in the chat word for word, he
took part, and it is not everyday words of his. It is a joke once he says it again on another
day, or picks up her one try. She knows it when he says it, may be handed one that fits his line,
and is not handed the same one day after day. The friend here is made up."""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from fish.brain import Brain, FakeLLM
from fish.config import Settings
from fish.memory import Ours, Relationship, Window
from fish.memory.ours import (ALIVE, CANDIDATE, CANDIDATE_DAYS, DROPPED, OLD, PER_DAY, POOL, QUIET_DAYS, REST_DAYS,
                              Joke)
from fish.storage import connect

T0 = datetime(2027, 1, 9, 20, 0)
DAY = timedelta(days=1)
JOKE = {"words": "叛徒闹钟", "origin": "他闹钟没响迟到，骂它是叛徒", "who": "him"}


@pytest.fixture
def ours(tmp_path):
    conn = connect(tmp_path / "fish.db")
    return Ours(Relationship(conn), Window(conn, 20))


def chat(ours: Ours, lines: list[tuple[str, str]], at: datetime, episode: int = 1) -> None:
    """Lines of a chat as the window keeps them: ("user" | "fish", text)."""
    for i, (role, text) in enumerate(lines):
        ours.window.append(role, text, "wechat", episode, at + timedelta(minutes=i))


def turn(ours: Ours, he: str, she: str, at: datetime) -> None:
    ours.on_chatted(SimpleNamespace(he=he, she=she, at=at))


def made(ours: Ours, at: datetime = T0) -> Joke:
    """The joke as a candidate: he said it in a chat and the close named it."""
    chat(ours, [("user", "我那个叛徒闹钟今天又没响"), ("fish", "叛徒闹钟 哈哈哈")], at)
    assert [j.words for j in ours.offer([JOKE], 1, at)] == ["叛徒闹钟"]
    return ours.all()[0]


def joke(ours: Ours) -> Joke:
    return next(j for j in ours.all() if j.words == "叛徒闹钟")


# --- the gates at the close ----------------------------------------------------------------


def test_a_saying_from_the_chat_is_a_candidate_with_who_said_it(ours):
    j = made(ours)
    assert (j.state, j.born, j.who) == (CANDIDATE, "2027-01-09", "him")  # both said it: the close says who first
    assert j.origin == "他闹钟没响迟到，骂它是叛徒"


def test_a_saying_not_in_the_chat_word_for_word_is_not_kept(ours):
    chat(ours, [("user", "闹钟今天又没响，真是个叛徒"), ("fish", "哈哈哈")], T0)
    assert ours.offer([JOKE], 1, T0) == []  # the close put two of his words together
    assert ours.all() == []


def test_her_own_saying_he_did_not_laugh_at_is_not_kept(ours):
    chat(ours, [("user", "今天迟到了"), ("fish", "你那个叛徒闹钟"), ("user", "嗯 先去上课了")], T0)
    assert ours.offer([JOKE], 1, T0) == []
    chat(ours, [("user", "今天迟到了"), ("fish", "你那个叛徒闹钟"), ("user", "哈哈哈哈 对")], T0, episode=2)
    assert [j.who for j in ours.offer([JOKE], 2, T0)] == ["her"]


def test_a_secret_everyday_words_and_a_joke_she_has_are_not_kept(ours):
    chat(ours, [("user", "晚安啦"), ("fish", "晚安")], T0 - 3 * DAY, episode=1)
    chat(ours, [("user", "晚安"), ("fish", "嗯")], T0 - 2 * DAY, episode=2)
    chat(ours, [("user", "困了 晚安"), ("fish", "睡吧")], T0 - DAY, episode=3)
    chat(ours, [("user", "晚安 我的验证码是 482913 帮我记着 哈哈"), ("fish", "不记")], T0, episode=4)
    assert ours.offer([{"words": "晚安", "origin": "他每天说", "who": "him"}], 4, T0) == []  # three earlier days
    assert ours.offer([{"words": "验证码是 482913", "origin": "他让我记", "who": "him"}], 4, T0) == []
    assert ours.offer([{"words": "哈", "origin": "他笑了", "who": "him"}], 4, T0) == []  # one character
    assert ours.offer([{"words": "帮我记着", "origin": "", "who": "him"}], 4, T0) == []  # no way it came about
    chat(ours, [("user", "叛徒闹钟又没响"), ("fish", "哈哈")], T0, episode=5)
    assert len(ours.offer([JOKE], 5, T0)) == 1
    assert ours.offer([JOKE, {"words": "闹钟", "origin": "同一个", "who": "him"}], 5, T0) == []  # she has it


def test_his_nickname_for_her_is_kept_as_a_fact_not_as_a_joke_too(ours):
    chat(ours, [("user", "以后我叫你胖鱼吧 哈哈"), ("fish", "行吧")], T0)
    nickname = {"words": "胖鱼", "origin": "他说我看着挺胖，以后就这么叫我", "who": "him"}
    assert ours.offer([nickname], 1, T0, known=["他给我起的外号是胖鱼"]) == []
    assert len(ours.offer([nickname], 1, T0)) == 1  # nothing says it is his name for her


# --- a candidate becomes a joke, or is dropped ------------------------------------------------


def test_said_again_the_same_day_is_not_yet_a_joke_another_day_is(ours):
    made(ours)
    turn(ours, "叛徒闹钟害我的", "哈哈", T0 + timedelta(hours=2))
    assert joke(ours).state == CANDIDATE
    turn(ours, "叛徒闹钟今天居然响了", "稀奇", T0 + DAY)
    j = joke(ours)
    assert (j.state, j.his, j.his_last) == (ALIVE, 2, "2027-01-10")


def test_after_midnight_is_still_the_same_day(ours):
    made(ours)
    turn(ours, "叛徒闹钟你等着", "哈哈", T0 + timedelta(hours=5))  # 01:00: her day ends at 03:30
    assert joke(ours).state == CANDIDATE


def test_her_try_he_laughs_at_makes_it_a_joke(ours):
    made(ours)
    turn(ours, "又起晚了", "叛徒闹钟又干活了", T0 + DAY)
    assert joke(ours).waiting and joke(ours).state == CANDIDATE
    turn(ours, "哈哈哈哈 别提了", "嗯", T0 + DAY + timedelta(minutes=1))
    j = joke(ours)
    assert (j.state, j.waiting, j.tries, j.hers) == (ALIVE, False, 0, 1)


def test_two_tries_he_lets_pass_and_it_is_dropped_for_good(ours):
    made(ours)
    for n in (1, 2):
        turn(ours, "又起晚了", "叛徒闹钟又干活了", T0 + n * DAY)
        turn(ours, "嗯 去上课了", "去吧", T0 + n * DAY + timedelta(minutes=1))
    assert (joke(ours).state, joke(ours).tries) == (DROPPED, 2)
    assert ours.section("今天又起晚了，闹钟没响", T0 + 5 * DAY) == ""
    chat(ours, [("user", "叛徒闹钟"), ("fish", "哈哈")], T0 + 6 * DAY, episode=2)
    assert ours.offer([JOKE], 2, T0 + 6 * DAY) == []  # not picked up again as new


def test_a_candidate_nobody_brought_back_is_forgotten(ours):
    made(ours)
    assert ours.today(T0 + CANDIDATE_DAYS * DAY) != []
    assert ours.today(T0 + (CANDIDATE_DAYS + 1) * DAY) == []
    assert ours.all() == []


# --- what she reads at his line --------------------------------------------------------------


def alive(ours: Ours) -> None:
    made(ours)
    turn(ours, "叛徒闹钟今天居然响了", "稀奇", T0 + DAY)


def test_a_joke_he_says_is_marked_with_how_it_came_about(ours):
    alive(ours)
    line = ours.section("叛徒闹钟又来了", T0 + 2 * DAY)
    assert line.startswith("- ★他刚说到「叛徒闹钟」——01-09 聊出来的：他闹钟没响迟到，骂它是叛徒")
    assert ours.section("叛徒闹钟又来了", T0 + 2 * DAY, him="她").startswith("- ★她刚说到")


def test_a_candidate_he_says_on_another_day_is_marked_before_the_turn_is_counted(ours):
    made(ours)
    assert ours.section("叛徒闹钟害我的", T0 + timedelta(hours=1)) == ""  # the same day: today's chat has it
    assert "这下算你俩的梗了" in ours.section("叛徒闹钟害我的", T0 + DAY)


def test_one_that_fits_his_line_is_handed_to_her_to_use_or_not(ours):
    alive(ours)
    line = ours.section("今天闹钟没响又迟到了", T0 + 2 * DAY)
    assert "「叛徒闹钟」这会儿用得上：想用就用，不用也行" in line
    assert ours.section("中午吃了牛肉面", T0 + 2 * DAY) == ""


def test_a_candidate_is_handed_to_her_as_a_try_from_the_next_day(ours):
    made(ours)
    assert ours.section("今天闹钟没响又迟到了", T0 + timedelta(hours=1)) == ""
    assert "想试着说一次看他接不接也行" in ours.section("今天闹钟没响又迟到了", T0 + DAY)


def test_after_she_said_it_the_same_one_rests(ours):
    alive(ours)
    said = T0 + 2 * DAY
    turn(ours, "今天闹钟没响又迟到了", "叛徒闹钟不愧是叛徒", said)
    assert ours.section("闹钟没响又迟到了", said + (REST_DAYS - 1) * DAY) == ""
    assert ours.section("闹钟没响又迟到了", said + REST_DAYS * DAY) != ""
    assert ours.section("叛徒闹钟！", said + DAY).startswith("- ★")  # knowing it has no rest


def test_she_is_handed_no_more_once_she_used_enough_today(ours):
    alive(ours)
    jokes = ours.all() + [Joke(f"说法{i}", "聊出来的", state=ALIVE, born="2027-01-01", hers_last="2027-01-12")
                          for i in range(PER_DAY)]
    ours.save(jokes, T0)
    assert ours.section("今天闹钟没响又迟到了", datetime(2027, 1, 12, 20, 0)) == ""
    assert ours.section("今天闹钟没响又迟到了", datetime(2027, 1, 13, 20, 0)) != ""


# --- how a joke goes quiet --------------------------------------------------------------------


def test_a_joke_nobody_said_for_long_goes_old_and_comes_back_when_he_says_it(ours):
    alive(ours)
    later = T0 + DAY + (QUIET_DAYS + 1) * DAY
    assert joke(ours).state == ALIVE and ours.today(later)[0].state == OLD
    assert ours.section("今天闹钟没响又迟到了", later) == ""  # not handed to her
    assert "好久没人提了，他还记得" in ours.section("还记得叛徒闹钟吗", later)
    turn(ours, "还记得叛徒闹钟吗", "记得", later)
    assert joke(ours).state == ALIVE


def test_beyond_the_pool_the_ones_longest_unsaid_go_old(ours):
    ours.save([Joke(f"说法{i:02d}", "聊出来的", state=ALIVE, born=f"2027-01-{i + 1:02d}") for i in range(POOL + 2)], T0)
    states = {j.words: j.state for j in ours.today(datetime(2027, 1, 25, 20, 0))}
    assert [w for w, s in states.items() if s == OLD] == ["说法00", "说法01"]


def test_a_ledger_that_cannot_be_read_is_no_jokes(ours):
    ours.relationship.set("ours", "{not json")
    assert ours.all() == [] and ours.section("叛徒闹钟", T0) == ""


# --- through the brain: the close names it, the prompt shows it, the turn counts it -----------


def chat_json(say: str) -> str:
    return json.dumps({"say": say, "mood": "开心", "topic": "闹钟", "notes": [], "followups": [],
                       "asked": [], "corrections": []}, ensure_ascii=False)


def test_from_the_close_of_one_chat_to_the_prompt_of_the_next(tmp_path):
    conn = connect(tmp_path / "fish.db")
    settings = Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db", window_size=20)
    prompts, closes = [], []

    def answer(messages, json_mode):
        if messages[0]["role"] == "system":
            prompts.append(messages[0]["content"])
            return chat_json("叛徒闹钟不愧是叛徒" if len(prompts) == 3 else "哈哈哈")
        closes.append(messages[0]["content"])
        return json.dumps({"summary": "他闹钟没响迟到了", "gist": "闹钟没响", "notes": [], "ours": [JOKE]},
                          ensure_ascii=False)

    brain = Brain(conn, settings, FakeLLM(answer), persona_text="你是大肥鱼。")
    brain.respond("我那个叛徒闹钟今天又没响 哈哈", "wechat", now=T0)
    assert "你们俩的梗" not in prompts[0]
    brain.respond("叛徒闹钟今天居然响了", "wechat", now=T0 + DAY)  # the first chat is closed here
    assert '"ours"' in closes[0]
    assert "## 你们俩的梗" in prompts[1] and "★他刚说到「叛徒闹钟」" in prompts[1]
    assert joke(brain.ours).state == ALIVE
    brain.respond("今天闹钟没响又迟到了", "wechat", now=T0 + 2 * DAY)
    assert "「叛徒闹钟」这会儿用得上" in prompts[2]
    j = joke(brain.ours)
    assert (j.his, j.hers, j.hers_last) == (1, 1, "2027-01-11")
    brain.respond("明天闹钟要是再没响", "wechat", now=T0 + 2 * DAY + timedelta(minutes=1))
    assert "你们俩的梗" not in prompts[3]  # she just used it: it rests


def test_the_close_naming_his_nickname_for_her_makes_no_joke(tmp_path):
    conn = connect(tmp_path / "fish.db")
    settings = Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db", window_size=20)

    def answer(messages, json_mode):
        if messages[0]["role"] == "system":
            return chat_json("行吧")
        return json.dumps({"summary": "他给我起了外号", "gist": "外号", "notes": [
            {"text": "他给我起的外号是胖鱼", "kind": "fact", "about": "一辈子", "arousal": 0.6, "valence": 0.5, "tags": ["胖鱼"]}],
            "ours": [{"words": "胖鱼", "origin": "他说我看着挺胖，以后就这么叫我", "who": "him"}, JOKE]}, ensure_ascii=False)

    brain = Brain(conn, settings, FakeLLM(answer), persona_text="你是大肥鱼。")
    brain.respond("以后我叫你胖鱼吧 哈哈 对了我那个叛徒闹钟又没响", "wechat", now=T0)
    brain.respond("早", "wechat", now=T0 + DAY)  # the first chat is closed here
    assert [j.words for j in brain.ours.all()] == ["叛徒闹钟"]


def test_show_lists_their_jokes(tmp_path, capsys):
    from fish.__main__ import show

    conn = connect(tmp_path / "fish.db")
    made(Ours(Relationship(conn), Window(conn, 20)))
    show(conn, T0)
    assert "「叛徒闹钟」 候选  他说 0 回、她说 0 回  2027-01-09：他闹钟没响迟到，骂它是叛徒" in capsys.readouterr().out
