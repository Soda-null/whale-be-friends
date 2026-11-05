"""Where she lives (decision 15): home at neighbourhood level, weather, nearby places, the map."""

import io
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image

from fish.brain import Brain, FakeLLM
from fish.config import Settings
from fish.memory import MemoryStore, Relationship
from fish.routines.outside import load_home, load_places, run_outside
from fish.storage import connect
from fish.world.place import Home, locate, nearby, places_line, weather

T = datetime(2026, 10, 27, 9, 0)
HOME = Home("Springfield", "Ohio", "Downtown", 39.92, -83.81, "America/New_York")


def meteo(now, hours, at="2026-10-27T12:00") -> str:
    """Open-Meteo's answer: `now` is (weather code, mm); `hours` are (hour, code, mm, % chance) of that day."""
    day = at[:10]
    return json.dumps({"current": {"time": at, "temperature_2m": 9.4, "weather_code": now[0], "precipitation": now[1]},
                       "hourly": {"time": [f"{day}T{h:02d}:00" for h, *_ in hours],
                                  "weather_code": [c for _, c, _, _ in hours],
                                  "precipitation": [mm for _, _, mm, _ in hours],
                                  "precipitation_probability": [p for _, _, _, p in hours]},
                       "daily": {"temperature_2m_min": [5.2], "temperature_2m_max": [13.8],
                                 "sunset": [f"{day}T18:05"]}})


def fake_fetch(url, timeout):
    if "ipinfo" in url:
        return json.dumps({"city": "Springfield", "region": "Ohio", "loc": "39.9242,-83.8088",
                           "timezone": "America/New_York"})
    if "nominatim" in url:
        assert "lat=39.92&lon=-83.81" in url  # only the rounded position ever leaves the box
        return json.dumps({"address": {"quarter": "Downtown", "house_number": "1", "road": "X St"}})
    if "open-meteo" in url:
        return meteo(now=(3, 0.0), hours=[(9, 3, 0.0, 10), (18, 61, 0.5, 60)])
    if "holiday-cn" in url:
        return json.dumps({"year": 2026, "days": [{"name": "元旦", "date": "2026-01-01", "isOffDay": True}]})
    raise AssertionError(url)


def fake_post(url, form, timeout):
    assert "around:1500,39.92,-83.81" in form["data"]
    return json.dumps({"elements": [
        {"lat": 39.9105, "lon": -83.7988, "tags": {"name": "McDonald's", "amenity": "fast_food", "addr:street": "Green St"}},
        {"center": {"lat": 39.92, "lon": -83.81}, "tags": {"name": "Cafe Kopi", "amenity": "cafe"}},
        {"lat": 39.92, "lon": -83.81, "tags": {"name": "McDonald's", "amenity": "fast_food"}},
        {"lat": 39.92, "lon": -83.81, "tags": {"amenity": "restaurant"}},
    ]})


def fake_tile(url, timeout):
    out = io.BytesIO()
    Image.new("RGB", (256, 256), "lightblue").save(out, "PNG")
    return out.getvalue()


def test_locate_keeps_only_city_and_neighbourhood():
    home = locate(fake_fetch)
    assert home == HOME
    assert home.line() == "你住在 Springfield（Ohio）的 Downtown 一带"
    assert "X St" not in home.to_json()


def line_for(*args, **kwargs) -> str:
    return weather(HOME, lambda url, timeout: meteo(*args, **kwargs)).line()


def test_weather_line_keeps_now_and_what_may_come_apart():
    w = weather(HOME, fake_fetch)
    assert w.line() == "现在阴，没下雨，9 度，18 点前后可能有小雨（可能性 60%）；今天 5 到 14 度，18:05 日落"


def test_a_small_chance_of_drizzle_is_not_rain():
    """11-05: the day's worst hour said drizzle at under 40%, she said it had rained all day."""
    line = line_for(now=(3, 0.0), hours=[(15, 51, 0.1, 36), (16, 3, 0.0, 10)])
    assert line.startswith("现在阴，没下雨") and "毛毛雨" not in line


