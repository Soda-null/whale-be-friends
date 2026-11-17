"""What is always in front of her: her card of facts about him, the how-to card, and the
other fixed reads (plans for a day, what she saw lately)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from fish.memory import stability as st
from fish.memory.longterm.record import Memory, _from_row, iso
from fish.memory.longterm.rows import Rows

PROFILE_IMPORTANCE = 8  # facts at or above this importance form the always-present profile
PROFILE_SIZE = 12
# Card facts that keep him safe come right after the pinned ones (memory v3 §B3).
SAFETY = re.compile(r"过敏|不耐(?!烦)|病|药")
# A card fact about someone around him: one that starts with another name ("大壮是他表哥……",
# "团子是只仓鼠"), or with his family, friends or people at work ("他表哥……", "他合租的室友叫……").
# They go on the card after the facts about him himself, so many friends never push his school or
# his home off it. Kinship and social words of the language, not of any one friend's story.
RELATIONS = ("爸|妈|父亲|母亲|爷爷|奶奶|姥姥|姥爷|外公|外婆|祖|[表堂]?[哥姐弟妹]|兄|叔|伯|姨|舅|姑|侄|甥"
             "|儿子|女儿|孩子|老婆|老公|媳妇|对象|男朋友|女朋友|前任|室友|舍友|同学|同事|朋友|闺蜜|发小"
             "|老师|导师|老板|领导|上司|组长|经理|师兄|师姐|师弟|师妹|邻居|房东")
ABOUT_OTHERS = re.compile(rf"^(?![他她])|^[他她](?:[^，。,；;的]{{0,4}}的)?(?:{RELATIONS})")


def card_order(m: Memory) -> tuple:
    """Sort key of her card: pinned, then safety, then facts about him himself before facts
    about people around him, each by the latest day it came up."""
    last = date.fromisoformat(m.last_time or m.created[:10])
    return (not m.pinned, not SAFETY.search(m.text), bool(ABOUT_OTHERS.search(m.text.lstrip())),
            -last.toordinal(), -m.importance, m.id)


class Cards(Rows):
    def profile(self, limit: int = PROFILE_SIZE) -> list[Memory]:
        """The facts she always keeps in mind (her card): pinned first, then what keeps him
        safe (allergies, illness, medicine), then what is about him himself, then the people
        around him (ABOUT_OTHERS), each by when it last came up. Facts about
        him himself (about = 本人, decision 21) always qualify. Not by stability (memory v3
        §B3): how strongly she holds a fact says nothing about whether it is who he is now.
        His nickname is on it (a pact with no state); a promise is not, whatever its state: an
        open one has its own block (`pacts`), a settled one is pinned and comes back when
        recalled (§B3), so kept promises never crowd his allergy off the card."""
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL AND pact_state IS NULL"
            " AND ((kind = 'fact' AND (pinned = 1 OR importance >= ? OR about = '本人'))"
            "      OR (pact IS NOT NULL AND pinned = 1))", (PROFILE_IMPORTANCE,)
        )
        return sorted(map(_from_row, rows), key=card_order)[:limit]

    def howto_card(self, limit: int = 8) -> list[Memory]:
        """How to get along with him: the rules she has drawn, always in mind (decision 11).
        A rule she saw is outdated (weakened) leaves the card until it is seen again."""
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL AND kind = 'howto' AND stability > ?"
            " ORDER BY importance DESC, stability DESC, id DESC LIMIT ?", (st.WEAKENED_DAYS, limit)
        )
        return [_from_row(r) for r in rows]

    def planned_for(self, days: list[date]) -> list[Memory]:
        """Things he said would happen on these days (an exam, a trip), said before the day came:
        what the "today" section reminds her of (memory v3 §B3). A note written on the day it is
        about is not a plan, it is news, and the chat it came from is still in front of her.
        Events only: a fact is who he is, not something that happens on a day."""
        wanted = [d.isoformat() for d in days]
        rows = self.conn.execute(
            f"SELECT * FROM memories WHERE superseded_by IS NULL AND kind = 'event'"
            f" AND happened_on IN ({', '.join('?' * len(wanted))}) AND substr(created, 1, 10) < happened_on"
            " ORDER BY happened_on, id", wanted)
        return [_from_row(r) for r in rows]

    def count_of_kind(self, kind: str, ids: list[int]) -> int:
        """How many of these memories are of this kind (her free time counts its self notes)."""
        if not ids:
            return 0
        marks = ",".join("?" * len(ids))
        return self.conn.execute(f"SELECT COUNT(*) FROM memories WHERE kind = ? AND id IN ({marks})",
                                 [kind, *ids]).fetchone()[0]

    def seen_recently(self, now: datetime, days: int = 7) -> list[Memory]:
        """World memories from the last `days`, newest first (also the URLs not to reopen)."""
        since = iso(now - timedelta(days=days))
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE kind = 'world' AND created >= ? ORDER BY id DESC", (since,)
        )
        return [_from_row(r) for r in rows]
