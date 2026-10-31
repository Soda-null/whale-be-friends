"""Spending tiers (decision 47): FISH_SPEND moves the defaults; a number set by hand wins."""

import pytest

from fish.config import load_settings
from fish.spend import TIERS, tier_of

KNOBS = ("FISH_SPEND", "FISH_PROMPT_CHARS", "FISH_LEISURE_MAX", "FISH_REACH_MAX")


@pytest.fixture
def env(tmp_path, monkeypatch):
    for k in KNOBS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("FISH_DB_PATH", str(tmp_path / "fish.db"))
    monkeypatch.setenv("TZ", "UTC")  # keep load_settings off the real home file
    (tmp_path / ".env").write_text("", encoding="utf-8")
    return tmp_path / ".env", monkeypatch


def test_no_setting_is_exactly_what_it_was_before_tiers(env):
    path, _ = env
    s = load_settings(path)
    assert (s.spend, s.prompt_chars, s.leisure_max_per_day, s.reach_max_per_day) == ("normal", 6000, 3, 0)


def test_low_spends_less_than_normal_and_high_more():
    low, normal, high = TIERS["low"], TIERS["normal"], TIERS["high"]
    assert low.prompt_chars < normal.prompt_chars < high.prompt_chars
    assert low.leisure_max_per_day < normal.leisure_max_per_day < high.leisure_max_per_day
    assert low.reach_max_per_day > 0  # low caps what she starts; normal and high do not (decision 30)


def test_the_tier_sets_the_defaults(env):
    path, monkeypatch = env
    monkeypatch.setenv("FISH_SPEND", "low")
    s = load_settings(path)
    assert (s.spend, s.prompt_chars, s.leisure_max_per_day, s.reach_max_per_day) == (
        "low", TIERS["low"].prompt_chars, TIERS["low"].leisure_max_per_day, TIERS["low"].reach_max_per_day)


def test_a_number_set_by_hand_beats_the_tier(env):
    path, monkeypatch = env
    monkeypatch.setenv("FISH_SPEND", "low")
    monkeypatch.setenv("FISH_LEISURE_MAX", "2")
    s = load_settings(path)
    assert s.leisure_max_per_day == 2 and s.prompt_chars == TIERS["low"].prompt_chars


def test_chinese_names_work_and_a_typo_stops_the_start(env):
    assert tier_of("省").name == "low" and tier_of("随便").name == "high" and tier_of(" 正常 ").name == "normal"
    with pytest.raises(ValueError, match="FISH_SPEND"):
        tier_of("cheap")
