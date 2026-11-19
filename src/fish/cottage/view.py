"""Her room as a picture to draw (decision 62, the window in the panel): where she is in it and
what each thing looks like right now. Read only: it never moves time on and never saves.

The room's own lines (`Cottage.lines`) are words for her and for him. A picture needs places
and small numbers instead: she is at the stove, three bowls are in the sink, the spring onions
are at their second stage, the sky is grey and it is after sunset. Pure functions, no model.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from fish.cottage.florist import FloristMixin
from fish.cottage.garden import GardenMixin
from fish.cottage.guest import GuestMixin
from fish.cottage.heater import HeaterMixin
from fish.cottage.rules import ACTIONS, FISH_DIRTY_DAYS, FISH_FOUL_DAYS, PLANTS, RICE_FULL
from fish.cottage.state import BED_WORDS, Room, rice_word, sill_name
from fish.cottage.tank import TankMixin, doing_at

# Where in the picture each thing she does puts her.
SPOT_OF = {"rice": "stove", "cook": "stove", "wash": "sink", "bed": "bed", "nap": "bed", "leave": "sill",
           "sow": "sill", "water": "sill", "pick": "sill", "feed": "tank", "change": "tank", "namefish": "tank",
           "heat_on": "bed", "heat_off": "bed", "shop": "out", "lake": "out", "florist": "out"}
SPOTS = {ACTIONS[key].doing: spot for key, spot in SPOT_OF.items()} | {"睡觉": "bed"}
AWAY = {ACTIONS[key].doing: key for key in ("shop", "lake", "florist")}  # where she went, when out
ASLEEP = {"睡觉", ACTIONS["nap"].doing}
COOKING = {ACTIONS["rice"].doing, ACTIONS["cook"].doing}
IDLE = "desk"  # nothing in particular: at her desk by the window

# The weather line says "现在阴，没下雨，9 度；…，16:34 日落" (world/place.py). Only what it says right
# now counts: "没下雨" has 雨 in it, and so does "今天早些时候有过小雨".
NOW = re.compile(r"现在([^，,；;]+)")
SKY = (("雪", "snow"), ("雨", "rain"), ("雾", "fog"), ("阴", "overcast"), ("多云", "cloudy"), ("晴", "clear"))
SUNSET = re.compile(r"(\d{1,2}):(\d{2}) 日落")
DEFAULT_SUNSET = 18.0
NOON = 12.3  # the sun is highest about now; sunrise is as far before it as sunset is after
DUSK = 0.75  # hours either side of sunset (and of sunrise) that are neither day nor night


def sky_of(weather: str) -> str:
    now = NOW.search(weather or "")
    return next((name for word, name in SKY if now and word in now[1]), "")


def light_of(now: datetime, weather: str = "") -> str:
    """day, dusk or night: the sky in her window, from the sunset the weather line gives."""
    found = SUNSET.search(weather or "")
    sunset = int(found[1]) + int(found[2]) / 60 if found else DEFAULT_SUNSET
    sunrise = 2 * NOON - sunset
    hour = now.hour + now.minute / 60
    if sunrise + DUSK <= hour <= sunset - DUSK:
        return "day"
    if sunrise - DUSK <= hour <= sunset + DUSK:
        return "dusk"
    return "night"


def _days(since: str, today: date) -> int:
    try:
        return (today - date.fromisoformat(since[:10])).days
    except ValueError:
        return 0


def _pot(p: dict, today: date) -> dict | None:
    if not p:
        return None
    plant = PLANTS[p["plant"]]
    stage = sum(p["days"] >= d for d, _ in plant.stages)  # 0 before it comes up
    return {"plant": p["plant"], "stage": stage, "stages": len(plant.stages), "ready": int(p.get("ready") or 0),
            "wilted": bool(p.get("wilted")), "dry": _days(p.get("watered") or p["sown"], today)}


def _tank(room: Room, now: datetime) -> dict | None:
    t = room.tank
    if not t:
        return None
    water = _days(t["water"], now.date())
    return {"name": t.get("name", ""), "doing": doing_at(t, now), "sad": bool(t.get("sad")),
            "cloudy": 0 if water < FISH_DIRTY_DAYS else 1 if water < FISH_FOUL_DAYS else 2,
            "hungry": _days(t["fed"], now.date()) >= 1 and now.hour >= 10}


def her(room: Room, now: datetime) -> dict:
    """Where she is and what she is doing, in the words the picture shows next to her."""
    doing = room.doing
    out = AWAY.get(doing, "")
    until = room.until[11:16] if room.until and doing not in ASLEEP else ""
    return {"spot": SPOTS.get(doing, IDLE), "doing": doing or "闲着", "until": until,
            "asleep": doing in ASLEEP, "out": out}


def view(room: Room, now: datetime, *, weather: str = "", mood: str = "") -> dict:
    """Everything the window draws, as plain data (JSON-ready). weather: the line the hourly look
    at the sky wrote; mood: how she feels, in words."""
    today = now.date()
    meals: dict[str, int] = {}
    for item in room.fridge:
        meals[item["name"]] = meals.get(item["name"], 0) + item["meals"]
    words = {"bed": BED_WORDS.get(room.bed, room.bed), "pots": GardenMixin.pots_line(room),
             "warmth": HeaterMixin.warmth_line(room)}
    if room.tank:
        words["tank"] = TankMixin.tank_line(room)
    if room.flowers:
        words["flowers"] = FloristMixin.flowers_line(room)
    guest = room.guest
    return {
        "at": now.strftime("%m-%d %H:%M"),
        "light": light_of(now, weather),
        "sky": sky_of(weather),
        "weather": weather,
        "her": her(room, now),
        "mood": mood,
        "bed": room.bed,
        "fridge": [{"name": n, "meals": k} for n, k in meals.items()],
        "rice": room.rice, "rice_full": RICE_FULL, "rice_word": rice_word(room.rice),
        "sink": len(room.sink),
        "cooking": room.doing in COOKING,
        "pots": [_pot(p, today) for p in room.pots],
        "flowers": [{"name": f["name"], "wilted": bool(f.get("wilted"))} for f in room.flowers],
        "sill": [sill_name(x) for x in room.sill],
        "tank": _tank(room, now),
        "temp": round(room.temp), "heater": bool(room.heater),
        "outside": room.outside.get("c") if room.outside else None,
        "guest": "here" if guest.get("here") else "coming" if guest else "",
        "guest_line": GuestMixin.guest_line(room) if guest else "",
        "words": words,
        "today": [{"when": e["ts"][11:16], "text": e["line"]} for e in room.events
                  if e["ts"].startswith(today.isoformat()) and not e.get("routine")][-6:],
    }

