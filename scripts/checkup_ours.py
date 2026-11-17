"""The inside-joke part of the memory checkup (decision 61, docs/ours_design_zh.md §7): what
needs no judge. scripts/checkup.py calls it when a script has a "jokes" entry:

  "jokes": {"real": ["叛徒闹钟"], "once": ["纽扣包子", "拖拉机室友"]}

real: sayings he makes and brings back, which she should end up keeping. once: funny things he
says a single time, which must not end up as jokes of theirs. Whether she knows a joke when he
says it is asked by the script's own questions and graded by the judge like any other.

Counted here, from her ledger at the end and from the chat itself:
- kept: each real one is a joke at the end (成了 or 旧了);
- made up: anything else that ended up a joke (a `once` one, or words nobody meant as one);
- overuse: the most times she brought one joke up herself (his line did not say it) within
  WEEK days, against MOST_A_WEEK;
- used: whether she ever brought a real one up herself (soft: never is no failure).
"""

from __future__ import annotations

WEEK = 7
MOST_A_WEEK = 2
KEPT = ("alive", "old")
STATES = {"candidate": "候选", "alive": "成了", "old": "旧了", "dropped": "放下了"}
Turn = tuple[int, str, str, str]  # day, time, he, she


def her_uses(transcript: list[Turn], words: str) -> list[int]:
    """The days of the turns where she said the words and his line did not."""
    return [day for day, _, he, she in transcript if words in she and words not in he]


def most_in_a_week(days: list[int]) -> int:
    return max((sum(start <= d < start + WEEK for d in days) for start in days), default=0)


def jokes_report(spec: dict, transcript: list[Turn], jokes: list[dict]) -> dict:
    """jokes: her ledger at the end, one dict per joke (memory/ours.py)."""
    states = {j["words"]: j["state"] for j in jokes}
    real = list(spec.get("real", []))
    uses = {w: days for w in dict.fromkeys(real + list(states)) if (days := her_uses(transcript, w))}
    made_up = sorted(w for w, s in states.items() if s in KEPT and w not in real)
    most = max((most_in_a_week(days) for days in uses.values()), default=0)
    return {
        "states": states,
        "real": {w: states.get(w, "") for w in real}, "real_ok": all(states.get(w) in KEPT for w in real),
        "made_up": made_up, "made_up_ok": not made_up,
        "her_uses": uses, "most_in_a_week": most, "overuse_ok": most <= MOST_A_WEEK,
        "used": any(uses.get(w) for w in real),
    }


def report_lines(o: dict) -> list[str]:
    tick = lambda ok: "过" if ok else "**不过**"  # noqa: E731
    word = lambda s: STATES.get(s, "没记下")  # noqa: E731
    others = {w: s for w, s in o["states"].items() if w not in o["real"]}
    return [
        "- 梗（决定 61）：该成的 " + "、".join(f"「{w}」{word(s)}" for w, s in o["real"].items())
        + f" → {tick(o['real_ok'])}",
        "- 梗：不该成却成了的 " + ("、".join(f"「{w}」" for w in o["made_up"]) or "没有") + f" → {tick(o['made_up_ok'])}"
        + ("；别的她记过的：" + "、".join(f"「{w}」{word(s)}" for w, s in others.items()) if others else ""),
        f"- 梗：同一个梗她 {WEEK} 天内自己提起最多 {o['most_in_a_week']} 次，线是 {MOST_A_WEEK} 次 → {tick(o['overuse_ok'])}"
        + ("（" + "；".join(f"「{w}」第 {'、'.join(map(str, days))} 天" for w, days in o["her_uses"].items()) + "）"
           if o["her_uses"] else ""),
        "- 梗：她自己用过该成的梗（软指标）：" + ("用过" if o["used"] else "没用过"),
    ]
