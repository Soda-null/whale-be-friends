"""One long-term memory: the `Memory` record, its kinds, and how it reads and fades.

A row of the `memories` table as the rest of her memory sees it. Data and math only.
Field meanings: docs/memory_design_zh.md §4.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from fish.memory import stability as st

KINDS = ("fact", "event", "howto", "insight", "self", "world")  # world: things she saw online
# Only for things that happen (his events, her own doings). A fact, a rule or an insight said again
# is the same thing confirmed, not something that happened again: counted, never "好几回".
HAPPENING_KINDS = ("event", "self")
# Insights and howto rules start unconfirmed (decision 21): they need evidence on this many
# different days before they get the strength of a fact about him.
RULE_KINDS = ("insight", "howto")
EVIDENCE_DAYS = 3
UNCONFIRMED = "待印证"
# Why a memory stopped being current (memory v3). Only a correction he made and an update the
# night found are "what she used to think"; a memory merged away or pushed out by a cap is not.
WHYS = ("correct", "update", "merge", "cap", "expired")
SHOWN_AS_FORMER = ("correct", "update")
SETTLED = {"kept": "兑现了", "dropped": "后来说不算了"}  # how a settled pact reads
# The follow-ups she let go were written as events before memory v3 step 1; they fade within
# weeks (stability.UNASKED_MAX_DAYS), whoever the merge made the subject. Only that row shape
# ("我/他一直没问成他……"): his own "他一直没问成导师……" is an ordinary thing about him.
UNASKED = re.compile(r"^[我他]一直没问成他")


def iso(now: datetime) -> str:
    return now.isoformat(timespec="seconds")


def days_between(earlier: str, now: datetime) -> float:
    return (now - datetime.fromisoformat(earlier)).total_seconds() / 86400


@dataclass(frozen=True)
class Memory:
    id: int
    kind: str
    text: str
    created: str
    source_episode: int | None
    importance: int
    valence: float
    arousal: float
    stability: float
    last_recalled: str
    recall_count: int
    superseded_by: int | None
    merged_from: tuple[int, ...]
    tags: tuple[str, ...]
    pinned: bool
    source: str | None = None  # kind=world: where she saw it
    times: int = 1  # how many times it happened or was said (decision 20)
    gist_due: bool = False  # often enough now to be rewritten as a gist tonight
    pattern: str | None = None  # how one time of it was worded, kept when the text became a gist
    about: str | None = None  # 路过 / 日常 / 本人 / 一辈子, or 待印证 for a rule not yet confirmed
    last_time: str | None = None  # YYYY-MM-DD it last happened; a day counts once
    why: str | None = None  # why it was superseded (WHYS); None while current, or before v3
    happened_on: str | None = None  # YYYY-MM-DD it happened (or will); None before v3
    pact: str | None = None  # a promise between them or his nickname for her: pacts.WHO
    pact_state: str | None = None  # open / kept / dropped; None for the nickname
    outcome: str | None = None  # how it turned out, with the day he said so; the text never changes

    @property
    def unconfirmed(self) -> bool:
        return self.about == UNCONFIRMED

    @property
    def often(self) -> str:
        """How she feels about how often: nothing, 好几回, 很多回 (only for things that happen)."""
        if self.kind not in HAPPENING_KINDS or self.times < 2:
            return ""
        return "好几回了" if self.times < 5 else "很多回了"

    def line(self) -> str:
        """The text as it goes into a prompt: with "（很多回了）" when it kept happening,
        "（还说不准）" for a rule she has not seen confirmed yet, and "→结果：……" once he told her
        how it went."""
        if self.unconfirmed:
            return f"{self.text}（还说不准）"
        if self.pact_state in SETTLED:
            return f"{self.text}（{SETTLED[self.pact_state]}）"
        text = f"{self.text}（{self.often}）" if self.often else self.text
        return f"{text} →结果：{self.outcome}" if self.outcome else text

    def retrievability(self, now: datetime) -> float:
        """A fact about him himself never falls below HIMSELF_R_FLOOR (memory v3 §B4): she may
        be unsure of his hometown after a year, she does not lose it."""
        floor = st.HIMSELF_R_FLOOR if self.kind == "fact" and self.about == "本人" else 0.0
        return st.retrievability(self.stability, days_between(self.last_recalled, now), floor)

    @property
    def ceiling(self) -> float:
        """The most S it can get from recall, a merge or a correction (memory v3 §B4)."""
        return ceiling_of(self.kind, self.text, self.about)

    def fuzzy(self, now: datetime) -> bool:
        return self.retrievability(now) < st.FUZZY_R

    @property
    def alive(self) -> bool:
        return self.superseded_by is None


def about_of(kind: str, about: str | None) -> str | None:
    """路过 is a meal, what he is doing now, today's plan: things that happen. A lasting fact
    filed there ("his friend's cat is called X") counts as 日常, wherever it is read: when it is
    written, when its ceiling is worked out, when it is corrected or merged, when a database
    written before this rule is migrated."""
    return "日常" if kind == "fact" and about == "路过" else about


def ceiling_of(kind: str, text: str, about: str | None) -> float:
    return st.ceiling(about_of(kind, about), unasked=kind == "event" and bool(UNASKED.search(text)))


def capped(stability: float, ceiling: float, was: float = 0.0) -> float:
    """stability, no higher than the ceiling; a memory already above it (written before memory
    v3) does not grow, and is not cut either: lowering what is there is the migration's job."""
    return min(stability, max(was, ceiling))


def _from_row(r: sqlite3.Row) -> Memory:
    return Memory(
        id=r["id"], kind=r["kind"], text=r["text"], created=r["created"],
        source_episode=r["source_episode"], importance=r["importance"],
        valence=r["valence"], arousal=r["arousal"], stability=r["stability"],
        last_recalled=r["last_recalled"], recall_count=r["recall_count"],
        superseded_by=r["superseded_by"],
        merged_from=tuple(json.loads(r["merged_from"] or "[]")),
        tags=tuple(json.loads(r["tags"] or "[]")),
        pinned=bool(r["pinned"]),
        source=r["source"] if "source" in r.keys() else None,
        times=r["times"] if "times" in r.keys() else 1,
        gist_due=bool(r["gist_due"]) if "gist_due" in r.keys() else False,
        pattern=r["pattern"] if "pattern" in r.keys() else None,
        about=r["about"] if "about" in r.keys() else None,
        last_time=r["last_time"] if "last_time" in r.keys() else None,
        why=r["why"] if "why" in r.keys() else None,
        happened_on=r["happened_on"] if "happened_on" in r.keys() else None,
        pact=r["pact"] if "pact" in r.keys() else None,
        pact_state=r["pact_state"] if "pact_state" in r.keys() else None,
        outcome=r["outcome"] if "outcome" in r.keys() else None,
    )
