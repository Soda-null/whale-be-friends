"""Choosing before writing (decision 19): `note`, and what happens when a thing is said again.

A note about the chat itself is refused, a repeat strengthens the old memory and counts one
more time (decision 20), a rule starts unconfirmed (decision 21), a kind over its cap pushes
out its weakest.
"""

from __future__ import annotations

import re
from datetime import datetime

from fish.memory import pacts as pk
from fish.memory import stability as st
from fish.memory.longterm.record import (EVIDENCE_DAYS, HAPPENING_KINDS, RULE_KINDS, UNCONFIRMED, Memory, _from_row,
                                         about_of, iso)
from fish.memory.longterm.rows import Rows
from fish.memory.longterm.words import _DATE, overlap
from fish.memory.scrub import secret
from fish.memory.when import absolute, agree_with_line, day_of, fix_weekday

# Choosing before writing (decision 19): what `note` refuses or folds into an old memory.
REPEAT_SIMILARITY = 0.5  # same kind, this much bigram overlap (dates removed): a repeat
FACT_REPEAT_SIMILARITY = 0.8  # facts differ by one number when he corrects himself; stricter
# Her own life (memory v3 step 7, §B4, waiting for the user's approval: docs/memory_v3_zh.md §11):
# she tells the same thread in new words each night ("数米粒" 27 ways in a year), so a looser bar,
# and no more than KIND_CAPS["self"] of them alive.
SELF_REPEAT_SIMILARITY = 0.35
# One piece of news noted twice in one chat (decision 57): as a fact and as an event in the same
# turn, or again a few turns on in other words. The real store held about thirty such pairs; with
# a tag hit both copies came back and took two of the six places of what his line brings to mind.
SAME_CHAT_KINDS, SAME_CHAT_SIMILARITY = ("fact", "event"), 0.7
KIND_CAPS = {"insight": 20, "howto": 20, "self": 30}  # beyond this the least stable is pushed out
# Notes about the chat itself (he is testing her memory, she could not recall) are not things about
# him: "他欠我一样东西，具体是什么我记不清了" would later read as a debt she knows of.
ABOUT_THE_CHAT = re.compile(r"考我|考她|记性|记不记得|试探我|试探她|测我记|我(?:记不清|想不起|没记住)")
ABOUT_HIM_KINDS = ("fact", "event", "insight", "howto")
GIST_AT = (3, 6, 12, 24, 48, 96)  # times at which a repeated thing is rewritten as a gist
# Words that make a "him himself" note a passing state (a sore throat last week), not who he is.
FOR_NOW = re.compile(r"最近|这几天|这阵子|这周|上周|今天|昨天|刚才|还没好|这次|暂时|目前|这两天")
# ... unless it names something that lasts (memory v3 §B2 D3): "他说妹妹今天打电话来，她叫小雨"
# is his sister, not today's news; "以后提醒他" is a standing thing.
LASTING = re.compile(r"妹|弟|哥|姐|爸|妈|家在|老家|过敏|不耐|不能吃|专业|学校|年级|公司|岗位|生日|最爱"
                     r"|外号|从小|以后")
# A repeat that brings a number or a title the old memory lacks is news, not a repeat (§B2 D4).
_DETAIL = re.compile(r"\d+|《[^》]+》")


