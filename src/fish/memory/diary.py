"""Diary: one short entry per day about her own (invented) life."""

from __future__ import annotations

import sqlite3

from fish.memory.scrub import redact


class Diary:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def write(self, day: str, text: str) -> None:
        """A sentence that holds a secret is left out (scrub.py)."""
        self.conn.execute(
            "INSERT OR REPLACE INTO diary (day, text) VALUES (?, ?)", (day, redact(text))
        )
        self.conn.commit()

    def days(self) -> set[str]:
        return {r["day"] for r in self.conn.execute("SELECT day FROM diary")}

    def get(self, day: str) -> str:
        row = self.conn.execute("SELECT text FROM diary WHERE day = ?", (day,)).fetchone()
        return row["text"] if row else ""

    def before(self, day: str) -> str:
        """The latest diary written for a day before this one; "" if none."""
        row = self.conn.execute("SELECT text FROM diary WHERE day < ? ORDER BY day DESC LIMIT 1", (day,)).fetchone()
        return row["text"] if row else ""

    def recent(self, days: int = 3) -> list[tuple[str, str]]:
        rows = self.conn.execute(
            "SELECT day, text FROM diary ORDER BY day DESC LIMIT ?", (days,)
        ).fetchall()
        return [(r["day"], r["text"]) for r in reversed(rows)]
