#!/usr/bin/env python3
"""A week of her in one screen: how she really did, counted, no model called, nothing written.

    yu review [days]                     on the Mac: this file is piped to the box over ssh
    python3 scripts/review.py [days]     on the machine she lives on, from the repo root

Standard library only and no `fish` import, on purpose: `scripts/fish.sh` pipes this one file to
the box, so it works whatever code the box runs, with no deploy and no restart. What it must
know about her (when her day ends, what she can do) is copied here; tests/test_review.py fails
if the copies drift. The database is opened mode=ro, and the printed report is the only output.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote

NIGHT_BOUNDARY = time(3, 30)  # her day ends here: 01:00 still belongs to yesterday
WEEKDAYS = "一二三四五六日"

# Her free-time menu: the activity keys in leisure_log.choice.
PICKS = {"nothing": "发呆", "news": "翻新闻", "bilibili": "刷 B 站", "book": "读书", "curious": "查好奇的", "cottage": "屋里的事"}
# What she did in her room: key, what to call it, the words the room's record uses for it. Order
# matters: sowing also says it watered.
DEEDS = (("sow", "种下", "种下了"), ("water", "浇水", "浇了水"), ("pick", "摘菜", "，放进冰箱"),
         ("feed", "喂鱼", "喂了鱼食"), ("change", "换水", "换了缸里的水"), ("namefish", "起名", "起了名字"),
         ("lake", "码头", "出门去湖边码头"), ("florist", "花店", "出门去镇上的花店"), ("shop", "买菜", "出门去镇上的菜店"),
         ("rice", "煮饭", "煮"), ("cook", "做饭", "开始做"), ("wash", "洗碗", "开始洗碗"), ("bed", "叠被子", "叠了被子"),
         ("nap", "午觉", "睡了个午觉"), ("leave", "给他留东西", "给他留了"))
DEED_NAME = {key: name for key, name, _ in DEEDS}
# The things worth asking "did she really do it": these four are what the record can also tell us.
THINGS = (("种菜", ("sow", "water", "pick")), ("养鱼", ("feed", "change", "namefish")), ("码头", ("lake",)), ("花店", ("florist",)))
THING_KEYS = {k for _, keys in THINGS for k in keys}
VEGETABLES = ("小葱", "小白菜", "小番茄")  # what grows in her pots; watering only flowers is not growing vegetables

MIN_PHRASE, MAX_PHRASES, MAX_REPEATS, MAX_LISTED = 3, 12, 8, 5
# When a number reaches the top of the report. A short line ("嗯") needs far more repeats than a long one.
LOUD_PHRASE, LOUD_REPEAT, LOUD_SHORT_REPEAT, LOUD_FIRST_A_DAY, LOUD_RUN = 5, 3, 10, 8, 3

BRACKET = re.compile(r"\[[^\]]*\]")  # [Doge], [图片：...], [表情包：...]: not words anyone typed
CHINESE = re.compile(r"[一-鿿]+")
TRAILING = "。！？!?~～…，,. 、"


def fish_day(ts: datetime) -> date:
    return ts.date() if ts.time() >= NIGHT_BOUNDARY else ts.date() - timedelta(days=1)


def open_readonly(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{quote(str(db.resolve()))}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def rows(conn: sqlite3.Connection, sql: str, *args) -> list[sqlite3.Row]:
    """All the rows, or none if this database is older than the table or column asked about."""
    try:
        return conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError as e:
        if "no such" in str(e):
            return []
        raise


def md(d: date | str) -> str:
    return (d.isoformat() if isinstance(d, date) else d)[5:10]


def day_name(d: date) -> str:
    return f"{md(d)} 周{WEEKDAYS[d.weekday()]}"


def short(text: str, n: int = 30) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n] + "…"


def pad(text: str, width: int) -> str:
    """Right-align by what the terminal shows: a Chinese character takes two columns."""
    shown = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return " " * max(0, width - shown) + text


# --- the chat -----------------------------------------------------------------------------


def bubbles(text: str) -> list[str]:
    """One stored message is one bubble per line on WeChat. Stickers and picture notes have no words."""
    return [b for b in (BRACKET.sub("", line).strip() for line in text.splitlines()) if b]


@dataclass
class Message:
    ts: datetime
    role: str  # 'user' | 'fish'
    text: str
    first: bool = False  # she said it without being answered to

    @property
    def day(self) -> date:
        return fish_day(self.ts)


def load_messages(conn: sqlite3.Connection) -> list[Message]:
    """A reply is stored with the same time as what he said; anything else of hers she said first."""
    msgs: list[Message] = []
    for r in rows(conn, "SELECT ts, role, text FROM messages ORDER BY id"):
        m = Message(datetime.fromisoformat(r["ts"]), r["role"], r["text"])
        before = msgs[-1] if msgs else None
        m.first = m.role == "fish" and not (before and before.role == "user" and before.ts == m.ts)
        msgs.append(m)
    return msgs


def average(lines: list[str]) -> float:
    return sum(map(len, lines)) / len(lines) if lines else 0.0


def daily(msgs: list[Message], days: list[date]) -> list[str]:
    out = ["== 每天聊了多少（一条 = 微信上一个气泡，长度是字数）==",
           "  " + pad("", 10) + pad("他说", 7) + pad("平均", 7) + pad("她说", 7) + pad("平均", 7) + pad("她先开口", 10)]
    def row(label: str, chunk: list[Message]) -> str:
        his = [b for m in chunk if m.role == "user" for b in bubbles(m.text)]
        hers = [b for m in chunk if m.role == "fish" for b in bubbles(m.text)]
        return ("  " + label + pad(str(len(his)), 7) + pad(f"{average(his):.1f}", 7) + pad(str(len(hers)), 7)
                + pad(f"{average(hers):.1f}", 7) + pad(str(sum(m.first for m in chunk)), 10))
    today = days[-1]
    for d in days:
        out.append(row(day_name(d) if d != today else md(d) + " 今天", [m for m in msgs if m.day == d]))
    out.append(row(pad("合计", 10), msgs))
    return out


def phrases(lines: list[tuple[date, str]]) -> list[tuple[str, int, int]]:
    """Four-character phrases she keeps using: (phrase, how many bubbles, how many days). One
    long sentence said again makes many overlapping phrases; only the most frequent stays, and
    what starts on a particle ("了一下子") is a piece of something, not a phrase."""
    count: Counter[str] = Counter()
    on_days: dict[str, set[date]] = defaultdict(set)
    for day, line in lines:
        grams = {run[i:i + 4] for run in CHINESE.findall(line) for i in range(len(run) - 3)}
        for g in grams:
            count[g] += 1
            on_days[g].add(day)
    kept: list[tuple[str, int, int]] = []
    for g, n in sorted(count.items(), key=lambda kv: (-kv[1], kv[0])):
        if n < MIN_PHRASE or len(kept) == MAX_PHRASES:
            break
        if g[0] not in "了的着" and not any(_overlap(g, other) for other, _, _ in kept):
            kept.append((g, n, len(on_days[g])))
    return kept


def _overlap(a: str, b: str) -> bool:
    """The same words seen twice: one runs on into the other, or they differ in an end character."""
    return (any(a[k:] == b[:4 - k] or b[k:] == a[:4 - k] for k in (1, 2))
            or a[1:] == b[1:] or a[:3] == b[:3])


def repeats(lines: list[tuple[date, str]]) -> list[tuple[str, int, int]]:
    """Bubbles said word for word more than once, trailing punctuation aside."""
    count: Counter[str] = Counter()
    on_days: dict[str, set[date]] = defaultdict(set)
    for day, line in lines:
        same = line.rstrip(TRAILING)
        if same:
            count[same] += 1
            on_days[same].add(day)
    return [(t, n, len(on_days[t])) for t, n in sorted(count.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0])) if n > 1]


def tics(msgs: list[Message]) -> tuple[list[str], list[str]]:
    lines = [(m.day, b) for m in msgs if m.role == "fish" for b in bubbles(m.text)]
    said, again = phrases(lines), repeats(lines)
    out = ["== 她反复说的 ==", "  四个字的口头禅（几条气泡里有 / 几天都有）："]
    out += [f"    {p}  {n} 条 / {d} 天" for p, n, d in said] or ["    没有说过 3 次以上的"]
    share = sum(n for _, n, _ in again) / len(lines) if lines else 0
    out.append(f"  一字不差说过不止一次的气泡：{len(again)} 种，占她这段时间气泡的 {share:.0%}。最多的几句：")
    out += [f"    {n} 回 / {d} 天  {short(t)}" for t, n, d in again[:MAX_REPEATS]] or ["    没有"]
    loud = [f"口头禅「{p}」说了 {n} 条，{d} 天都有" for p, n, d in said[:2] if n >= LOUD_PHRASE]
    loud += [f"这句一字不差说了 {n} 回：{short(t)}" for t, n, _ in again
             if n >= LOUD_SHORT_REPEAT or (n >= LOUD_REPEAT and len(t) >= 4)][:2]
    return out, loud


def speaking_first(msgs: list[Message]) -> tuple[list[str], list[str]]:
    """Her first messages, whether he picked them up, and runs of them with him silent between."""
    firsts = [m for m in msgs if m.first]
    answered = 0
    runs: list[list[Message]] = []
    run: list[Message] = []
    for i, m in enumerate(msgs):
        if m.role == "user":
            if len(run) >= 2:
                runs.append(run)
            run = []
        elif m.first:
            run.append(m)
            if i + 1 < len(msgs) and msgs[i + 1].role == "user":
                answered += 1
    if len(run) >= 2:
        runs.append(run)
    out = ["== 她先开口 ==", f"  主动发了 {len(firsts)} 回，他接话 {answered} 回，没接（或者还没接）{len(firsts) - answered} 回。"]
    longest = max(runs, key=len) if runs else []
    out.append(f"  连发没人回（他没说话、她连着发两回以上）：{len(runs)} 次" +
               (f"，最长一串 {len(longest)} 回，在 {day_name(longest[0].day)}。" if runs else "。"))
    per_day = Counter(m.day for m in firsts)
    loud = [f"{day_name(d)} 她一天主动发了 {n} 回，有点多" for d, n in sorted(per_day.items()) if n >= LOUD_FIRST_A_DAY]
    if longest and len(longest) >= LOUD_RUN:
        loud.append(f"连发没人回 {len(runs)} 次，最长一串 {len(longest)} 回（{day_name(longest[0].day)}）")
    return out, loud


# --- what she did -------------------------------------------------------------------------


def deed_of(text: str | None) -> str | None:
    """Which deed a line of the room's record is. A result can hold several lines (she came home,
    then did it), the deed last; "从花店回来了，…浇了水" is coming home, "他…" is his doing."""
    for line in reversed((text or "").split("；")):
        if not line.startswith(("从", "他")):
            for key, _, words in DEEDS:
                if words in line:
                    return key
    return None


def counts_as_growing(key: str | None, text: str) -> bool:
    return key != "water" or any(v in text for v in VEGETABLES)


def load_room(db: Path) -> dict:
    try:
        return json.loads((db.parent / "cottage" / "now.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def leisure(conn: sqlite3.Connection, days: list[date]) -> list[sqlite3.Row]:
    return [r for r in rows(conn, "SELECT ts, choice, line, result FROM leisure_log ORDER BY id")
            if fish_day(datetime.fromisoformat(r["ts"])) in days]


def failed(r: sqlite3.Row) -> bool:
    return (r["result"] or "").endswith("没弄成")


def free_time(moments: list[sqlite3.Row]) -> tuple[list[str], list[str]]:
    picked = Counter(r["choice"] for r in moments if r["choice"])
    deeds = Counter(deed_of(r["result"]) or "?" for r in moments if r["choice"] == "cottage" and not failed(r))
    out = [f"== 空闲时间：一共 {len(moments)} 段，她都选了什么 =="]
    for key, n in picked.most_common():
        line = f"  {PICKS.get(key, key)} {n} 回"
        if key == "cottage":
            line += "：" + "、".join(f"{DEED_NAME.get(k, '别的')} {v}" for k, v in deeds.most_common())
        out.append(line)
    undecided = sum(1 for r in moments if not r["choice"])
    not_done = [r for r in moments if failed(r)]
    if undecided:
        out.append(f"  开了头没选成（模型没回好）：{undecided} 段")
    out += [f"  想做没弄成：{short(r['line'] or '')}" for r in not_done[:MAX_LISTED]]
    never = [name for key, name in PICKS.items() if key not in picked]
    never_deeds = [name for key, name, _ in DEEDS if key not in deeds]
    out.append("  一次都没选：" + ("、".join(never) or "（都选过）") + "；屋里的事里：" + ("、".join(never_deeds) or "（都选过）"))
    out.append("  （只记她选了什么，不记当时菜单上有没有。比如花盆满了就不会摆「种下」。）")
    loud = [f"空闲时一次都没选：{'、'.join(never)}"] if never and moments else []
    return out, loud


def things(moments: list[sqlite3.Row], room: dict, days: list[date]) -> tuple[list[str], list[str]]:
    """Her free-time picks over the whole stretch, plus what the room's record adds: it keeps two
    days, so what she did in the middle of a chat can be seen only that far back."""
    done = Counter()
    seen = set()
    for r in moments:
        key = deed_of(r["result"])
        if key and not failed(r):
            seen.add((r["ts"][:16], key))
            done[key] += counts_as_growing(key, r["result"])
    for e in room.get("events", []):
        key, line, ts = deed_of(e.get("line")), e.get("line", ""), e.get("ts", "")
        if key in THING_KEYS and ts and fish_day(datetime.fromisoformat(ts)) in days and (ts[:16], key) not in seen:
            done[key] += counts_as_growing(key, line)
    state = {"种菜": _pots(room), "养鱼": _tank(room), "码头": _last(room, "lake"), "花店": _last(room, "florist")}
    out = ["== 种菜、养鱼、码头、花店真做了几回（只浇花不算种菜）=="]
    for name, keys in THINGS:
        total = sum(done[k] for k in keys)
        parts = "（" + "、".join(f"{DEED_NAME[k]} {done[k]}" for k in keys) + "）" if len(keys) > 1 else ""
        out.append(f"  {name} {total} 回{parts}  {state[name]}".rstrip())
    out.append("  （算的是她空闲时挑的；聊天中顺手做的只查得到最近两天，屋里的记录只留两天。）")
    zero = [name for name, keys in THINGS if not sum(done[k] for k in keys)]
    # nothing to go on (a brand-new her) is not the same as not having done it
    return out, [f"这段时间一回都没做：{'、'.join(zero)}"] if zero and (moments or room) else []


def _pots(room: dict) -> str:
    pots = room.get("pots")
    if pots is None:
        return ""
    planted = [p["plant"] for p in pots if p.get("plant")]
    return f"现在：种着{'、'.join(planted)}，空着 {len(pots) - len(planted)} 盆" if planted else f"现在：{len(pots)} 个花盆都空着"


def _tank(room: dict) -> str:
    tank = room.get("tank") or {}
    if not tank:
        return "现在：还没有小金鱼"
    fed = tank.get("fed")
    return f"现在：{tank.get('name') or '小金鱼还没名字'}" + (f"，上次喂是 {md(fed)}" if fed else "，还没喂过")


def _last(room: dict, key: str) -> str:
    at = (room.get("been") or {}).get(key)
    return f"上次是 {md(at)}" if at else ""


# --- the nights and the follow-ups --------------------------------------------------------


def nights(conn: sqlite3.Connection, db: Path, days: list[date], born: date | None) -> tuple[list[str], list[str]]:
    """Each night closes the day before it. Only diary, phase, letter and chat summaries leave a
    trace per day; routine_runs holds just the last run of each routine."""
    today = days[-1]
    closed = [d for d in days[:-1] if born is not None and d >= born]
    diaries = {r["day"] for r in rows(conn, "SELECT day FROM diary")}
    phases = {r["day"] for r in rows(conn, "SELECT day FROM phase")}
    drawer = db.parent / "cottage" / "抽屉"
    letters = {p.stem for p in drawer.glob("*.md")} if drawer.is_dir() else set()
    unsummed: Counter[date] = Counter()
    for r in rows(conn, "SELECT started FROM episodes WHERE gist IS NULL AND summary IS NULL"):
        unsummed[fish_day(datetime.fromisoformat(r["started"]))] += 1
    runs = {r["name"]: r["last_run"] for r in rows(conn, "SELECT name, last_run FROM routine_runs")}

    def mark(ok: bool) -> str:
        return "有" if ok else "没有"

    out, loud = ["== 每晚整理（一晚管前一天，凌晨 3:30 跑）=="], []
    for d in closed:
        iso = d.isoformat()
        diary, phase, letter = iso in diaries, iso in phases, iso in letters
        wants_letter = bool(letters) and iso >= min(letters)  # the letters began one night; no blame before
        verdict = ""
        if not diary:
            verdict = "整理跑了，日记没写出来（多半是模型那次没回好）" if phase else "那晚的整理整个没跑"
            loud.append(f"{day_name(d)} 没有日记：{verdict}")
        elif wants_letter and not letter:
            verdict = "日记有，信没写出来"
        line = f"  {day_name(d)}  日记{mark(diary)}  这阵子{mark(phase)}"
        if letters:
            line += f"  给他的信{mark(letter) if wants_letter else '（那时还没有）'}"
        if unsummed[d]:
            line += f"  {unsummed[d]} 段聊天没写摘要"
        out.append(line + (f"  ← {verdict}" if verdict else ""))
    if not closed:
        out.append("  这段时间还没有整理过的日子")
    last = md(runs["nightly"]) if runs.get("nightly") else "（从来没跑过）"
    reflected = md(runs["reflect"]) if runs.get("reflect") else "（还没有）"
    expected = today - timedelta(days=1)
    out.append(f"  上次整理管的是 {last}；上次回头反思管到 {reflected}（每 7 天或 5 段聊天一回）")
    if born is not None and today > born and runs.get("nightly") != expected.isoformat():
        loud.append(f"昨晚的整理没跑：上次整理管的是 {last}，该是 {md(expected)}")
    out.append("  （合并、改写、压缩旧聊天、数习惯这几步不按天留记录，这里查不了；流水在 journalctl --user -u dafeiyu-nightly。）")
    return out, loud


def followups(conn: sqlite3.Connection, days: list[date]) -> tuple[list[str], list[str]]:
    start, today = days[0].isoformat(), days[-1].isoformat()
    records = rows(conn, "SELECT p.text, p.due, p.created, p.status, e.started AS asked_at FROM prospective p"
                         " LEFT JOIN episodes e ON e.id = p.asked_episode")
    new = [r for r in records if fish_day(datetime.fromisoformat(r["created"])) in days]
    asked = [r for r in records if r["status"] == "asked"
             and start <= (fish_day(datetime.fromisoformat(r["asked_at"])).isoformat() if r["asked_at"] else r["due"]) <= today]
    lapsed = [r for r in records if r["status"] == "expired" and start <= r["due"] <= today]
    waiting = sorted((r for r in records if r["status"] == "open"), key=lambda r: r["due"])
    out = ["== 惦记的事 ==", f"  新记下 {len(new)} 条，问了 {len(asked)} 条，到期没问就放下了 {len(lapsed)} 条。"]
    if waiting:
        out.append(f"  现在还挂着 {len(waiting)} 条，最早 {md(waiting[0]['due'])} 到期。")
    out += [f"  没问成（{md(r['due'])} 到期）：{short(r['text'])}" for r in lapsed[:MAX_LISTED]]
    return out, [f"惦记的事有 {len(lapsed)} 条到期没问就放下了"] if lapsed else []


# --- the report ---------------------------------------------------------------------------


def report(db: Path, now: datetime, days_back: int = 7) -> str:
    today = fish_day(now)
    days = [today - timedelta(days=n) for n in range(days_back - 1, -1, -1)]
    conn = open_readonly(db)
    try:
        everything = load_messages(conn)
        born = everything[0].day if everything else None
        msgs = [m for m in everything if m.day in days]
        moments = leisure(conn, days)
        room = load_room(db)
        parts = [nights(conn, db, days, born), speaking_first(msgs), tics(msgs),
                 free_time(moments), things(moments, room, days), followups(conn, days)]
    finally:
        conn.close()
    loud = [line for _, flags in parts for line in flags]
    head = [f"大肥鱼这 {days_back} 天的复盘：{day_name(days[0])} 到 {day_name(today)}（她的一天到凌晨 3:30，今天还没过完）", "",
            "== 先看这几条 =="]
    head += [f"  ! {line}" for line in loud] or ["  这段时间没有要紧的。"]
    sections = [head, daily(msgs, days)] + [lines for lines, _ in parts]
    return "\n\n".join("\n".join(s) for s in sections)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="她这几天的真实表现（只读，不调模型）")
    parser.add_argument("days", nargs="?", type=int, default=7, help="看最近几天，默认 7")
    parser.add_argument("--db", type=Path, default=Path("data/fish.db"), help="她的数据库，默认 data/fish.db")
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("天数至少是 1")
    if not args.db.is_file():
        print(f"找不到她的数据库：{args.db}", file=sys.stderr)
        return 2
    print(report(args.db, datetime.now(), args.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
