"""Night steps 4a–5c: a diary or letter an earlier night failed to write (decision 53); her
diary and her own life (no diary for days before she met him; the diary call also rewrites the
phase's sentence, slowly); the phase steps a fifth of the way toward what the day showed
(decision 13); about once a month she looks back at herself and may move a slider a notch."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from fish.brain import away, moment_line
from fish.cottage import invented_act
from fish.memory import Diary, Pastimes, TraitStore, first_message_at
from fish.routines.night.context import Night, day_bounds, fish_day
from fish.routines.night.missed import EPISODES_LOOKED_AT, chat_days

CATCH_UP_PER_NIGHT = 2  # days; a long outage is made up for over a few nights, oldest first
SELF_NOTES_PER_NIGHT = 1  # decision 19: her life grows by one thread a night at most
GROWTH_EVERY_DAYS = 30  # layer A looks back about once a month
FORGOTTEN_MOOD = "（那天的心情记不太清了）"


def strongest(notes: list[tuple[str, int]], n: int) -> list[tuple[str, int]]:
    """Her life grows by at most n threads a night (decision 19): keep the most important."""
    return sorted(notes, key=lambda x: -x[1])[:n]


def _gists_of(night: Night, day: date) -> list[str]:
    todays = [e for e in night.episodes.recent(EPISODES_LOOKED_AT)
              if fish_day(datetime.fromisoformat(e.started)) == day and (e.gist or e.summary)]
    return [e.gist or e.summary[:60] for e in reversed(todays)]


def _ask_diary(night: Night, day: date, mood: str, gists: list[str]) -> tuple[str, list[tuple[str, int]], str, list[str] | None]:
    """Everything the diary of one day is written from, and the reply; nothing is stored here."""
    conn, store, now, brain = night.conn, night.store, night.now, night.brain
    start, end = day_bounds(day)
    threads = [m.line() for m in store.alive("self")][-5:]
    seen = [m.text for m in store.seen_recently(now, (night.day - day).days + 2)
            if fish_day(datetime.fromisoformat(m.created)) == day]
    leisure = [moment_line(m) for m in Pastimes(conn).moments(start, end) if away(m)]
    home: list[str] | None = None
    if brain.cottage is not None:  # what she did at home, meals, food gone off (decision 26)
        try:
            home = brain.cottage.between(start, end)
        except ValueError:
            home = []
    prev = night.phases.current()
    text, notes, line = night.thinker.diary(day.isoformat(), mood, threads, gists,
                                            Diary(conn).before(day.isoformat()), seen=seen, phase_line=prev.line,
                                            tone_word=prev.tone_word, drive_word=prev.drive_word,
                                            leisure=leisure, home=home)
    if not text and "diary" not in night.thinker.failed:  # a reply with no diary in it
        night.thinker.failed.append("diary")
    return text, notes, line, home


def catch_up(night: Night) -> None:
    """4a. Days this past week they talked and an earlier night wrote no diary or letter. Only
    the words: her threads and the phase belong to the day they are written, and her mood that
    day is gone. Not while the model is failing tonight: the next night will try."""
    if not night.thinker or night.thinker.failed:
        return
    diary, room = Diary(night.conn), night.brain.cottage
    done: list[str] = []
    for day in chat_days(night.conn, night.day):
        if len(done) >= CATCH_UP_PER_NIGHT or night.thinker.failed:
            break
        text, gists = diary.get(day.isoformat()), _gists_of(night, day)
        wrote = False
        if not text:
            text = _ask_diary(night, day, FORGOTTEN_MOOD, gists)[0]
            if not text:
                break
            diary.write(day.isoformat(), text)
            wrote = True
        if room is not None and not room.letter(day):
            wrote = _write_letter_of(night, day, FORGOTTEN_MOOD, gists, text) or wrote
        if wrote:
            done.append(day.isoformat())
    if done:
        night.report["caught_up"] = done


def write_diary(night: Night) -> None:
    conn, store, day, now = night.conn, night.store, night.day, night.now
    first = first_message_at(conn)
    born = fish_day(first) if first else None
    if not (night.thinker and born is not None and day >= born):
        return
    diary = Diary(conn)
    gists = _gists_of(night, day)
    text, notes, line, home = _ask_diary(night, day, night.moods.load().describe(), gists)
    if not text:
        return
    night.line, night.diary_text, night.gists = line, text, gists
    diary.write(day.isoformat(), text)
    if home is not None:  # with a room, what she did is in it; her notes keep thoughts
        notes = [n for n in notes if not invented_act(n[0])]
    for note, importance in strongest(notes, SELF_NOTES_PER_NIGHT):
        store.note("self", note, importance=importance, now=now)
    night.report["diary"] = True


def write_letter(night: Night) -> None:
    """5a. a letter to him for her bedside drawer, never sent (decision 39): her day and what
    she did not say; she knows when the drawer was looked into."""
    brain = night.brain
    if not (night.thinker and night.diary_text and brain is not None and brain.cottage is not None):
        return
    if _write_letter_of(night, night.day, night.moods.load().describe(), night.gists, night.diary_text):
        night.report["letter"] = True


def _write_letter_of(night: Night, day: date, mood: str, gists: list[str], diary_text: str) -> bool:
    room = night.brain.cottage
    start, end = day_bounds(day)
    try:
        home = room.between(start, end)
        peeked = room.peeked(start, end)
    except ValueError:
        return False
    text = night.thinker.letter(day.isoformat(), mood, gists, home, diary_text,
                                yesterday=room.letter(day - timedelta(days=1)), peeked=peeked)
    if not text:
        if "letter" not in night.thinker.failed:
            night.thinker.failed.append("letter")
        return False
    room.put_letter(day, text)
    return True


def step_phase(night: Night) -> None:
    tone_today, energy_today = night.moods.day_tone(night.day_start, night.day_end)
    focus = [re.sub(r"^[\d\-年月日，, ]+", "", m.text).split("，")[0][:16]
             for m in night.store.alive("self")][-3:]  # short handles, not whole notes
    night.phase = night.phases.update(night.day.isoformat(), tone_today=tone_today,
                                      drive_today=None if energy_today is None else energy_today / 100,
                                      focus=focus, line=night.line)
    night.report["phase"] = {"tone": round(night.phase.tone, 2), "drive": round(night.phase.drive, 2)}


def look_at_herself(night: Night) -> None:
    if not night.thinker:
        return
    day, now = night.day, night.now
    known = night.rel.days_known(now)
    traits = TraitStore(night.conn)
    last = traits.growth_notes(1)
    last_day = date.fromisoformat(last[0].month) if last else None
    if not (known >= GROWTH_EVERY_DAYS and (last_day is None or (day - last_day).days >= GROWTH_EVERY_DAYS)):
        return
    month_diary = [f"{d}：{t}" for d, t in Diary(night.conn).recent(GROWTH_EVERY_DAYS)]
    trend = [f"{p.day}：基调{p.tone_word}，劲头{p.drive_word}" for p in night.phases.history(GROWTH_EVERY_DAYS)][::7]
    note, changes = night.thinker.grow(day.isoformat(), known, month_diary, trend, traits.describe_all())
    applied = traits.apply(changes, now)
    if note:
        traits.add_growth(day.isoformat(), note, applied)
        night.store.add("self", f"{day.isoformat()[:7]} 回头看自己：{note}", importance=6, now=now)
    night.report["growth"] = applied