class Choosing(Rows):
    def note(self, kind: str, text: str, *, importance: int, now: datetime | None = None,
             said: str = "", heard: str | None = None, **fields) -> Memory | None:
        """How the brain and the routines write (decision 19): choose before writing.

        None: not written (it is about the chat itself, not about him). An older memory:
        this was a repeat, so the old one was recalled instead. Otherwise the new memory;
        if its kind is over its cap, the least stable one of that kind is pushed out.
        said: his line the note came from; for an event, its time words date the note when the
        note's own text names no day (memory v3 §B1). A date that disagrees with the weekday written
        next to it is moved to that weekday first (§B2 D5); a written-out date a few days off the one
        day his line names ("大后天" counted wrong) becomes that day (§14.3, when.agree_with_line).
        heard: "chat" or "close" when the note comes from talking with him; only such a note can
        be a promise between them or his nickname for her (§B2 D1/D2, pacts.py).
        A note that holds a secret (a code, a password) is never written, whoever asks (scrub.py)."""
        now = now or datetime.now()
        if secret(text):
            return None
        text = fix_weekday(text, now.date())
        if said and heard in pk.HEARD:  # "大后天" counted by the model as 05-08 is 05-07 (§14.3)
            # the calendar date, as the date table she reads and absolute() count, so one turn
            # after midnight does not save two different days
            text = agree_with_line(text, said, now.date(), told=now.date())
        if kind in ABOUT_HIM_KINDS and ABOUT_THE_CHAT.search(text):
            return None
        said_as = text  # the words as said, for the day they name (two days named: no one day)
        if heard in pk.HEARD:
            text = absolute(text, now)  # "下个月19号" read next month is not May (§14)
        about = fields.pop("about", None)
        pact = state = None
        if heard in pk.HEARD and kind in RULE_KINDS and pk.ruled_promise(text):
            kind = "fact"  # "他答应我，……" filed as an insight: a rule would fade in weeks
        if heard in pk.HEARD:
            if pk.nickname(text):
                kind, about, pact = "fact", "一辈子", "both"  # what he calls her is a fact for life
            elif (pact := pk.promise(text, kind)) is not None:
                about, state = "一辈子", "open"  # however much it sounds like a plan
        if kind == "self" and text.lstrip().startswith(("他", "她")):
            return None  # her life threads are about her; his things are noted in chat
        # (the persona calls him 他 or 她, FISH_OWNER; she is never the subject in third person)
        if about == "本人" and FOR_NOW.search(text) and not LASTING.search(text):
            about = "日常"  # a state for now is not who he is; it does not go on his card
        about = about_of(kind, about)  # a fact is never 路过: it would sit under the 14-day ceiling
        same = self.repeat_of(kind, text, now, lifelong=about == "一辈子")
        if same is not None and not self.adds_detail(text, same):
            again = self.happened_again(same.id, now)
            return self.raise_to(again, about, fields.get("arousal", 0.0), pact, state)
        twin = self.said_in_chat(kind, text, fields.get("source_episode"))
        if twin is not None and not self.adds_detail(text, twin):
            return self.raise_to(twin, about, fields.get("arousal", 0.0), pact, state)  # said once, not twice
        if kind in RULE_KINDS:
            about = UNCONFIRMED  # however sure the model sounds, one day is one day
            fields["stability"] = st.UNCONFIRMED_DAYS
        elif about in st.ABOUTS:
            fields["stability"] = st.stability_from(about, fields.get("arousal", 0.0))
            fields["pinned"] = about == "一辈子"
        if "stability" in fields:
            importance = st.importance_of(fields["stability"])
        said = said if kind == "event" else ""  # a lasting fact is not dated by "明天" in his line
        fields.setdefault("happened_on", (day_of(said_as, now, said) or now.date()).isoformat())
        new = self.add(kind, text, importance=importance, now=now, **fields)
        self.conn.execute("UPDATE memories SET about = ?, last_time = ?, pact = ?, pact_state = ? WHERE id = ?",
                          (about, iso(now)[:10], pact, state, new.id))
        self.conn.commit()
        new = self.get(new.id)
        cap = KIND_CAPS.get(kind)
        if cap is not None:
            others = [m for m in self.alive(kind) if m.id != new.id and not m.pinned]
            for weakest in sorted(others, key=lambda m: (m.stability, m.id))[:max(0, len(others) + 1 - cap)]:
                self.supersede(weakest.id, new.id, why="cap")
        return new

    def repeat_of(self, kind: str, text: str, now: datetime, *, lifelong: bool = False) -> Memory | None:
        """The live memory this text repeats, if any. Across days too (decision 20): the
        same thing every Friday is one memory that happened many times. A lifelong fact (his
        birthday) said in other words is still the same one: against pinned facts the bar
        is the ordinary one, not the strict one for facts."""
        threshold = {"fact": FACT_REPEAT_SIMILARITY, "self": SELF_REPEAT_SIMILARITY}.get(kind, REPEAT_SIMILARITY)
        best: tuple[float, Memory] | None = None
        for m in self.alive(kind):
            sim = max(overlap(text, m.text), overlap(text, m.pattern) if m.pattern else 0.0)
            if lifelong and m.pinned and sim >= REPEAT_SIMILARITY:
                sim = max(sim, threshold)
            if sim >= threshold and (best is None or sim > best[0]):
                best = (sim, m)
        return best[1] if best else None

    def said_in_chat(self, kind: str, text: str, episode: int | None) -> Memory | None:
        """The fact or event of the same chat that already says this, whichever of the two it was
        filed as. Not counted as happening again: it was said once."""
        if episode is None or kind not in SAME_CHAT_KINDS:
            return None
        best: tuple[float, Memory] | None = None
        for m in self.alive():
            if m.kind in SAME_CHAT_KINDS and m.source_episode == episode:
                sim = overlap(text, m.text)
                if sim >= SAME_CHAT_SIMILARITY and (best is None or sim > best[0]):
                    best = (sim, m)
        return best[1] if best else None

    @staticmethod
    def adds_detail(text: str, old: Memory) -> bool:
        """The new words bring a number or a 《title》 the old memory does not have ("他考了82分"
        after "他考完期中了"): that is news, written as a memory of its own (memory v3 §B2 D4)."""
        known = set(_DETAIL.findall(_DATE.sub("", old.text + " " + (old.pattern or ""))))
        return any(d not in known for d in _DETAIL.findall(_DATE.sub("", text)))

    def raise_to(self, m: Memory, about: str | None, arousal: float = 0.0,
                 pact: str | None = None, state: str | None = None) -> Memory:
        """A repeat that says more of it than the old memory did (memory v3 §B2 D4): the promise
        first filed as 日常, told again as a promise. The old memory rises to the new about, with
        its strength and pin, and becomes the pact; never down. Rules keep their own evidence."""
        if m.kind in RULE_KINDS:
            return m
        rank = {a: i for i, a in enumerate(st.ABOUTS)}
        sets: dict[str, object] = {}
        if about in rank and rank[about] > rank.get(m.about, -1):
            s = max(m.stability, st.stability_from(about, arousal))
            sets.update(about=about, stability=s, importance=max(m.importance, st.importance_of(s)),
                        pinned=int(m.pinned or about == "一辈子"))
        if pact and not m.pact:
            sets.update(pact=pact, pact_state=state)
        if sets:
            cols = ", ".join(f"{c} = ?" for c in sets)
            self.conn.execute(f"UPDATE memories SET {cols} WHERE id = ?", (*sets.values(), m.id))
            self.conn.commit()
        return self.get(m.id)

    def happened_again(self, memory_id: int, now: datetime | None = None) -> Memory:
        """The same thing once more: recalled once; on a new day, one more time, flagged for
        a gist rewrite at 3, 6, 12, ... A rule seen on its third day is confirmed: it gets the
        strength of a fact about him (decision 21)."""
        now = now or datetime.now()
        m = self.touch(memory_id, now)
        today = iso(now)[:10]
        if m.last_time == today:
            return m  # said twice the same day: still one time
        times = m.times + 1
        due = times in GIST_AT and m.kind in HAPPENING_KINDS
        self.conn.execute("UPDATE memories SET times = ?, gist_due = gist_due OR ?, last_time = ? WHERE id = ?",
                          (times, int(due), today, memory_id))
        if m.unconfirmed and times >= EVIDENCE_DAYS:
            s = max(m.stability, st.stability_from("本人", m.arousal))
            self.conn.execute("UPDATE memories SET about = '本人', stability = ?, importance = ? WHERE id = ?",
                              (s, st.importance_of(s), memory_id))
        self.conn.commit()
        return self.get(memory_id)

    def gists_due(self) -> list[Memory]:
        rows = self.conn.execute("SELECT * FROM memories WHERE gist_due = 1 AND superseded_by IS NULL"
                                 " ORDER BY id")
        return [_from_row(r) for r in rows]

    def rewrite_as_gist(self, memory_id: int, text: str) -> Memory:
        """Nightly: the one-off details are gone, the gist stays; same memory, same strength."""
        self.conn.execute("UPDATE memories SET pattern = COALESCE(pattern, text), text = ?, gist_due = 0"
                          " WHERE id = ?", (text, memory_id))
        self.conn.commit()
        return self.get(memory_id)
