"""Comparing words: how alike two notes are, what a line is about, whose words a note holds.

Pure functions on text; nothing here knows the `memories` table.
"""

from __future__ import annotations

import re

_DATE = re.compile(r"\d{4}\s*[-年/.]\s*\d{1,2}\s*[-月/.]\s*\d{1,2}\s*日?")
# A note is about what he said, not what she said (memory v3 §14): her guess at a question of his,
# or a turn of his she made up, written down as his, is a false memory for good. Its content words
# (no dates, no function words, no persons) must not come from her lines of the chat alone.
ECHO_HIS = 0.2  # less than this share of the note's words from his lines ...
ECHO_HERS = 0.5  # ... and this much from words only she said: hers, not his
_NOT_CONTENT = re.compile(r"[的了是在和就也都还又很吧呢啊吗呀哦嗯他她我你]")
_DAY_WORDS = re.compile(r"\d{4}\s*[-年/.]\s*\d{1,2}(?:\s*[-月/.]\s*\d{1,2}\s*[日号]?)?|\d{1,2}\s*月(?:\s*\d{1,2}\s*[日号])?"
                        r"|\d{1,2}\s*[日号点时]|(?:周|星期|礼拜)[一二三四五六日天]")


def _bigrams(text: str) -> set[str]:
    chars = [c for c in _DATE.sub("", text) if c.isalnum()]
    return {a + b for a, b in zip(chars, chars[1:])}


def overlap(a: str, b: str) -> float:
    """Dice overlap of character bigrams with dates taken out: "he had lab on 10-26" and
    "he had lab on 10-27" are the same words."""
    x, y = _bigrams(a), _bigrams(b)
    return 2 * len(x & y) / (len(x) + len(y)) if x and y else 0.0


def content_words(text: str) -> set[str]:
    """The two-character runs of what a line is about: no dates, no function words, no persons."""
    chars = [c for c in _NOT_CONTENT.sub("", _DAY_WORDS.sub(" ", text)) if c.isalnum() or c == " "]
    return {a + b for a, b in zip(chars, chars[1:]) if a != " " and b != " "}


# A number said in words ("两千八", "十五个") is the number she writes in digits ("2800"). Two or more
# numeral characters, or one before a unit; "一下", "一起" are no numbers.
_CN_NUMBER = re.compile(r"[一二两三四五六七八九十][零一二两三四五六七八九十百千万]+"
                        r"|[一二两三四五六七八九十](?=[块元岁斤只个本次])")
_CN_DIGIT = {c: i for i, c in enumerate("零一二三四五六七八九")} | {"两": 2}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def cn_number(word: str) -> int:
    """"两千八" -> 2800, "一万二" -> 12000, "三百零五" -> 305, "十五" -> 15, "二零二七" -> 2027."""
    if not any(c in _CN_UNIT or c == "万" for c in word):
        return int("".join(str(_CN_DIGIT[c]) for c in word))
    total = section = digit = 0
    last, prev = 1, ""
    for c in word:
        if c in _CN_DIGIT:
            digit = _CN_DIGIT[c]
        elif c in _CN_UNIT:
            section += (digit or (1 if c == "十" else 0)) * _CN_UNIT[c]
            digit, last = 0, _CN_UNIT[c]
        else:  # 万
            total += (section + digit) * 10000
            section = digit = 0
            last = 10000
        prev = c
    if digit and last >= 100 and prev != "零" and word[-2] in "百千万":
        digit *= last // 10  # "两千八": the unit after the last one is left out
    return total + section + digit


def digits(text: str) -> str:
    """The numbers of a line in digits: "一个月两千八" -> "一个月2800"."""
    return _CN_NUMBER.sub(lambda m: str(cn_number(m.group(0))), text)


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", _DAY_WORDS.sub(" ", text)))


def echoes_her(text: str, his: str, hers: str) -> bool:
    """The note says what she said in the chat (`hers`, her lines), not what he said (`his`):
    hardly any of its words are his and most are hers alone, or it has a number only she said
    ("两千八" he said is her "2800")."""
    text, his, hers = digits(text), digits(his), digits(hers)
    note = content_words(text)
    if note:
        him = content_words(his)
        only_hers = content_words(hers) - him
        if len(note & him) < ECHO_HIS * len(note) and len(note & only_hers) >= ECHO_HERS * len(note):
            return True
    return bool(_numbers(text) & (_numbers(hers) - _numbers(his)))
