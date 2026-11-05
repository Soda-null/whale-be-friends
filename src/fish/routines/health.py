"""Is anything wrong that he should know about? Shown at the top of `fish life`, silent when not."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from fish.routines.night.context import diary_day, fish_day
from fish.routines.night.missed import CRASHED, days_without_diary, last_night_failed
from fish.routines.runs import last_run

DISK_FLOOR_GB = 10.0  # below this, whatever else fills the disk may stop her writing her memory

LABELS = {"diary": "日记", "letter": "给他的信", "reflect": "回头看", "merge": "合并重复的记忆",
          "contradictions": "改过时的记忆", "rewrite_facts": "改过时的记忆", "gist": "把反复的事写成大意",
          "growth": "每月回看"}


def problems(conn: sqlite3.Connection, data_dir: Path, now: datetime | None = None,
             disk_free_gb: float | None = None) -> list[str]:
    now = now or datetime.now()
    lines: list[str] = []
    done = last_run(conn, "nightly")
    if done and done < diary_day(now).isoformat():
        lines.append(f"夜里整理最后只跑到 {done}，之后的没跑（看 yu timers，机器是不是关过）")
    day, failed = last_night_failed(conn)
    model = sorted({LABELS.get(n, n) for n in failed if not n.startswith(CRASHED)})
    crashed = sorted(n.removeprefix(CRASHED) for n in failed if n.startswith(CRASHED))
    if model:
        lines.append(f"{day} 那晚模型没回上，没做成：{'、'.join(model)}（下一晚会补）")
    if crashed:
        lines.append(f"{day} 那晚程序出错：{'、'.join(crashed)}（不会自己好，得查）")
    missing = [d.isoformat() for d in days_without_diary(conn, fish_day(now))]
    if missing:
        lines.append(f"还缺这几天的日记：{'、'.join(missing)}（下一晚会补）")
    free = shutil.disk_usage(data_dir).free / 1024 ** 3 if disk_free_gb is None else disk_free_gb
    if free < DISK_FLOOR_GB:
        lines.append(f"她那台机器的硬盘只剩 {free:.0f} GB，满了她就存不进记忆了")
    return lines
