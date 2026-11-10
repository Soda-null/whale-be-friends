"""When his line is only a nod or a goodbye, she is told so right at that line (2026-11-10).

Read from two weeks of real chat: she answered nearly every "嗯嗯", "好的好的" and "拜拜" with a
full reply, and with nothing new to answer she filled it with an old errand, one more "记得吃饭"
or her last line over again (six goodbyes in ninety seconds). The rule that she may leave such a
line unanswered sits in the middle of the prompt, where rules lose to the chat around them
(prompt.py, FACE_NOW); these notes stand at his line. Only in the prompt, never stored.
"""

from __future__ import annotations

import re

ACK_CHARS = 12  # a nod is short; anything longer says something
# WeChat's own emoji as they reach her ("[Doge]", "[表情：狗头]"), picture emoji, and what ends a line
_NOT_WORDS = re.compile(r"\[表情[^\]]*\]|\[[A-Za-z]+\]|[\U0001F300-\U0001FAFF☀-➿]|[\s，。！!~～…、.]")
_NOD = re.compile(r"(?:嗯|好的?|好滴|好吧|哈|嘿|呵|ok|行|是的?|对的?|可以|没事|知道了?|收到|诶|哦|噢|额|的|啊|呀|哒)+", re.I)
_BYE = re.compile(r"拜拜|晚安|先下了|明天见|回聊|(?:一会儿?|待会儿?|回头|晚上|晚点)[见聊]|有事[找叫]我"
                  r"|(?:学习|干活|上课)去了|先(?:去|学习|忙)了|去了去了")
_FEELING = re.compile(r"大哭|流泪|裂开|无语|心碎|委屈|难受|失望|生气|惊恐|叹气|不舒服")  # a face that says how he is
_ASKING = re.compile(r"[？?]|[吗没呢]$|(.)不\1|什么|怎么|咋|啥|几点|多少|哪|谁")

ACK_NOTE = "（他只是应了一声，这段话说到头了：短短接一句，或者不回（say 留空）都行；别开新话题、别叮嘱、别把前面说过的事再提一遍）"
BYE_NOTE = "（他在道别：回一句短的就好，别再加叮嘱、别再提别的事）"


def asking(hers: str) -> bool:
    """Her last line asked him something: then his "是的" or "可以" is an answer, not a nod."""
    return any(_ASKING.search(line.strip()) for line in hers.splitlines())


def closing_note(his: str, her_last: str = "") -> str:
    """The note for his line, "" when it says something. her_last: what she said just before."""
    if "?" in his or "？" in his or len(his) > ACK_CHARS * 3:
        return ""
    words = _NOT_WORDS.sub("", his)
    if len(words) > ACK_CHARS:
        return ""
    if _BYE.search(words):
        return BYE_NOTE
    if asking(her_last):
        return ""
    if not words:  # only an emoji; a picture, a file, or a face that says how he feels is not a nod
        return ACK_NOTE if his.strip() and not his.lstrip().startswith(("[图片", "[文件")) and not _FEELING.search(his) else ""
    return ACK_NOTE if _NOD.fullmatch(words) else ""
