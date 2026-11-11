"""Layer C of her character (decision 13): how she feels right now.

Three numbers 0..100 — energy, boredom, hunger — move every turn and with the clock. They
reset each night to a baseline that layer B (the phase) sets, so a flat week starts her days
tired and a good one keen. Closeness is not here: it is the relationship's, and moves over
days (memory/relationship.py).
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Callable

from fish.config import owner_words
from fish.memory import iso

KEYS = ("energy", "boredom", "hunger")
DEFAULTS = {"energy": 70.0, "boredom": 20.0, "hunger": 40.0}
FOOD_WORDS = ("吃", "饭", "喂", "零食", "夜宵")
# What each reported mood word says about her tone that turn, -1..1 (layer B reads these).
WORD_TONE = {"开心": 1.0, "好奇": 0.5, "平静": 0.1, "无聊": -0.3, "困": -0.2, "饿": -0.2,
             "烦": -0.7, "难过": -1.0}
LIVELY_TURN_ENERGY = 0.5  # a turn she called 开心 or 好奇; twenty of them undo two tired hours
# Closeness stages (decision 11); the names match the headings in docs/persona_zh.md.
STAGES = ((60.0, "很熟"), (25.0, "熟了"), (0.0, "刚认识"))


def stage_of(closeness: float) -> str:
    for threshold, name in STAGES:
        if closeness >= threshold:
            return name
    return STAGES[-1][1]


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


@dataclass
class Mood:
    energy: float
    boredom: float
    hunger: float

    def describe(self, stage: str | None = None) -> str:
        """One plain Chinese sentence for the prompt; numbers never reach the model. Each number
        has several steps, and a step several ways of saying it (decision 59): she was told the
        same "很困，不太想打字" at 29 and at 0, word for word, on 43% of two weeks' turns."""
        parts = [said for said in (_step(ENERGY_STEPS, self.energy), _step(HUNGER_STEPS, self.hunger),
                                   _step(BOREDOM_STEPS, self.boredom)) if said]
        if stage:
            parts.append(owner_words({"刚认识": "和他刚认识", "熟了": "和他熟了", "很熟": "和他很熟了"}[stage]))
        return "，".join(parts) if parts else "状态一般"


# (from, up to, ways of saying it): the number picks the step, and within the step which wording,
# so the words change as the number moves and stay put while it does not. Between the steps
# nothing is said. Only "困得不行" says she would rather not type: that used to start at 30,
# which with her cottage's hourly tiring was every evening from six.
ENERGY_STEPS = (
    (0, 15, ("困得眼睛快睁不开了，不太想打字", "困得不行，话都懒得说", "快睡着了，回得慢")),
    (15, 30, ("困了，话比平时少", "有点犯困", "打哈欠了")),
    (30, 42, ("有点乏", "有点懒懒的", "不太有劲")),
    (75, 101, ("挺精神", "精神头不错", "劲头挺足")),
)
HUNGER_STEPS = (
    (55, 70, ("有点饿了", "肚子有点空")),
    (70, 85, ("饿了，满脑子白饭", "饿了，想吃东西")),
    (85, 101, ("饿得不行，满脑子都是吃的", "饿得发慌")),
)
BOREDOM_STEPS = (
    (60, 80, ("有点无聊，想换个话题", "有点闷，想聊点别的")),
    (80, 101, ("无聊透了，想找点新鲜的", "闷得慌，想干点别的")),
)


def _step(steps: tuple, value: float) -> str:
    for lo, hi, ways in steps:
        if lo <= value < hi:
            return ways[int(value) % len(ways)]
    return ""


class MoodStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def load(self) -> Mood:
        rows = self.conn.execute("SELECT key, value FROM mood").fetchall()
        values = dict(DEFAULTS)
        values.update({r["key"]: r["value"] for r in rows if r["key"] in KEYS})
        return Mood(**{k: values[k] for k in KEYS})

    def save(self, mood: Mood) -> None:
        now = iso(datetime.now())
        for k, v in asdict(mood).items():
            self.conn.execute(
                "INSERT OR REPLACE INTO mood (key, value, updated) VALUES (?, ?, ?)",
                (k, _clamp(v), now),
            )
        self.conn.commit()

    @staticmethod
    def apply_clock(mood: Mood, now: datetime | None = None, *, kitchen: bool = False) -> Mood:
        """How she feels right now: the stored baseline plus the time of day.
        Returns a copy; the offset is never saved. With a kitchen, mealtimes are real meals in
        the cottage, so the clock does not make her hungry on top of them."""
        hour = (now or datetime.now()).hour
        shown = replace(mood)
        if 0 <= hour < 6:
            shown.energy = _clamp(mood.energy - 45)
        elif 9 <= hour < 12:
            shown.energy = _clamp(mood.energy + 10)
        if not kitchen and hour in (11, 12, 17, 18):
            shown.hunger = _clamp(mood.hunger + 20)
        return shown

    @staticmethod
    def after_turn(mood: Mood, user_text: str, fish_text: str, *, reported: str | None = None,
                   topic: str | None = None, last_topic: str | None = None, kitchen: bool = False) -> Mood:
        """How one exchange moves her: the mood she reported, whether the topic repeats,
        and whether he brought up food. With a kitchen (decisions 26, 32) hunger and energy
        are the cottage's: time, meals and sleep move them, talking does not."""
        if not kitchen:
            mood.energy = _clamp(mood.energy - 1)
            mood.hunger = _clamp(mood.hunger + 2)  # time passes; food words below undo it
        if topic and last_topic and topic == last_topic:
            mood.boredom = _clamp(mood.boredom + 8)
        else:
            mood.boredom = _clamp(mood.boredom - 6)
        if reported == "无聊":
            mood.boredom = _clamp(mood.boredom + 10)
        elif reported in ("开心", "好奇"):
            mood.boredom = _clamp(mood.boredom - 8)
            # a chat she enjoys keeps her up a little (decision 59): the one thing talking still
            # does to her energy with a kitchen, where every awake hour tires her
            mood.energy = _clamp(mood.energy + LIVELY_TURN_ENERGY)
        if not kitchen and any(k in user_text for k in FOOD_WORDS):
            mood.hunger = _clamp(mood.hunger - 20)
        return mood

    def log(self, mood: Mood, word: str | None, now: datetime | None = None) -> None:
        """One row per turn, so the night can read the day's tone."""
        self.conn.execute(
            "INSERT INTO mood_log (ts, word, energy, boredom, hunger) VALUES (?, ?, ?, ?, ?)",
            (iso(now or datetime.now()), word, mood.energy, mood.boredom, mood.hunger),
        )
        self.conn.commit()

    def day_tone(self, start: datetime, end: datetime, *,
                 rested: Callable[[float, datetime], float] | None = None) -> tuple[float | None, float | None]:
        """(mean tone of the words she reported, mean energy) between start and end, or Nones.
        rested: what to read each turn's energy as (her cottage takes the hour of day out of it)."""
        rows = self.conn.execute(
            "SELECT ts, word, energy FROM mood_log WHERE ts >= ? AND ts < ?", (iso(start), iso(end))
        ).fetchall()
        if not rows:
            return None, None
        tones = [WORD_TONE[r["word"]] for r in rows if r["word"] in WORD_TONE]
        tone = sum(tones) / len(tones) if tones else None
        energies = [rested(r["energy"], datetime.fromisoformat(r["ts"])) if rested else r["energy"] for r in rows]
        return tone, sum(energies) / len(energies)

    def rest(self, tone: float = 0.0, drive: float = 0.6) -> Mood:
        """Nightly: sleep. Where she wakes up depends on the phase (layer B): a keen stretch
        gives a brighter morning, a low one a duller one. She wakes a bit hungry."""
        mood = self.load()
        mood.energy = _clamp(30 + 60 * drive)
        mood.boredom = _clamp(DEFAULTS["boredom"] - 10 * tone)
        mood.hunger = _clamp(mood.hunger + 10)
        self.save(mood)
        return mood
