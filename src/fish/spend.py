"""Spending tiers (decision 47): one switch that moves the knobs which decide how often she
calls the model. Pure data, no os.environ and no model; config.py reads FISH_SPEND and uses
these as the defaults, and a number set by hand in .env still wins over its tier."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tier:
    name: str
    prompt_chars: int  # how much memory goes into every chat prompt (the biggest cost per reply)
    leisure_max_per_day: int  # free moments a day, each one a couple of model calls
    reach_max_per_day: int  # messages she may start a day; 0 = no cap (decision 30)


# "normal" is exactly what the code did before tiers existed
TIERS = {
    "low": Tier("low", prompt_chars=4000, leisure_max_per_day=1, reach_max_per_day=3),
    "normal": Tier("normal", prompt_chars=6000, leisure_max_per_day=3, reach_max_per_day=0),
    "high": Tier("high", prompt_chars=8000, leisure_max_per_day=5, reach_max_per_day=0),
}

ALIASES = {"省": "low", "正常": "normal", "随便": "high", "": "normal"}


def tier_of(name: str) -> Tier:
    """Tier for a FISH_SPEND value (low / normal / high, or 省 / 正常 / 随便). An unknown word
    stops the start-up rather than quietly picking one: a typo here changes the bill."""
    key = name.strip().lower()
    key = ALIASES.get(key, key)
    if key not in TIERS:
        raise ValueError(f"FISH_SPEND={name!r}: use low, normal or high (省 / 正常 / 随便)")
    return TIERS[key]
