"""A memory replaced by a newer one: he corrected her, the night merged near-duplicates.

The old memory is never deleted; `former` reads back what she used to think.
"""

from __future__ import annotations

from datetime import datetime

from fish.memory import stability as st
from fish.memory.longterm.record import (RULE_KINDS, SHOWN_AS_FORMER, UNCONFIRMED, Memory, _from_row, about_of,
                                         capped, ceiling_of, iso)
from fish.memory.longterm.rows import Rows
from fish.memory.scrub import secret
from fish.memory.when import day_of, written_day


def strongest_about(abouts: list[str | None]) -> str | None:
    """What a merged memory is about: the strongest of its sources (一辈子 > 本人 > 日常 > 路过).
    It stays unconfirmed only when every source was; a merge is not evidence."""
    known = [a for a in abouts if a in st.ABOUTS]
    if known:
        return max(known, key=st.ABOUTS.index)
    return UNCONFIRMED if abouts and all(a == UNCONFIRMED for a in abouts) else None


def why_before_v3(old: Memory, new: Memory) -> str:
    """A memory superseded before the `why` column existed: guessed the way the v3 migration
    writes it (docs/memory_v3_zh.md §8, scripts/migrate_v3.py). A source of a merge was merged;
    a rule replaced by another rule, not merged, was pushed out by the cap; anything else was
    an update."""
    if old.id in new.merged_from:
        return "merge"
    if old.kind in RULE_KINDS and new.kind == old.kind:
        return "cap"
    return "update"


class Replacing(Rows):
    def correct(
        self, old_id: int, text: str, *, importance: int | None = None,
        now: datetime | None = None,
    ) -> Memory:
        """He corrected her: a new memory replaces the old one, which stays as 'what she used to think'.
        It keeps what the old one was about (his major corrected is still about him himself), its
        pact, its outcome, and the day it happened unless the new words name another one. New words
        that hold a secret change nothing: the old memory is returned as it was."""
        old = self.get(old_id)
        if secret(text):
            return old
        now = now or datetime.now()
        importance = old.importance if importance is None else importance
        fresh = st.initial_stability(importance, old.valence)
        stability = max(fresh, old.stability) if fresh != st.INFINITE else st.INFINITE
        stability = capped(stability, ceiling_of(old.kind, text, old.about), old.stability)
        new = self.add(
            old.kind, text, importance=importance, valence=old.valence, arousal=old.arousal,
            source_episode=old.source_episode, tags=old.tags, pinned=old.pinned,
            stability=stability, now=now,
            happened_on=(d.isoformat() if (d := day_of(text, now)) else old.happened_on),
        )
        self.conn.execute("UPDATE memories SET about = ?, last_time = ?, pact = ?, pact_state = ?, outcome = ?"
                          " WHERE id = ?", (about_of(old.kind, old.about), iso(now)[:10], old.pact,
                                            old.pact_state, old.outcome, new.id))
        self.supersede(old_id, new.id, why="correct")
        self.repoint([old_id], new.id)
        return self.get(new.id)

    def merge(self, ids: list[int], text: str, *, now: datetime | None = None) -> Memory:
        """Nightly: several near-duplicates become one, more stable (up to its ceiling), with its sources noted.
        What it is about, whether it is pinned, the pact (still open if any source was), the latest
        outcome and the day it last happened carry over; so does
        the day it happened (the latest of its sources), unless the merged words write a date."""
        olds = [self.get(i) for i in ids]
        if not olds:
            raise ValueError("merge needs at least one memory")
        now = now or datetime.now()
        # only a date written out in the merged words: their "明天" was said on its source's
        # day, and read at night it would land a day late
        latest = max(datetime.fromisoformat(o.created) for o in olds)
        tags: list[str] = []
        for o in olds:
            tags += [t for t in o.tags if t not in tags]
        about = about_of(olds[0].kind, strongest_about([o.about for o in olds]))
        strongest = max(o.stability for o in olds)
        new = self.add(
            olds[0].kind, text,
            importance=max(o.importance for o in olds),
            valence=sum(o.valence for o in olds) / len(olds),
            arousal=max(o.arousal for o in olds),
            source_episode=olds[0].source_episode, tags=tags,
            pinned=any(o.pinned for o in olds),
            stability=capped(st.after_merge(*(o.stability for o in olds)),
                             ceiling_of(olds[0].kind, text, about), strongest),
            merged_from=ids, now=now,
            happened_on=(d.isoformat() if (d := written_day(text, latest.date()))
                         else max((o.happened_on for o in olds if o.happened_on), default=None)),
        )
        for o in olds:
            self.supersede(o.id, new.id, why="merge")
        self.repoint(ids, new.id)
        times = sum(o.times for o in olds)  # both counts carry over (decision 20)
        last = max((o.last_time for o in olds if o.last_time), default=None)
        pact = next((o.pact for o in olds if o.pact), None)
        states = [o.pact_state for o in olds if o.pact_state]
        outcome = next((o.outcome for o in sorted(olds, key=lambda o: o.created, reverse=True) if o.outcome), None)
        self.conn.execute("UPDATE memories SET times = ?, about = ?, last_time = ?, pact = ?, pact_state = ?,"
                          " outcome = ? WHERE id = ?",
                          (times, about, last, pact,
                           "open" if "open" in states else next(iter(states), None), outcome, new.id))
        self.conn.commit()
        return self.get(new.id)

    def former(self, memory_id: int) -> Memory | None:
        """The memory this one replaced, if any ('你之前说是周五来着'): only a correction or an
        update, never a source it was merged from or a rule a cap pushed out."""
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by = ? ORDER BY id DESC", (memory_id,)
        ).fetchall()
        new = self.get(memory_id) if rows else None
        for old in map(_from_row, rows):
            if (old.why or why_before_v3(old, new)) in SHOWN_AS_FORMER:
                return old
        return None
