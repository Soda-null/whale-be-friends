"""The `memories` table, one row at a time: add, get, the live ones, used, replaced.

The base of `MemoryStore`; the other parts (choosing, replacing, promises, cards) build on it.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from fish.memory import stability as st
from fish.memory.longterm.record import KINDS, WHYS, Memory, _from_row, capped, iso
from fish.memory.when import day_of


class Rows:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        kind: str,
        text: str,
        *,
        importance: int,
        valence: float = 0.0,
        arousal: float = 0.0,
        source_episode: int | None = None,
        tags: tuple[str, ...] | list[str] = (),
        pinned: bool = False,
        stability: float | None = None,
        merged_from: tuple[int, ...] | list[int] = (),
        source: str | None = None,
        now: datetime | None = None,
        happened_on: str | None = None,
    ) -> Memory:
        """happened_on: the day it happened; by default the one day its text names, else today."""
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
        now = now or datetime.now()
        importance = st.clamp_importance(importance)
        pinned = pinned or importance >= st.PINNED_IMPORTANCE
        if stability is None:
            stability = st.initial_stability(importance, valence)
        if pinned:
            stability = st.INFINITE
        happened_on = happened_on or (day_of(text, now) or now.date()).isoformat()
        cur = self.conn.execute(
            "INSERT INTO memories (kind, text, created, source_episode, importance, valence, arousal,"
            " stability, last_recalled, recall_count, superseded_by, merged_from, tags, pinned, source,"
            " happened_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?, ?, ?)",
            (kind, text, iso(now), source_episode, importance, valence, arousal, stability,
             iso(now), json.dumps(list(merged_from)), json.dumps(list(tags), ensure_ascii=False),
             int(pinned), source, happened_on),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)

    def get(self, memory_id: int) -> Memory:
        row = self.conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if row is None:
            raise KeyError(f"no memory {memory_id}")
        return _from_row(row)

    def alive(self, kind: str | None = None) -> list[Memory]:
        sql = "SELECT * FROM memories WHERE superseded_by IS NULL"
        args: tuple = ()
        if kind:
            sql += " AND kind = ?"
            args = (kind,)
        return [_from_row(r) for r in self.conn.execute(sql + " ORDER BY id", args)]

    def touch(self, memory_id: int, now: datetime | None = None, *, strengthen: bool = True) -> Memory:
        """She just used this memory: it gets stronger, more so if it was nearly gone, up to its
        ceiling. strengthen=False: used, so fresh again, but no stronger (a fact on her card he
        just mentioned: it is in front of her every turn anyway, memory v3 §B4)."""
        now = now or datetime.now()
        m = self.get(memory_id)
        new_s = st.after_recall(m.stability, m.retrievability(now)) if strengthen else m.stability
        new_s = capped(new_s, m.ceiling, m.stability)
        self.conn.execute(
            "UPDATE memories SET stability = ?, last_recalled = ?, recall_count = recall_count + 1"
            " WHERE id = ?",
            (new_s, iso(now), memory_id),
        )
        self.conn.commit()
        return self.get(memory_id)

    def repoint(self, old_ids: list[int], new_id: int) -> None:
        """Follow-ups about a memory that was replaced are about the one that replaced it."""
        self.conn.execute(f"UPDATE prospective SET source_memory = ? WHERE source_memory IN"
                          f" ({', '.join('?' * len(old_ids))})", (new_id, *old_ids))
        self.conn.commit()

    def supersede(self, old_id: int, new_id: int, *, why: str) -> None:
        if why not in WHYS:
            raise ValueError(f"why must be one of {WHYS}, got {why!r}")
        self.conn.execute("UPDATE memories SET superseded_by = ?, why = ? WHERE id = ?",
                          (new_id, why, old_id))
        self.conn.commit()

    def weaken(self, memory_id: int, now: datetime | None = None) -> Memory:
        """She sees a rule is no longer true: it fades within days instead of lasting."""
        now = now or datetime.now()
        self.conn.execute("UPDATE memories SET stability = MIN(stability, ?), last_recalled = ? WHERE id = ?",
                          (st.WEAKENED_DAYS, iso(now), memory_id))
        self.conn.commit()
        return self.get(memory_id)

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
