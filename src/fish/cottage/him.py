"""His status (decision 51): him as she sees him right now, in one place. Where he is, how they
are talking (face to face, or by phone) and what he says he is up to. The chat used to know he
was in her room only from one line among the room's, under rules that still told her to text
like on WeChat and to send stickers.

Where he is comes from `guest` (guest.py). What he is up to is his own words, from a chat or
`fish me`; it is only ever what he said, and it goes stale on its own."""

from __future__ import annotations

from datetime import datetime, timedelta

from fish.config import owner_words
from fish.cottage.state import Room, _iso
from fish.msgs import HisStatus

DOING_KEEPS = timedelta(hours=2)  # "在图书馆" said at noon says nothing about the evening
DOING_CHARS = 30
OUT_OF_THE_HOUSE = ("buy", "lake", "florist")  # what she is out for (`pending`): not in the room with him
ELSEWHERE = "他不在你这儿，在他自己那边"
FACE = "当面说话，他就在你眼前，他说的你是亲耳听见的，不是手机上发来的"
PHONE = "手机上发消息，你看不见他"


class HimMixin:
    """Part of Cottage (room.py). Uses the room's load / save and the guest's guest_here / guest_line."""

    def he_is_doing(self, what: str, now: datetime) -> None:
        """What he says he is up to. Not a line in the room's record: it is not something that
        happened in her house, and her reasons to text him listen to that record."""
        what = what.strip()[:DOING_CHARS]
        room = self.load(now)
        # the model copies it back from her prompt each turn: that is not him saying it again
        if what and what != room.him.get("doing"):
            room.him = {"doing": what, "at": _iso(now)}
            self.save(room)

    def together(self, room: Room, now: datetime) -> bool:
        """Face to face: he is in her room and she is too (she may have gone to the shop)."""
        return self.guest_here(room, now) and not any(room.pending.get(k) is not None for k in OUT_OF_THE_HOUSE)

    def him_status(self, now: datetime) -> HisStatus:
        room = self.load(now)
        together = self.together(room, now)
        where = self.guest_line(room) or owner_words(ELSEWHERE)
        if self.guest_here(room, now) and not together:
            where += "；你这会儿不在屋里"
        lines = [f"- 在哪：{where}", f"- 怎么说话：{owner_words(FACE if together else PHONE)}"]
        doing = room.him.get("doing")
        at = room.him.get("at", "")
        if doing and now - datetime.fromisoformat(at) <= DOING_KEEPS:
            lines.append(f"- 在干嘛：{doing}" + owner_words(f"（{at[11:16]} 他说的）"))
        return HisStatus("\n".join(lines), together)
