"""The window into her cottage (decision 62): her room as a picture to draw. `view` says where she
is and what each thing looks like; `fish window` prints it; the panel passes it to the page,
whose drawing (window.js) loads nothing from outside and puts no text in as HTML."""

import json
from datetime import datetime
from pathlib import Path

from fish.cottage import Cottage, view
from fish.cottage.view import light_of, sky_of

T = datetime(2026, 11, 18, 15, 0)
WEATHER = "现在阴，没下雨，9 度；今天 -0 到 18 度，16:34 日落"
WINDOW_JS = Path(__file__).resolve().parents[1] / "src" / "fish" / "panel" / "window.js"


def room(tmp_path, **fields):
    c = Cottage(tmp_path / "cottage" / "now.json")
    r = c.load(T)
    for k, v in fields.items():
        setattr(r, k, v)
    c.save(r)
    return c, r


def test_what_she_is_doing_puts_her_somewhere_in_the_room(tmp_path):
    _, r = room(tmp_path)
    assert view(r, T)["her"] == {"spot": "desk", "doing": "闲着", "until": "", "asleep": False, "out": ""}
    r.doing, r.until = "做饭", "2026-11-18T15:40"
    v = view(r, T)
    assert v["her"]["spot"] == "stove" and v["her"]["until"] == "15:40" and v["cooking"]
    r.doing = "洗碗"
    assert view(r, T)["her"]["spot"] == "sink" and not view(r, T)["cooking"]
    r.doing = "喂小金鱼"
    assert view(r, T)["her"]["spot"] == "tank"
    r.doing = "浇水"
    assert view(r, T)["her"]["spot"] == "sill"


def test_asleep_and_out_of_the_door(tmp_path):
    _, r = room(tmp_path, doing="睡觉", until="")
    assert view(r, T)["her"] == {"spot": "bed", "doing": "睡觉", "until": "", "asleep": True, "out": ""}
    r.doing, r.until = "睡午觉", "2026-11-18T16:00"
    her = view(r, T)["her"]
    assert her["asleep"] and her["spot"] == "bed" and her["until"] == ""  # nobody says when a nap ends
    for doing, where in (("去菜店", "shop"), ("湖边码头坐着", "lake"), ("去花店", "florist")):
        r.doing = doing
        assert view(r, T)["her"]["out"] == where and view(r, T)["her"]["spot"] == "out"


def test_the_sky_is_what_the_weather_says_right_now():
    assert sky_of(WEATHER) == "overcast"  # "没下雨" has 雨 in it, and is no rain
    assert sky_of("现在小雨，6 度；今天 3 到 9 度，16:40 日落") == "rain"
    assert sky_of("现在晴，2 度，今天早些时候有过小雨；今天 0 到 8 度") == "clear"  # rain earlier is not rain now
    assert sky_of("现在阵雪，-3 度；今天 -5 到 0 度") == "snow"
    assert sky_of("现在雾，没下雨，4 度") == "fog" and sky_of("现在多云，没下雨，12 度") == "cloudy"
    assert sky_of("") == ""


def test_day_dusk_and_night_follow_the_sunset():
    at = lambda h, m=0: datetime(2026, 11, 18, h, m)  # noqa: E731
    assert light_of(at(15), WEATHER) == "day"
    assert light_of(at(16, 30), WEATHER) == "dusk" and light_of(at(17, 10), WEATHER) == "dusk"
    assert light_of(at(17, 30), WEATHER) == "night" and light_of(at(3), WEATHER) == "night"
    assert light_of(at(7, 40), WEATHER) == "dusk" and light_of(at(9), WEATHER) == "day"  # sunrise mirrors sunset
    assert light_of(at(17)) == "day" and light_of(at(17, 30)) == "dusk"  # no weather line: sunset at 18:00


def test_things_in_the_room_as_small_numbers(tmp_path):
    _, r = room(tmp_path, sink=["碗", "碗", "锅"], rice=3, heater="2026-11-18T14:00", temp=15.6,
                fridge=[{"name": "鸡蛋", "meals": 3, "bought": "2026-11-17"}, {"name": "鸡蛋", "meals": 2, "bought": "2026-11-18"}],
                pots=[{"plant": "小葱", "sown": "2026-11-01", "watered": "2026-11-15", "days": 9, "ready": 0}, {}],
                flowers=[{"name": "小菊花", "bought": "2026-11-04", "watered": "2026-11-16", "wilted": True}],
                tank={"name": "小泡泡", "since": "2026-10-30", "from": "他", "fed": "2026-11-17", "water": "2026-11-12"},
                events=[{"ts": "2026-11-18T09:00", "line": "给小泡泡喂了鱼食"}, {"ts": "2026-11-18T12:00", "line": "吃了午饭", "routine": True},
                        {"ts": "2026-11-17T20:00", "line": "昨天的事"}])
    v = view(r, T, weather=WEATHER, mood="有点困")
    assert v["sink"] == 3 and v["rice"] == 3 and v["rice_word"] == "快见底了" and v["heater"] and v["temp"] == 16
    assert v["fridge"] == [{"name": "鸡蛋", "meals": 5}]  # eggs bought on two days are just eggs
    assert v["pots"][0] == {"plant": "小葱", "stage": 2, "stages": 2, "ready": 0, "wilted": False, "dry": 3} and v["pots"][1] is None
    assert v["flowers"] == [{"name": "小菊花", "wilted": True}]
    assert v["tank"]["name"] == "小泡泡" and v["tank"]["cloudy"] == 1 and v["tank"]["hungry"]
    assert v["today"] == [{"when": "09:00", "text": "给小泡泡喂了鱼食"}]  # not a meal on time, not yesterday
    assert v["mood"] == "有点困" and v["light"] == "day" and v["sky"] == "overcast"
    assert "取暖器开着" in v["words"]["warmth"] and json.dumps(v, ensure_ascii=False)  # all of it is plain JSON


def test_looking_never_changes_her_room(tmp_path):
    c, r = room(tmp_path, doing="做饭", until="2026-11-18T12:40")
    before = c.path.read_bytes()
    view(c.load(T), datetime(2026, 11, 18, 20, 0))  # long after the cooking should have ended
    assert c.path.read_bytes() == before


def test_fish_window_prints_one_line_of_json(tmp_path, capsys):
    from fish.__main__ import window
    from fish.config import Settings
    from fish.memory import Relationship
    from fish.storage import connect

    conn = connect(tmp_path / "fish.db")
    Relationship(conn).set("weather_line", WEATHER)
    window(conn, Settings(api_key="", base_url="", model="fake", db_path=tmp_path / "fish.db", cottage=True), now=T)
    d = json.loads(capsys.readouterr().out)
    assert d["sky"] == "overcast" and d["her"]["spot"] and d["mood"]
    window(conn, Settings(api_key="", base_url="", model="fake", db_path=tmp_path / "fish.db", cottage=False), now=T)
    assert json.loads(capsys.readouterr().out) == {"cottage": False}


def test_the_drawing_loads_nothing_from_outside_and_puts_no_html_in():
    js = WINDOW_JS.read_text(encoding="utf-8")
    assert "innerHTML" not in js and "outerHTML" not in js and "insertAdjacentHTML" not in js
    assert "https://" not in js and "http://" not in js.replace("http://www.w3.org/2000/svg", "")
    assert 'href: "/img/her.webp"' in js  # her face is the one picture, from this panel
