"""What belongs to the two of them (decision 61, docs/ours_design_zh.md). Version 1: inside jokes.

Her other memories retell ("他 10-30 闹钟没响迟到了"). A joke is its exact words ("叛徒闹钟"): one
character off and it is not the joke. And a memory grows by being recalled, while a joke is one
only once somebody brings it back and the other picks it up. So:

- the close of a chat may name a saying the chat made (`offer`): a candidate, kept only when the
  words are in the chat word for word, he took part (said them or laughed), they hold no secret,
  they are not everyday words of his, and they are not a joke she already has;
- he says a candidate again on another day: it is a joke. Or she tries it once, a day or more
  later, and his next line says it or laughs. Two tries he lets pass: dropped, never tried again.
  A candidate that is nothing after CANDIDATE_DAYS is forgotten;
- each turn (`section`): a joke his line says is marked, so she does not read it literally; else
  one that fits what he is saying may be handed to her, to use or not. One a turn, the same one
  again only after REST_DAYS, PER_DAY of them a day;
- QUIET_DAYS without either saying it: old. Never handed to her, known again the moment he says it.

Kept as one JSON list in the relationship ledger (as the weekday patterns are). No model, no SQL.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from typing import Any

from fish.memory.patterns import day_of
from fish.memory.relationship import Relationship
from fish.memory.retrieval import BigramEmbedder
from fish.memory.scrub import secret
from fish.memory.window import Window

KEY = "ours"
CANDIDATE, ALIVE, OLD, DROPPED = "candidate", "alive", "old", "dropped"
WHO = ("him", "her", "both")
STATE_WORDS = {CANDIDATE: "候选", ALIVE: "成了", OLD: "旧了", DROPPED: "放下了"}  # for `fish show`
MIN_LEN, MAX_LEN = 2, 12  # characters of the saying itself
ORIGIN_CHARS = 60
PER_CHAT = 2  # one chat makes this many sayings at most
COMMON_DAYS = 3  # he said these words on this many earlier days: everyday words, not a joke
MAX_CANDIDATES = 10
CANDIDATE_DAYS = 14  # a candidate nobody brought back in this long is forgotten
TRIES = 2  # she tried it this many times and he let it pass: dropped
QUIET_DAYS = 30  # neither said it in this long: old
POOL = 20  # jokes she may be handed; beyond this the ones longest unsaid go old
REST_DAYS = 3  # after she said one, it is not handed to her again for this long
PER_DAY = 2  # jokes she said today, after which none is handed to her
OFFER_RELEVANCE = 0.3  # how much his line must have to do with a joke for it to be handed to her
LAUGH = re.compile(r"哈哈|嘿嘿|嘻嘻|笑死|笑出|笑哭|笑了|绝了|hhh|233|😂|🤣|😆"
                   r"|\[表情：[^\]]*(?:笑|呲牙|捂脸)[^\]]*\]", re.I)
_EDGES = " \t\n\"'“”‘’「」『』《》，。！？!?~～…"


@dataclass
class Joke:
    words: str  # the saying itself, word for word
    origin: str  # how it came about, one line
    who: str = "both"  # who said it first: WHO
    state: str = CANDIDATE
    born: str = ""  # YYYY-MM-DD of the chat that made it
    his: int = 0  # times he has said it since
    hers: int = 0  # times she has
    his_last: str = ""  # YYYY-MM-DD
    hers_last: str = ""
    tries: int = 0  # times she tried it as a candidate and he let it pass
    waiting: bool = False  # she just tried it: his next line tells

    tags = ()  # read by an Embedder, as a memory's are

    @property
    def text(self) -> str:
        return f"{self.words}：{self.origin}"

    @property
    def last(self) -> str:
        """The last day anyone said it."""
        return max(self.born, self.his_last, self.hers_last)

    @property
    def times(self) -> int:
        return 1 + self.his + self.hers  # the chat that made it counts once


def _days(since: str, today: date) -> int:
    try:
        return (today - date.fromisoformat(since)).days
    except ValueError:
        return 10 ** 6  # no day written: long ago


def aged(jokes: list[Joke], today: date) -> list[Joke]:
    """The list as it stands today: stale candidates gone, jokes long unsaid gone old."""
    kept = [j for j in jokes if j.state != CANDIDATE or _days(j.born, today) <= CANDIDATE_DAYS]
    for j in kept:
        if j.state == ALIVE and _days(j.last, today) > QUIET_DAYS:
            j.state = OLD
    alive = sorted((j for j in kept if j.state == ALIVE), key=lambda j: j.last, reverse=True)
    for j in alive[POOL:]:
        j.state = OLD
    return kept


class Ours:
    def __init__(self, relationship: Relationship, window: Window) -> None:
        self.relationship = relationship
        self.window = window

    # --- the ledger --------------------------------------------------------------

    def all(self) -> list[Joke]:
        try:
            rows = json.loads(self.relationship.get(KEY) or "[]")
        except ValueError:
            return []
        names = {f.name for f in fields(Joke)}
        return [Joke(**{k: v for k, v in r.items() if k in names})
                for r in rows if isinstance(r, dict) and r.get("words")] if isinstance(rows, list) else []

    def save(self, jokes: list[Joke], now: datetime) -> None:
        self.relationship.set(KEY, json.dumps([asdict(j) for j in jokes], ensure_ascii=False), now)

    def today(self, now: datetime) -> list[Joke]:
        """The list as it stands now, saved when a day's passing changed it."""
        before = self.all()
        was = [asdict(j) for j in before]
        jokes = aged(before, day_of(now))
        if [asdict(j) for j in jokes] != was:
            self.save(jokes, now)
        return jokes

    # --- a chat is over: sayings it may have made --------------------------------

    def offer(self, named: list[dict[str, str]], episode_id: int, at: datetime) -> list[Joke]:
        """The sayings the close of a chat named, through the gates; the ones kept, as candidates."""
        his, hers = self.window.said_in(episode_id)
        jokes = self.today(at)
        new: list[Joke] = []
        for n in named:
            if len(new) >= PER_CHAT:
                break
            words = str(n.get("words") or "").strip(_EDGES)
            origin = str(n.get("origin") or "").strip()[:ORIGIN_CHARS]
            if not MIN_LEN <= len(words) <= MAX_LEN or not origin:
                continue
            if words not in his and words not in hers:
                continue  # not said in this chat: made up at the close
            if words not in his and not LAUGH.search(his):
                continue  # hers alone and he did not laugh: nothing of the two of them yet
            if secret(words) or secret(origin):
                continue
            if any(j.words in words or words in j.words for j in jokes):
                continue  # a joke she has, or one already dropped
            if self.window.days_he_said(words, episode_id) >= COMMON_DAYS:
                continue  # he says this all the time
            who = "him" if words not in hers else "her" if words not in his else n.get("who")
            joke = Joke(words, origin, who if who in WHO else "both", born=day_of(at).isoformat())
            jokes.append(joke)
            new.append(joke)
        if new:
            waiting = [j for j in jokes if j.state == CANDIDATE]
            for j in sorted(waiting, key=lambda j: j.born)[:max(0, len(waiting) - MAX_CANDIDATES)]:
                jokes.remove(j)
            self.save(jokes, at)
        return new

    # --- a turn is over: who said what --------------------------------------------

    def on_chatted(self, m: Any) -> None:
        """Counts who said which joke in this turn (a `Chatted`), and settles a candidate: he
        said it again on another day, or her try was picked up, or let pass."""
        jokes = self.today(m.at)
        was = [asdict(j) for j in jokes]
        day = day_of(m.at).isoformat()
        for j in jokes:
            if j.state == DROPPED:
                continue
            he_said = j.words in m.he
            if j.waiting:  # she tried it in her last line: this line of his is the answer
                j.waiting = False
                if he_said or LAUGH.search(m.he):
                    j.state = ALIVE
                else:
                    j.tries += 1
                    if j.tries >= TRIES:
                        j.state = DROPPED
                        continue
            if he_said:
                if j.state == OLD or j.state == CANDIDATE and day != j.born:
                    j.state = ALIVE
                j.his += 1
                j.his_last = day
            if j.words in m.she:
                if j.state == CANDIDATE:
                    j.waiting = day != j.born  # said again in the chat that made it is no try
                j.hers += 1
                j.hers_last = day
        if [asdict(j) for j in jokes] != was:
            self.save(jokes, m.at)

    # --- a turn begins: what his line has to do with their jokes --------------------

    def section(self, said: str, now: datetime, embedder: Any | None = None, him: str = "他") -> str:
        """The "你们俩的梗" section of the prompt, "" when there is nothing to say. A joke his line
        says is marked, however old. When he says none, one that fits his line may be handed to
        her: to use or not."""
        jokes = self.today(now)
        today = day_of(now)
        day = today.isoformat()
        said_now = [j for j in jokes if j.words in said
                    and (j.state in (ALIVE, OLD) or j.state == CANDIDATE and j.born != day)]
        if said_now:
            return "\n".join(_marked(j, him) for j in said_now)
        if sum(j.hers_last == day for j in jokes) >= PER_DAY:
            return ""
        embedder = embedder or BigramEmbedder()
        fits = [(embedder.relevance(said, j), j) for j in jokes
                if (j.state == ALIVE or j.state == CANDIDATE and j.born != day and not j.waiting)
                and (not j.hers_last or _days(j.hers_last, today) >= REST_DAYS)]
        fits = [(r, j) for r, j in fits if r >= OFFER_RELEVANCE]
        if not fits:
            return ""
        return _handed(max(fits, key=lambda f: (f[0], f[1].last))[1], him)


def _when(j: Joke) -> str:
    return f"{j.born[5:]} 聊出来的" if j.born else "以前聊出来的"


def _marked(j: Joke, him: str) -> str:
    line = f"- ★{him}刚说到「{j.words}」——{_when(j)}：{j.origin}"
    if j.state == CANDIDATE:
        return line + f"（上回才聊出来，{him}又说了，这下算你俩的梗了）"
    if j.state == OLD:
        return line + f"（好久没人提了，{him}还记得）"
    return line + (f"（你俩说过 {j.times} 回了）" if j.times >= 3 else "")


def _handed(j: Joke, him: str) -> str:
    if j.state == CANDIDATE:
        return (f"- 「{j.words}」是上回聊出来的说法，还不算你俩的梗：想试着说一次看{him}接不接也行，"
                f"不试也行——{_when(j)}：{j.origin}")
    return f"- 「{j.words}」这会儿用得上：想用就用，不用也行——{_when(j)}：{j.origin}"
