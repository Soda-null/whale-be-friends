"""Urges to text him (decisions 10, 26, 30): something she saw today worth sharing, a
follow-up that came due, a long silence, an anniversary, plain boredom, something that
happened at home. Moved here from brain/reach.py unchanged (decision 46); in this order she
is told them."""

from __future__ import annotations

from fish.config import owner_words
from fish.memory import DUE_SHOWN, MemoryStore, ProspectiveStore, Relationship, last_his_message
from fish.urges.rules import (ANNIVERSARIES, BORED_LEVEL, BORED_PER_QUIET_HOUR, BORED_SILENCE_HOURS, SHARE_AT_MOST,
                              SHARE_IMPORTANCE, SILENCE_HOURS)
from fish.urges.urge import HIM, Scene, Urge


def silence_hours(s: Scene) -> float:
    his = last_his_message(s.conn)
    return (s.now - his).total_seconds() / 3600 if his else 0.0


def seen(s: Scene) -> list[Urge]:
    found = [m for m in MemoryStore(s.conn).seen_recently(s.now, 1)
             if m.importance >= SHARE_IMPORTANCE and m.id not in s.shared][:SHARE_AT_MOST]
    return [Urge(HIM, "seen", f"今天看到的（见闻 #{m.id}）：{m.text}", ref=m) for m in found]


def _day(created: str) -> str:
    """"11月4日": a follow-up says "今天考试" in the words of the day it was written (11-05 she
    asked about "today's" exam, which was the day before)."""
    return f"{int(created[5:7])}月{int(created[8:10])}日"


def due(s: Scene) -> list[Urge]:
    return [Urge(HIM, "due", f"惦记的事到日子了（惦记 #{f.id}，{_day(f.created)}记下的）：{f.text}", ref=f)
            for f in ProspectiveStore(s.conn).due(s.now)[:DUE_SHOWN]]


def silence(s: Scene) -> list[Urge]:
    hours = silence_hours(s)
    return [Urge(HIM, "silence", owner_words(f"他有 {int(hours)} 个小时没来找你了"), ref=hours)] if hours >= SILENCE_HOURS else []


def anniversary(s: Scene) -> list[Urge]:
    rel = Relationship(s.conn)
    known = rel.days_known(s.now)
    if rel.get("reach_anniversary") == str(known):  # she already said it on this day; once is enough
        return []
    if known in ANNIVERSARIES or (known > 0 and known % 100 == 0):
        return [Urge(HIM, "anniversary", f"今天是你们认识的第 {known} 天", ref=known)]
    return []


def bored(s: Scene) -> list[Urge]:
    quiet = silence_hours(s)
    if quiet < BORED_SILENCE_HOURS or s.mood.boredom + BORED_PER_QUIET_HOUR * quiet < BORED_LEVEL:
        return []
    return [Urge(HIM, "bored", "你有点无聊")]


def home(s: Scene) -> list[Urge]:
    return [Urge(HIM, "home", f"家里的事：{line}", ref=line) for line in s.home]


SOURCES = (seen, due, silence, anniversary, bored, home)


def about_him(s: Scene) -> list[Urge]:
    """Every urge to text him right now, in the order she is told them."""
    return [u for source in SOURCES for u in source(s)]