def test_a_wet_code_with_nothing_falling_is_not_rain():
    assert line_for(now=(51, 0.0), hours=[]).startswith("现在阴，没下雨")


def test_rain_now_is_said_as_now():
    line = line_for(now=(61, 0.4), hours=[(9, 61, 0.4, 80)])
    assert line.startswith("现在小雨，9 度") and "没下雨" not in line and "早些时候" not in line


def test_rain_that_stopped_is_said_as_earlier():
    line = line_for(now=(3, 0.0), hours=[(2, 55, 1.1, 60), (9, 51, 0.4, 60), (11, 3, 0.0, 5)])
    assert "现在阴，没下雨" in line and "今天早些时候有过毛毛雨" in line


def test_a_clear_sky_needs_no_word_about_rain():
    assert line_for(now=(0, 0.0), hours=[]).startswith("现在晴，9 度")


def test_after_midnight_it_says_tomorrow():
    d = json.loads(meteo(now=(3, 0.0), hours=[], at="2026-10-27T22:00"))
    d["hourly"] = {"time": ["2026-10-27T23:00", "2026-10-28T02:00"], "weather_code": [3, 63],
                   "precipitation": [0, 1.0], "precipitation_probability": [10, 70]}
    assert "明天 2 点前后可能有雨（可能性 70%）" in weather(HOME, lambda u, t: json.dumps(d)).line()


def test_nearby_places_have_names_kinds_and_minutes_but_no_addresses():
    places = nearby(HOME, fake_post)
    assert [(p.name, p.kind) for p in places] == [("Cafe Kopi", "咖啡馆"), ("McDonald's", "快餐")]
    assert places[1].walk_min > places[0].walk_min >= 1
    assert "Green St" not in places_line(places)


def test_outside_routine_sets_home_weather_places_and_looks_at_the_map_once(tmp_path: Path):
    def respond(messages, json_mode):
        content = messages[-1]["content"]
        assert isinstance(content, list) and content[1]["image_url"]["url"].startswith("data:image/png")
        assert "McDonald's" in content[0]["text"]
        return json.dumps({"notes": [{"text": "我住 Springfield 市中心，走几分钟就有麦当劳。", "importance": 6}]},
                          ensure_ascii=False)

    conn = connect(tmp_path / "fish.db")
    brain = Brain(conn, Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db"),
                  FakeLLM(respond), persona_text="你是大肥鱼。", stickers_dir=tmp_path / "stickers")
    report = run_outside(conn, T, brain=brain, fetch=fake_fetch, fetch_bytes=fake_tile, post=fake_post)
    assert report["places"] == 2 and report["map_notes"] == 1 and "现在阴，没下雨" in report["weather"]
    assert load_home(tmp_path / "home") == HOME and len(load_places(tmp_path / "home")) == 2
    assert Image.open(tmp_path / "home" / "map.png").size == (768, 768)
    assert [m.text for m in MemoryStore(conn).alive("self")] == ["我住 Springfield 市中心，走几分钟就有麦当劳。"]
    again = run_outside(conn, T, brain=brain, fetch=fake_fetch, fetch_bytes=fake_tile, post=fake_post)
    assert again == {}  # just looked at the weather, map already looked at

    brain.llm = FakeLLM([json.dumps({"say": "嗯"})])
    brain.respond("你在哪", now=T)
    system = brain.llm.calls[0][0][0]["content"]
    assert "你住在 Springfield（Ohio）的 Downtown 一带" in system and "McDonald's（快餐，走" in system
    assert "你那儿现在阴，没下雨" in system
    assert Relationship(conn).get("weather_at") == T.isoformat(timespec="seconds")


def outside_brain(tmp_path: Path) -> tuple:
    conn = connect(tmp_path / "fish.db")
    brain = Brain(conn, Settings(api_key="t", base_url="", model="fake", db_path=tmp_path / "fish.db"),
                  FakeLLM([json.dumps({"notes": []})]), persona_text="你是大肥鱼。", stickers_dir=tmp_path / "stickers")
    return conn, brain


