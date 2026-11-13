"""How warm her room is, and the little heater by her bed (decision 60).

The room has a temperature of its own. It drifts toward where it settles: with the heater off,
a little warmer than outdoors (a wooden cottage keeps some warmth: a quarter of the way from
outdoors to 24 degrees), with it on, much warmer, up to the heater's thermostat. Off it cools
slowly, on it warms fast. Outdoors is the real weather's temperature, which the hourly look at
the weather tells the room (`outdoors`, through the bus); without one, the month's usual.

She turns the heater on and off herself (on is offered only when the room is cool). The body's
habits are the program's, like her meals: she turns it off going out of the door and going to
bed. No model calls; the numbers are in rules.py.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from fish.cottage.rules import (CHILLY, COLD, COOLS_HOURS, FEEL, HEATER_ADDS, HEATER_UP_TO, KEEPS_SHARE,
                                KEEPS_TOWARD, MONTH_C, OUTDOOR_TRUSTED_HOURS, WARMS_HOURS)
from fish.cottage.state import Change, Offer, Room

KEYS = ("heat_on", "heat_off")
OUT_OF_THE_DOOR = ("shop", "lake", "florist")  # starting one of these, she turns it off first


def outdoor_c(room: Room, now: datetime) -> float:
    """Outdoors as last looked at, or the month's usual when that is too old or never came."""
    o = room.outside
    if o and now - datetime.fromisoformat(o["at"]) < timedelta(hours=OUTDOOR_TRUSTED_HOURS):
        return float(o["c"])
    return float(MONTH_C[now.month])


def settles_at(outdoor: float, heater_on: bool) -> float:
    """Where the room goes if left long enough."""
    off = outdoor + max(0.0, KEEPS_TOWARD - outdoor) * KEEPS_SHARE
    return max(off, min(HEATER_UP_TO, off + HEATER_ADDS)) if heater_on else off


def feel(c: float) -> str:
    return next((word for below, word in FEEL if c < below), "热得很")


class HeaterMixin:
    """Part of Cottage (room.py): the room's warmth and the heater. Uses the room's load / save / note."""

    def outdoors(self, c: float, now: datetime) -> None:
        """The weather was looked at: it is `c` degrees outdoors."""
        room = self.load(now)
        room.outside = {"c": round(float(c), 1), "at": now.isoformat(timespec="minutes")}
        self.save(room)

    @staticmethod
    def _heat_step(room: Room, last: datetime, now: datetime) -> None:
        """Time moves the room's warmth toward where it settles."""
        hours = (now - last).total_seconds() / 3600
        target = settles_at(outdoor_c(room, now), bool(room.heater))
        pace = WARMS_HOURS if room.heater else COOLS_HOURS
        room.temp = round(target + (room.temp - target) * math.exp(-hours / pace), 2)

    def _heater_off(self, room: Room, now: datetime, change: Change, line: str) -> None:
        """A habit, not a choice: going out, going to bed."""
        if room.heater:
            room.heater = ""
            self.note(room, now, line, change, routine=True)

    @staticmethod
    def heater_offers(room: Room, now: datetime) -> list[Offer]:
        if room.heater:
            return [Offer("heat_off", f"把取暖器关了（屋里 {room.temp:.0f} 度）")]
        if room.temp < CHILLY:
            return [Offer("heat_on", f"开取暖器（屋里 {room.temp:.0f} 度，{feel(room.temp)}）")]
        return []

    def heater_possible(self, room: Room, key: str, now: datetime) -> bool:
        return any(o.key == key for o in self.heater_offers(room, now))

    @staticmethod
    def _heater_apply(room: Room, key: str, now: datetime) -> str:
        if key == "heat_on":
            room.heater = now.isoformat(timespec="minutes")
            return f"屋里 {room.temp:.0f} 度，开了取暖器"
        room.heater = ""
        return f"关了取暖器，屋里 {room.temp:.0f} 度"

    @staticmethod
    def warmth_line(room: Room) -> str:
        on = f"取暖器开着（{room.heater[11:16]} 开的）" if room.heater else "取暖器关着"
        return f"屋里 {room.temp:.0f} 度，{feel(room.temp)}；{on}"

    @staticmethod
    def warmth_matters(room: Room) -> bool:
        """Worth a place among the few room lines of a chat turn: cold, hot, or the heater on."""
        return room.temp < COLD or room.temp >= FEEL[-1][0] or bool(room.heater)
