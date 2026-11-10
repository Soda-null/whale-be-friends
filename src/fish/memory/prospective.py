"""Prospective memory: things she means to ask him on a given day (§5.7)."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from fish.memory.longterm import iso
from fish.memory.retrieval import BigramEmbedder
from fish.memory.scrub import secret

# A friend keeps a few things in mind, asks within a day or so, and lets the rest go (decision 17).
GRACE_DAYS = 1  # an open follow-up this many days past due is given up on
MAX_OPEN = 5  # no new follow-up while this many are open
SAME_AS = 0.5  # bigram overlap at which a new follow-up repeats an open one
DUE_SHOWN = 2  # due follow-ups offered to her in one turn
# One question in other words ("问他科目二有没有消息" / "科目二那边后来有消息了吗") scores far under SAME_AS:
# the real store held three copies of one question with three due days, and she asked on all three
# mornings. Without the words every question has, the shorter one mostly lies in the longer.
FILLER = re.compile(r"问问他|问他|到底|后来|那边|怎么样|\d+月\d+日|[的了吗没有得，。？?！、\s]")
SAME_TOPIC, SAME_TOPIC_LONGER = 0.5, 0.4  # share of the shorter question's bigrams found in the other, and of the longer's


@dataclass(frozen=True)
class Followup:
    id: int
    text: str
    due: str  # YYYY-MM-DD
    created: str
    source_memory: int | None  # the memory it is about: a note of the same chat, or an open promise
    status: str  # open | asked | expired | settled (he told her before she asked)
    asked_episode: int | None = None  # the chat she asked it in (memory v3 §B1)


def _overlap(a: str, b: str) -> float:
    x, y = BigramEmbedder.bigrams(a), BigramEmbedder.bigrams(b)
    return 2 * len(x & y) / (len(x) + len(y)) if x and y else 0.0


def same_topic(a: str, b: str) -> bool:
    """Two follow-ups ask about one thing, however each is worded."""
    x, y = BigramEmbedder.bigrams(FILLER.sub("", a)), BigramEmbedder.bigrams(FILLER.sub("", b))
    if not x or not y:
        return False
    both = len(x & y)  # the longer one counts too: "期末考得怎么样" is not "期末考完去海边了吗"
    return both / min(len(x), len(y)) >= SAME_TOPIC and both / max(len(x), len(y)) >= SAME_TOPIC_LONGER


def _from_row(r: sqlite3.Row) -> Followup:
    return Followup(r["id"], r["text"], r["due"], r["created"], r["source_memory"], r["status"],
                    r["asked_episode"] if "asked_episode" in r.keys() else None)


class ProspectiveStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, text: str, due: str, *, source_memory: int | None = None,
            now: datetime | None = None) -> Followup | None:
        """None when she already has enough on her mind, or already means to ask this (the same
        words, the same thing in other words, or the same memory it is about), or it holds a
        secret (scrub.py)."""
        now = now or datetime.now()
        if secret(text):
            return None
        held = self.open()
        if len(held) >= MAX_OPEN or any(_overlap(text, f.text) >= SAME_AS or same_topic(text, f.text)
                                        or (source_memory is not None and f.source_memory == source_memory)
                                        for f in held):
            return None
        cur = self.conn.execute(
            "INSERT INTO prospective (text, due, created, source_memory, status)"
            " VALUES (?, ?, ?, ?, 'open')",
            (text, due, iso(now), source_memory),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)

    def get(self, followup_id: int) -> Followup:
        row = self.conn.execute("SELECT * FROM prospective WHERE id = ?", (followup_id,)).fetchone()
        if row is None:
            raise KeyError(f"no follow-up {followup_id}")
        return _from_row(row)

    def open(self) -> list[Followup]:
        rows = self.conn.execute("SELECT * FROM prospective WHERE status = 'open' ORDER BY due, id")
        return [_from_row(r) for r in rows]

    def due(self, now: datetime | None = None) -> list[Followup]:
        """Open follow-ups whose day has come: these go into the prompt as '你想问他的'."""
        today = (now or datetime.now()).date().isoformat()
        rows = self.conn.execute(
            "SELECT * FROM prospective WHERE status = 'open' AND due <= ? ORDER BY due, id", (today,)
        )
        return [_from_row(r) for r in rows]

    def close(self, followup_id: int, status: str = "asked", *, episode: int | None = None) -> None:
        """episode: the chat she asked it in; its close hears how it went (memory v3 §B2)."""
        self.conn.execute("UPDATE prospective SET status = ?, asked_episode = COALESCE(?, asked_episode)"
                          " WHERE id = ?", (status, episode, followup_id))
        self.conn.commit()

    def asked_in(self, episode_id: int) -> list[Followup]:
        rows = self.conn.execute("SELECT * FROM prospective WHERE status = 'asked' AND asked_episode = ?"
                                 " ORDER BY id", (episode_id,))
        return [_from_row(r) for r in rows]

    def expire(self, now: datetime | None = None, grace_days: int = GRACE_DAYS) -> list[Followup]:
        """Nightly: give up on follow-ups she never got to ask; returns them. They are only closed,
        never turned into memories (memory v3). One about a promise still open between them
        ("去海边了没") is never given up: the promise has no day it runs out."""
        cutoff = ((now or datetime.now()).date() - timedelta(days=grace_days)).isoformat()
        rows = self.conn.execute(
            "SELECT * FROM prospective p WHERE status = 'open' AND due < ? AND NOT EXISTS"
            " (SELECT 1 FROM memories m WHERE m.id = p.source_memory AND m.superseded_by IS NULL"
            "  AND m.pact_state = 'open') ORDER BY due, id", (cutoff,)
        ).fetchall()
        expired = [_from_row(r) for r in rows]
        for f in expired:
            self.close(f.id, "expired")
        return expired
