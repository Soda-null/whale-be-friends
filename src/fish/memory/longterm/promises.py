"""Promises between them and how his things turned out (memory v3 §B1-B3).

The open promises, making and settling one, the result hung on an event, and which memory a
follow-up is about.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from fish.memory import pacts as pk
from fish.memory import stability as st
from fish.memory.longterm.record import Memory, _from_row, iso
from fish.memory.longterm.rows import Rows
from fish.memory.longterm.words import overlap
from fish.memory.scrub import secret

PACT_LINK = 0.3  # overlap at which a follow-up is about an open promise (memory v3 §B1)
SOURCE_LINK = 0.3  # overlap at which a follow-up is about a note from the same chat (§B1)
# Things that end in a result she will want to hear (memory v3 §B2): an exam, an interview, a move.
# 考虑 is thinking it over, not an exam.
OUTCOME_WORDS = re.compile(r"考(?!虑)|面试|述职|答辩|演示|汇报|比赛|体检|复查|看病|看房|搬家|录取|申请|结题|评审")
OUTCOME_DAYS = 30  # how far back an event can still get its result at the close
OUTCOMES_SHOWN = 3


class Promises(Rows):
    def pacts(self, limit: int = pk.PACTS_SHOWN, *, settled: bool = False) -> list[Memory]:
        """The promises between them still open, latest first (memory v3 §B3): always in front of
        her in a block of their own, so they leave her card. settled: he asks what was promised
        (pacts.asks_pact), so the ones kept or called off come after the open ones (§14)."""
        states = "('open', 'kept', 'dropped')" if settled else "('open')"
        rows = self.conn.execute(
            f"SELECT * FROM memories WHERE superseded_by IS NULL AND pact_state IN {states}"
            " ORDER BY pact_state = 'open' DESC, COALESCE(last_time, substr(created, 1, 10)) DESC, id DESC"
            " LIMIT ?", (limit,)
        )
        return [_from_row(r) for r in rows]

    def make_pact(self, memory_id: int, who: str) -> Memory:
        """His own line made a promise and the note of it was not taken for one (memory v3 §14):
        it becomes an open pact, pinned, for life; a rule or an insight becomes a fact."""
        if who not in pk.WHO:
            raise ValueError(f"who must be one of {pk.WHO}, got {who!r}")
        self.conn.execute(
            "UPDATE memories SET kind = CASE WHEN kind IN ('insight', 'howto') THEN 'fact' ELSE kind END,"
            " about = '一辈子', pinned = 1, stability = ?, importance = ?, pact = ?, pact_state = 'open'"
            " WHERE id = ?", (st.INFINITE, st.importance_of(st.INFINITE), who, memory_id))
        self.conn.commit()
        return self.get(memory_id)

    def pact_for(self, text: str) -> Memory | None:
        """The open promise a follow-up is about ("期末考完去海边了吗" and the promise of the
        sea): the one it overlaps most, at PACT_LINK or more. A shared tag alone is not enough:
        "问问他期末考得怎么样" says 期末 too, and a linked follow-up never runs out."""
        best = max(self.pacts(limit=-1), key=lambda p: overlap(text, p.text), default=None)
        return best if best is not None and overlap(text, best.text) >= PACT_LINK else None

    def settle(self, memory_id: int, state: str, now: datetime | None = None) -> Memory:
        """He kept a promise, or said it is off: it leaves the block. The memory stays pinned and
        its words stay as they were, read with "（兑现了）" when it is recalled; never on her card."""
        if state not in pk.STATES[1:]:
            raise ValueError(f"a pact is settled as kept or dropped, got {state!r}")
        now = now or datetime.now()
        self.conn.execute("UPDATE memories SET pact_state = ?, last_time = ? WHERE id = ?",
                          (state, iso(now)[:10], memory_id))
        self.conn.commit()
        return self.get(memory_id)

    def set_outcome(self, memory_id: int, text: str, now: datetime | None = None) -> Memory | None:
        """How something turned out ("考得还行，估计八十来分"), hung on the memory of the thing
        itself with the day he said it (memory v3 §B1), instead of a memory of its own that fades
        in a week. The text stays as it was; a later result replaces an earlier one. Hearing it is
        using the memory once. None when the result holds a secret: nothing is written."""
        if secret(text):
            return None
        now = now or datetime.now()
        said = f"（{now.month}月{now.day}日说的）"
        self.conn.execute("UPDATE memories SET outcome = ? WHERE id = ?", (text.strip() + said, memory_id))
        self.conn.commit()
        return self.touch(memory_id, now)

    def awaiting_outcome(self, chat: str, now: datetime, *, also: set[int] | frozenset[int] = frozenset()
                         ) -> list[Memory]:
        """What the close may hang a result on (memory v3 §B2): first the memories the follow-ups
        she asked in this chat are about (`also`), then his events of the last OUTCOME_DAYS that
        end in a result (an exam, an interview, a move) and that this chat touched (one of those
        words or one of its tags comes up in `chat`), latest first. Nothing still to come: a result
        needs the day to have passed. A promise is not here; it is kept or dropped (`settle`)."""
        since = (now.date() - timedelta(days=OUTCOME_DAYS)).isoformat()
        today = now.date().isoformat()
        asked = [m for m in self.alive() if m.id in also and not m.pact]
        touched = []
        for m in reversed(self.alive("event")):
            words = OUTCOME_WORDS.findall(m.text)
            if (m.id not in also and words and not m.pact and not m.text.lstrip().startswith("我")
                    and since <= (m.happened_on or m.created[:10]) <= today
                    and any(w in chat for w in [*words, *(t for t in m.tags if len(t) >= 2)])):
                touched.append(m)
        return (asked + touched)[:OUTCOMES_SHOWN]

    def source_for(self, text: str, episode_id: int) -> Memory | None:
        """The note of the same chat a follow-up is about ("演唱会看得怎么样" and the concert he
        mentioned, memory v3 §B1): of his events and facts from that chat whose tag the follow-up
        says, or that it overlaps at SOURCE_LINK or more, the one it overlaps most. Never an open
        promise: that link is `pact_for`'s, stricter, since such a follow-up never runs out."""
        notes = [m for m in self.alive() if m.source_episode == episode_id and m.kind in ("event", "fact")
                 and m.pact_state != "open"
                 and (overlap(text, m.text) >= SOURCE_LINK or any(len(t) >= 2 and t in text for t in m.tags))]
        return max(notes, key=lambda m: (overlap(text, m.text), -m.id), default=None)
