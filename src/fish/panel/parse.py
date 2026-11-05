"""The `fish` commands print for people: `== 标题 ==` and indented lines. This turns that into
what the page draws, so a new section in `fish life` or `fish show` needs no second copy here."""

from __future__ import annotations

import ast
import re

HEADER = re.compile(r"^== (.+?) ?==\s*(.*)$")
MEMORY = re.compile(r"^\[#\d+\] (\w+)\s+重要\s*(\d+) R=[\d.]+ (钉住|想不起|模糊|清楚)\s+(.*)$", re.S)
WITH_ID = re.compile(r"^\[#\d+\] ")
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{2}:\d{2})\s+(.*)$", re.S)
KINDS = {"event": "发生的事", "fact": "事实", "howto": "相处", "insight": "看法", "self": "她自己", "world": "见闻"}
PASTIMES = {"cottage": "屋里的事", "bilibili": "刷 B 站", "news": "看新闻", "book": "读书", "curious": "查好奇的事",
            "nothing": "发呆", "idle": "发呆"}


def sections(text: str) -> tuple[list[str], list[dict]]:
    """(the "！" warnings at the top, the sections). A line with no indent inside a section is
    the rest of the entry before it: memories can hold line breaks."""
    alerts: list[str] = []
    out: list[dict] = []
    for raw in text.splitlines():
        if raw.startswith("！"):
            alerts.append(raw[1:])
            continue
        header = HEADER.match(raw)
        if header:
            out.append({"title": header[1], "inline": header[2].strip(), "lines": []})
        elif out and raw.startswith("  "):
            out[-1]["lines"].append(raw.strip())
        elif out and raw.strip() and out[-1]["lines"]:
            out[-1]["lines"][-1] += "\n" + raw.strip()
    return alerts, out


def _named(found: list[dict], start: str) -> dict:
    return next((s for s in found if s["title"].startswith(start)), {"title": "", "inline": "", "lines": []})


def _dated(line: str) -> dict:
    match = DATED.match(line)
    return {"when": match[1], "text": match[2]} if match else {"when": "", "text": line}


def _after(lines: list[str], prefix: str) -> str:
    return next((line[len(prefix):] for line in lines if line.startswith(prefix)), "")


def life(text: str) -> dict:
    alerts, found = sections(text)
    now, today = _named(found, "她现在"), _named(found, "今天")
    clock = re.search(r"（(.+)）", now["title"])
    return {
        "alerts": alerts,
        "at": clock[1] if clock else "",
        "mood": _after(now["lines"], "心情："),
        "phase": _after(now["lines"], "这阵子："),
        "room": [x for x in now["lines"] if not x.startswith(("心情：", "这阵子："))],
        "reading": _after(today["lines"], "在读 / 在追："),
        "today": [_dated(x) for x in today["lines"] if not x.startswith("在读 / 在追：") and x != "还没什么事"],
        "diary": [_dated(x) for x in _named(found, "日记")["lines"] if x != "还没写过"],
    }


def me(text: str) -> list[dict]:
    pairs = (line.split("：", 1) for line in _named(sections(text)[1], "你的状态")["lines"] if "：" in line)
    return [{"name": k, "value": v} for k, v in pairs]


def _plain(section: dict) -> list[str]:
    return [WITH_ID.sub("", line) for line in section["lines"]]


def _relationship(inline: str) -> str:
    match = re.match(r"(\{.*?\})\s*(.*)", inline)
    if not match:
        return inline
    try:
        stats = ast.literal_eval(match[1])
    except (ValueError, SyntaxError):
        return inline
    return f"认识 {stats.get('days_known', 0)} 天，聊过 {stats.get('days_talked', 0)} 天，连着 {stats.get('streak', 0)} 天；{match[2]}"


def _pastimes(inline: str) -> str:
    return re.sub(r"[a-z_]+", lambda m: PASTIMES.get(m[0], m[0]), inline)


def memories(text: str) -> dict:
    _, found = sections(text)
    long_term = []
    for line in _named(found, "长期条目")["lines"]:
        match = MEMORY.match(line)
        if match:
            words, _, source = match[4].partition("  ← ")
            long_term.append({"kind": KINDS.get(match[1], match[1]), "importance": int(match[2]), "state": match[3],
                              "text": words, "source": source})
    phase = _named(found, "这阵子")["inline"]
    mood = _named(found, "当日心情")["inline"]
    numbers = re.search(r"精力 (\d+) 无聊 (\d+) 饿 (\d+)", mood)
    how = _named(found, "和他相处") if _named(found, "和他相处")["title"] else _named(found, "和她相处")
    return {
        "mood": mood.split("  (")[0],
        "body": {"精力": int(numbers[1]), "无聊": int(numbers[2]), "饿": int(numbers[3])} if numbers else {},
        "phase": phase.split("  (")[0],
        "traits": _named(found, "底色")["inline"],
        "relationship": _relationship(_named(found, "关系")["inline"]),
        "pastimes": _pastimes(_named(found, "空闲")["inline"]),
        "profile": _plain(_named(found, "底牌")),
        "howto_title": how["title"],
        "howto": _plain(how),
        "waiting": [_dated(x) for x in _plain(_named(found, "惦记"))],
        "chats": [_dated(x) for x in _named(found, "最近的聊天")["lines"]],
        "memories": long_term,
    }


def plain_sections(text: str) -> list[dict]:
    """For a report the page shows as it is (the weekly review)."""
    alerts, found = sections(text)
    if found:
        return found
    return [{"title": "", "inline": "", "lines": alerts + [x for x in text.splitlines() if x.strip()]}]
