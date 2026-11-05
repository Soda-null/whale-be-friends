"""Where she lives (decision 15): a city and a neighbourhood, never a street address.

locate   the box's city-level position (ipinfo, which is itself city-level) and the
         neighbourhood name around it (OpenStreetMap Nominatim, zoom 14 = quarter level)
weather  the weather there right now and the next few hours (Open-Meteo, no key)
nearby   named places to eat and shop within walking distance (OpenStreetMap Overpass);
         names, kinds and walking minutes only — addresses are dropped on purpose
map      a picture of the neighbourhood stitched from OpenStreetMap tiles, for her to look at

All free services without keys; called about once an hour (weather) or once a month.
"""

from __future__ import annotations

import io
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from fish.world.http import (Fetch, FetchBytes, FetchPost, urllib_fetch, urllib_fetch_bytes,
                             urllib_post)

NOMINATIM = ("https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&zoom=14"
             "&format=jsonv2&accept-language=zh-CN,en")
OPEN_METEO = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
              "&current=temperature_2m,weather_code,precipitation"
              "&hourly=weather_code,precipitation,precipitation_probability"
              "&daily=temperature_2m_max,temperature_2m_min,sunset&forecast_days=2&timezone=auto")
OVERPASS = "https://overpass-api.de/api/interpreter"
OVERPASS_MIRRORS = (OVERPASS, "https://overpass.private.coffee/api/interpreter",
                    "https://maps.mail.ru/osm/tools/overpass/api/interpreter")  # the main one is often busy
TILE = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
COORD_DECIMALS = 2  # about a kilometre: city and neighbourhood, not a building
WALK_M_PER_MIN = 80
NEARBY_RADIUS_M = 1500
KINDS = {"restaurant": "餐馆", "fast_food": "快餐", "cafe": "咖啡馆", "bubble_tea": "奶茶",
         "supermarket": "超市", "convenience": "便利店", "bakery": "面包店", "ice_cream": "冰淇淋",
         "park": "公园", "library": "图书馆"}
# WMO weather codes -> a word
WEATHER = {0: "晴", 1: "晴", 2: "多云", 3: "阴", 45: "雾", 48: "雾", 51: "毛毛雨", 53: "毛毛雨",
           55: "毛毛雨", 61: "小雨", 63: "雨", 65: "大雨", 66: "冻雨", 67: "冻雨", 71: "小雪", 73: "雪",
           75: "大雪", 77: "雪粒", 80: "阵雨", 81: "阵雨", 82: "大阵雨", 85: "阵雪", 86: "阵雪",
           95: "雷雨", 96: "雷雨", 99: "雷雨"}
WET_FROM = 51  # WMO codes from here up are something falling from the sky
DRY_WORD = "阴"  # the model's code says it falls, its amount says nothing does
LIKELY_FROM = 40  # % chance before she is told to expect it; the false rains of 11-01 to 11-05 were all below
LOOK_AHEAD_HOURS = 12
FELL_FROM_MM = 0.1


@dataclass(frozen=True)
class Home:
    city: str
    region: str
    area: str  # neighbourhood / quarter, may be ""
    lat: float  # rounded to COORD_DECIMALS
    lon: float
    tz: str = ""  # the place's timezone (Europe/Berlin); her clock when .env has no TZ

    def line(self) -> str:
        where = f"{self.city}（{self.region}）" if self.region else self.city
        return f"你住在 {where}" + (f"的 {self.area} 一带" if self.area else "")

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "Home":
        return cls(**json.loads(text))


@dataclass(frozen=True)
class Place:
    name: str
    kind: str  # Chinese word from KINDS
    walk_min: int


def locate(fetch: Fetch = urllib_fetch, at: str = "") -> Home:
    """`at` = "lat,lon" from FISH_HOME in .env, for a machine whose network location is not
    where she should live (a cloud server); otherwise the machine's own city."""
    if at:
        info = {"loc": at}
    else:
        info = json.loads(fetch("https://ipinfo.io/json", 10.0))
    lat, lon = (float(v) for v in info["loc"].split(","))
    lat, lon = round(lat, COORD_DECIMALS), round(lon, COORD_DECIMALS)
    area = ""
    addr: dict = {}
    try:
        rev = json.loads(fetch(NOMINATIM.format(lat=lat, lon=lon), 15.0))
        addr = rev.get("address") or {}
        area = addr.get("quarter") or addr.get("neighbourhood") or addr.get("suburb") or ""
    except Exception:  # noqa: BLE001 - the neighbourhood is a nicety
        pass
    city = info.get("city") or addr.get("city") or addr.get("town") or addr.get("county") or ""
    return Home(city, info.get("region") or addr.get("state", ""), area, lat, lon,
                str(info.get("timezone") or ""))


@dataclass(frozen=True)
class Weather:
    """What is true now, kept apart from what may happen: "今天毛毛雨" for a day with a small
    chance of an hour of it read to her as rain all day, for days on end (decision 55)."""
    now_c: float
    low_c: float
    high_c: float
    sky: str  # right now
    falling: bool  # something is coming down right now
    earlier: str  # what came down earlier today ("小雨"), "" for nothing
    later: str  # what is likely in the next hours ("20 点前后可能有小雨（可能性 60%）"), "" for nothing
    sunset: str  # HH:MM

    def line(self) -> str:
        now = f"现在{self.sky}" + ("" if self.falling or self.sky == "晴" else "，没下雨")
        bits = [f"{now}，{self.now_c:.0f} 度"]
        if self.earlier and not self.falling:
            bits.append(f"今天早些时候有过{self.earlier}")
        if self.later:
            bits.append(self.later)
        day = f"今天 {self.low_c:.0f} 到 {self.high_c:.0f} 度"
        return "，".join(bits) + f"；{day}" + (f"，{self.sunset} 日落" if self.sunset else "")


