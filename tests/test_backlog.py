"""Messages that piled up while she was offline are told apart from live ones."""

import time

from fish.channels.wechat import backlog_note, sent_at, split_stale


def msg(text, age_s, key="create_time_ms"):
    t = time.time() - age_s
    return {"message_id": text, key: int(t * 1000) if key == "create_time_ms" else int(t),
            "item_list": [{"type": 1, "text_item": {"text": text}}]}


def test_old_and_new_are_split():
    old, new = msg("下午两点", 3 * 3600), msg("刚发的", 5)
    stale, live = split_stale([old, new], time.time())
    assert stale == [old] and live == [new]


def test_no_timestamp_counts_as_live():
    bare = {"message_id": "1"}
    assert split_stale([bare], time.time()) == ([], [bare])


def test_seconds_field_also_works():
    assert abs(sent_at(msg("x", 60, key="create_time")) - (time.time() - 60)) < 2


def test_note_says_when_it_was_sent():
    note = backlog_note([msg("a", 3 * 3600), msg("b", 2 * 3600)])
    assert "–" in note and "不用逐句回" in note


def test_channel_marks_the_backlog_in_what_she_hears(tmp_path):
    from fish.channels import WeChatChannel, WeChatState
    from fish.messages import Outgoing

    class Client:
        def __init__(self):
            self.queue = [([dict(msg("我在图书馆", 8 * 3600), from_user_id="o", message_type=1),
                            dict(msg("你睡了吗", 3), from_user_id="o", message_type=1)], "b1")]

        def get_updates(self, buf, timeout=45.0):
            return self.queue.pop(0) if self.queue else ([], buf)

        def send_text(self, to, text, token):
            return "m"

        def typing_ticket(self, u, t):
            return ""

        def send_typing(self, u, t, s):
            pass

    heard = []
    state = WeChatState(bot_token="t", bot_id="b", user_id="o")
    ch = WeChatChannel(Client(), state, tmp_path / "w.json", sleep=lambda s: None, out=lambda s: None, max_polls=1)
    ch.run(lambda inc: heard.append(inc.text) or Outgoing("嗯"))
    assert "不是刚说的" in heard[0] and "我在图书馆" in heard[0] and heard[0].endswith("（现在）你睡了吗")
