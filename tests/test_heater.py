"""How warm her room is and the heater by her bed (decision 60): the room drifts toward the real
weather, she turns the heater on and off, and turns it off going out and going to bed."""

from datetime import datetime, timedelta
from pathlib import Path

from fish.bus import Bus
from fish.cottage import Cottage, RoomNode
from fish.cottage.heater import outdoor_c, settles_at
from fish.msgs import WeatherLooked

MON = datetime(2026, 11, 2, 10, 0)  # November: the month's usual outdoors is 10 degrees


def home(tmp_path: Path, now: datetime = MON) -> Cottage:
    c = Cottage(tmp_path / "cottage" / "now.json")
    c.load(now)
    c.advance(now)
    return c


def keys(c: Cottage, now: datetime) -> list[str]:
    return [o.key for o in c.offers(now, hunger=20, energy=70)]


def test_where_the_room_settles():
    assert settles_at(0, False) == 6  # a quarter of the way from outdoors to 24
    assert settles_at(0, True) == 18  # the heater adds 12
    assert settles_at(10, True) == 24  # but not past its thermostat
    assert settles_at(32, False) == 32 and settles_at(32, True) == 32  # it never cools a hot room


def test_without_a_look_at_the_weather_the_month_stands_in(tmp_path):
    c = home(tmp_path)
    room = c.load(MON)
    assert outdoor_c(room, MON) == 10
    c.outdoors(-3, MON)
    assert outdoor_c(c.load(MON), MON + timedelta(hours=2)) == -3
    assert outdoor_c(c.load(MON), MON + timedelta(hours=4)) == 10  # too old: she no longer knows


def test_the_room_cools_toward_outdoors_and_she_sees_it(tmp_path):
    c = home(tmp_path)
    c.outdoors(0, MON)
    c.advance(MON + timedelta(hours=1))
    first = c.load().temp
    assert 6 < first < 18
    for h in range(1, 6):  # the weather is looked at every hour
        c.outdoors(0, MON + timedelta(hours=h))
        c.advance(MON + timedelta(hours=h + 1))
    room = c.load()
    assert 6 < room.temp < first and room.temp < 9
    assert c.lines(room)["warmth"] == f"屋里 {room.temp:.0f} 度，冷得很；取暖器关着"
    assert f"屋里 {room.temp:.0f} 度" in c.for_chat(MON + timedelta(hours=6), hunger=20)  # cold enough to be told  # cold enough to be told in a chat


def test_the_heater_is_on_her_menu_only_when_it_is_cool(tmp_path):
    c = home(tmp_path)
    assert c.load().temp == 18 and "heat_on" in keys(c, MON)
    room = c.load()
    room.temp = 22
    c.save(room)
    assert not {"heat_on", "heat_off"} & set(keys(c, MON))
    assert c.act("heat_on", MON) is None  # not when it is warm


def test_turned_on_it_warms_the_room_and_turned_off_it_stops(tmp_path):
    c = home(tmp_path)
    c.outdoors(2, MON)
    assert c.act("heat_on", MON) is not None
    room = c.load()
    c.advance(MON + timedelta(minutes=2))  # a minute's job: done at the next tick
    assert room.heater and "heat_off" in keys(c, MON + timedelta(minutes=2))
    assert room.events[-1]["line"] == "屋里 18 度，开了取暖器" and room.events[-1].get("routine")
    later = MON + timedelta(hours=1)  # before lunch, or she is busy cooking
    c.advance(later)
    warm = c.load().temp
    assert warm > 18 and "取暖器开着（10:00 开的）" in c.lines(c.load())["warmth"]
    assert "取暖器开着" in c.for_chat(later, hunger=20)
    assert c.act("heat_off", later) is not None
    assert not c.load().heater
    c.advance(later + timedelta(minutes=25))
    assert c.load().temp < warm


def test_she_turns_it_off_going_out(tmp_path):
    c = home(tmp_path)
    c.act("heat_on", MON)
    c.advance(MON + timedelta(minutes=5))
    assert c.act("lake", MON + timedelta(minutes=5)) is not None
    room = c.load()
    assert not room.heater
    assert [e["line"] for e in room.events[-2:]] == ["出门前把取暖器关了", "出门去湖边码头坐一会儿"]


def test_she_turns_it_off_going_to_bed(tmp_path):
    c = home(tmp_path, datetime(2026, 11, 2, 22, 0))
    c.act("heat_on", datetime(2026, 11, 2, 22, 0))
    c.advance(datetime(2026, 11, 3, 0, 30))
    room = c.load()
    assert room.doing == "睡觉" and not room.heater
    assert any(e["line"] == "睡前把取暖器关了" for e in room.events)


def test_the_weather_reaches_the_room_through_the_bus(tmp_path):
    from fish.app import wire

    class Quiet:
        def __getattr__(self, name):
            return lambda *a, **k: None

    c = home(tmp_path)
    bus = Bus()
    wire(bus, room=RoomNode(bus, c), mood=Quiet(), reach=Quiet(), leisure=Quiet(), chat=lambda m: None)
    bus.publish(WeatherLooked(MON, -5.0))
    assert c.load().outside == {"c": -5.0, "at": "2026-11-02T10:00"}


def test_an_old_room_file_without_warmth_still_loads(tmp_path):
    c = home(tmp_path)
    import json
    data = json.loads(c.path.read_text(encoding="utf-8"))
    for k in ("temp", "heater", "outside"):
        data.pop(k)
    c.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    room = c.load()
    assert room.temp == 18 and room.heater == "" and room.outside == {}