def test_she_looks_again_within_the_hour_and_the_line_follows(tmp_path: Path):
    conn, brain = outside_brain(tmp_path)
    run = lambda at, answer: run_outside(  # noqa: E731
        conn, at, brain=brain, fetch=lambda u, t: answer if "open-meteo" in u else fake_fetch(u, t),
        fetch_bytes=fake_tile, post=fake_post)
    run(T, meteo(now=(61, 0.5), hours=[]))
    assert Relationship(conn).get("weather_line").startswith("现在小雨")
    assert "weather" not in run(T + timedelta(minutes=30), meteo(now=(3, 0.0), hours=[]))
    assert Relationship(conn).get("weather_line").startswith("现在小雨")
    assert "weather" in run(T + timedelta(minutes=50), meteo(now=(3, 0.0), hours=[]))
    assert Relationship(conn).get("weather_line").startswith("现在阴，没下雨")


def test_a_failed_look_is_retried_and_an_old_line_is_dropped(tmp_path: Path):
    conn, brain = outside_brain(tmp_path)

    def down(url, timeout):
        if "open-meteo" in url:
            raise OSError("no network")
        return fake_fetch(url, timeout)

    run_outside(conn, T, brain=brain, fetch=fake_fetch, fetch_bytes=fake_tile, post=fake_post)
    run_outside(conn, T + timedelta(hours=1), brain=brain, fetch=down, fetch_bytes=fake_tile, post=fake_post)
    assert Relationship(conn).get("weather_line").startswith("现在阴")  # an hour old: still good enough
    run_outside(conn, T + timedelta(hours=3), brain=brain, fetch=down, fetch_bytes=fake_tile, post=fake_post)
    assert Relationship(conn).get("weather_line") == ""  # she would rather not know than say it wrong
    report = run_outside(conn, T + timedelta(hours=4), brain=brain, fetch=fake_fetch, fetch_bytes=fake_tile, post=fake_post)
    assert report["weather"].startswith("现在阴")  # no waiting for tomorrow


def test_home_can_be_set_by_hand_for_a_cloud_server():
    def fetch(url, timeout):
        assert "ipinfo" not in url  # the machine's own location is not asked
        assert "lat=39.92&lon=-83.81" in url
        return json.dumps({"address": {"city": "Springfield", "state": "Ohio", "quarter": "Downtown",
                                       "road": "X St"}})
    assert locate(fetch, at="39.9242,-83.8088") == Home("Springfield", "Ohio", "Downtown", 39.92, -83.81)


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="Windows keeps the machine's clock")
def test_her_clock_follows_her_home_when_env_has_no_tz(tmp_path, monkeypatch):
    """No TZ in .env: once she knows where she lives, that place's timezone is her clock."""
    import os
    import time

    from fish.config import load_settings

    orig = os.environ.get("TZ")
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setenv("FISH_DB_PATH", str(tmp_path / "fish.db"))
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / "home.json").write_text(HOME.to_json(), encoding="utf-8")
    (tmp_path / ".env").write_text("", encoding="utf-8")
    try:
        load_settings(tmp_path / ".env")
        assert os.environ["TZ"] == "America/New_York"
    finally:  # put the process clock back for the other tests
        if orig is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = orig
        if hasattr(time, "tzset"):
            time.tzset()


def test_on_windows_she_keeps_the_machine_clock(tmp_path, monkeypatch):
    """Windows' C library cannot read "Asia/Shanghai" and would count in UTC: drop TZ there."""
    import os
    import time

    from fish.config import load_settings

    monkeypatch.delattr(time, "tzset", raising=False)
    monkeypatch.setenv("TZ", "Asia/Shanghai")
    monkeypatch.setenv("FISH_DB_PATH", str(tmp_path / "fish.db"))
    (tmp_path / ".env").write_text("", encoding="utf-8")
    load_settings(tmp_path / ".env")
    assert "TZ" not in os.environ
