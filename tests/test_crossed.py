"""Messages that crossed (decision 58): what he sent before her last bubble reached him is not
an answer to it, and the channel says so in front of his line."""

import time

from fish.brain.closing import closing_note
from fish.brain.comfort import comfort_note
from fish.brain.parse import clean_say
from fish.channels import WeChatChannel, WeChatState
from fish.channels.crossed import NOTE, Crossing
from fish.messages import Outgoing


def test_only_what_was_sent_before_her_last_bubble_is_marked():
    c = Crossing(clock=lambda: 100.0)
    assert c.note([90.0]) == ""  # she has sent nothing yet
    c.she_sent()
    assert c.note([90.0, 120.0]) == NOTE  # the first of the batch was on its way already
    assert c.note([101.0]) == ""  # sent after her line arrived: an answer
    assert c.note([None]) == ""  # no time on the message: nothing is known


def test_the_note_is_no_goodbye_no_hurt_and_never_said_back():
    assert not closing_note(NOTE + "我想吃面", "你想吃啥") and not comfort_note(NOTE + "我想吃面")
    assert clean_say(NOTE + "\n好呀") == "好呀"


def his(text, age_s):
    return {"message_id": text, "create_time_ms": int((time.time() - age_s) * 1000), "from_user_id": "o",
            "message_type": 1, "item_list": [{"type": 1, "text_item": {"text": text}}]}


def test_the_channel_marks_his_line_that_crossed_hers(tmp_path):
    class Client:
        def __init__(self):
            # the second was written five seconds ago by its own clock; her bubble to the first
            # goes out "now" (the test does not wait), after it
            self.queue = [([his("晚上吃啥", 30)], "b1"), ([], "b1"), ([his("我想吃面", 5)], "b2"), ([], "b2")]

        def get_updates(self, buf, timeout=45.0):
            return self.queue.pop(0) if self.queue else ([], buf)

        def send_text(self, to, text, token):
            return "m"

        def typing_ticket(self, u, t):
            return ""

        def send_typing(self, u, t, s):
            pass

    heard = []
    ch = WeChatChannel(Client(), WeChatState(bot_token="t", bot_id="b", user_id="o"), tmp_path / "w.json",
                       sleep=lambda s: None, out=lambda s: None, max_polls=2)
    ch.run(lambda inc: heard.append(inc.text) or Outgoing("你想吃啥"))
    assert heard == ["晚上吃啥", NOTE + "我想吃面"]
