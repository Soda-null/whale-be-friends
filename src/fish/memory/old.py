"""Things of his from a while back that she could suddenly think of (decision 58).

A thing that happened to him, that she can still bring up herself, written and last thought of
at least `after_days` ago. Not a promise (those have their own block every turn), not pinned
(in front of her anyway), and with no ending written on it: the ones a friend asks "后来怎么样了"
about. Only looks; thinking of one changes nothing here.
"""

from __future__ import annotations

from datetime import datetime

from fish.memory import stability as st
from fish.memory.longterm import Memory, MemoryStore, days_between


def old_things(store: MemoryStore, now: datetime, *, after_days: int, importance: int) -> list[Memory]:
    return [m for m in store.alive("event")
            if m.importance >= importance and not m.outcome and not m.pact and not m.pinned
            and days_between(m.created, now) >= after_days
            and days_between(m.last_recalled, now) >= after_days
            and m.retrievability(now) >= st.FREE_RECALL_R]