def _is_wet(code: object) -> bool:
    return isinstance(code, int) and code >= WET_FROM


def _word(code: int) -> str:
    return WEATHER.get(code, "说不清")


def _earlier_today(hourly: dict, hour: str) -> str:
    """The most it came down in one hour earlier today, as a word."""
    fell = [(mm, code) for t, code, mm in zip(hourly["time"], hourly["weather_code"], hourly["precipitation"])
            if t[:10] == hour[:10] and t[:13] < hour and (mm or 0) >= FELL_FROM_MM and _is_wet(code)]
    return _word(max(fell, key=lambda f: f[0])[1]) if fell else ""


def _coming(hourly: dict, hour: str) -> str:
    """The first of the next hours when something is likely to come down, in her words."""
    ahead = [row for row in zip(hourly["time"], hourly["weather_code"], hourly["precipitation_probability"])
             if row[0][:13] > hour][:LOOK_AHEAD_HOURS]
    for t, code, chance in ahead:
        if _is_wet(code) and (chance or 0) >= LIKELY_FROM:
            when = f"{int(t[11:13])} 点前后" if t[:10] == hour[:10] else f"明天 {int(t[11:13])} 点前后"
            return f"{when}可能有{_word(code)}（可能性 {chance}%）"
    return ""


def weather(home: Home, fetch: Fetch = urllib_fetch) -> Weather:
    d = json.loads(fetch(OPEN_METEO.format(lat=home.lat, lon=home.lon), 15.0))
    cur, day = d["current"], d["daily"]
    code = int(cur.get("weather_code", 0))
    falling = _is_wet(code) and float(cur.get("precipitation") or 0) > 0
    sky = _word(code) if falling or not _is_wet(code) else DRY_WORD
    hourly, hour = d.get("hourly"), str(cur.get("time", ""))[:13]
    return Weather(float(cur["temperature_2m"]), float(day["temperature_2m_min"][0]),
                   float(day["temperature_2m_max"][0]), sky, falling,
                   _earlier_today(hourly, hour) if hourly and hour else "",
                   _coming(hourly, hour) if hourly and hour else "",
                   (day.get("sunset") or [""])[0][-5:])


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearby(home: Home, post: FetchPost = urllib_post, limit: int = 40) -> list[Place]:
    amenity = "|".join(k for k in KINDS if k not in ("supermarket", "convenience", "bakery", "park"))
    query = (f"[out:json][timeout:25];("
             f"nwr(around:{NEARBY_RADIUS_M},{home.lat},{home.lon})[amenity~\"^({amenity})$\"][name];"
             f"nwr(around:{NEARBY_RADIUS_M},{home.lat},{home.lon})[shop~\"^(supermarket|convenience|bakery)$\"][name];"
             f"nwr(around:{NEARBY_RADIUS_M},{home.lat},{home.lon})[leisure=park][name];"
             f");out center 200;")
    last: Exception | None = None
    for url in OVERPASS_MIRRORS:
        try:
            data = json.loads(post(url, {"data": query}, 40.0))
            break
        except Exception as e:  # noqa: BLE001 - try the next mirror
            last = e
    else:
        raise last  # type: ignore[misc]
    seen: set[str] = set()
    places: list[Place] = []
    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        name = tags.get("name:zh") or tags.get("name")
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        kind_key = tags.get("amenity") or tags.get("shop") or ("park" if tags.get("leisure") == "park" else "")
        if not name or lat is None or kind_key not in KINDS or name in seen:
            continue
        seen.add(name)
        minutes = max(1, round(_distance_m(home.lat, home.lon, lat, lon) / WALK_M_PER_MIN))
        places.append(Place(name, KINDS[kind_key], minutes))
    places.sort(key=lambda p: p.walk_min)
    return places[:limit]


def _tile_xy(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def neighbourhood_map(home: Home, fetch_bytes: FetchBytes = urllib_fetch_bytes, z: int = 15,
                      size: int = 3) -> bytes:
    """A size x size block of OpenStreetMap tiles around home, as one PNG."""
    from PIL import Image

    cx, cy = _tile_xy(home.lat, home.lon, z)
    x0, y0 = int(cx) - size // 2, int(cy) - size // 2
    canvas = Image.new("RGB", (256 * size, 256 * size), "white")
    for dx in range(size):
        for dy in range(size):
            tile = Image.open(io.BytesIO(fetch_bytes(TILE.format(z=z, x=x0 + dx, y=y0 + dy), 20.0)))
            canvas.paste(tile.convert("RGB"), (256 * dx, 256 * dy))
    out = io.BytesIO()
    canvas.save(out, "PNG", optimize=True)
    return out.getvalue()


def load_home(folder: Path) -> Home | None:
    """Where she lives, as saved in data/home/ once she located it; None before."""
    p = folder / "home.json"
    return Home.from_json(p.read_text(encoding="utf-8")) if p.exists() else None


def load_places(folder: Path) -> list[Place]:
    p = folder / "places.json"
    if not p.exists():
        return []
    return [Place(**d) for d in json.loads(p.read_text(encoding="utf-8"))["places"]]


def places_line(places: list[Place], limit: int = 15) -> str:
    return "；".join(f"{p.name}（{p.kind}，走 {p.walk_min} 分钟）" for p in places[:limit])
