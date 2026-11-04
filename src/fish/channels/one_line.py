"""Only one of her on one WeChat (decision 52). Two of them answer him at once, and one with an
old cursor replays what was said days ago (decision 49: the Mac and the box, 10-31). So a second
one does not get as far as the phone line.

Two checks, for the two ways it can happen:
- on another machine: BOX= in .env says she lives over there and this machine only looks in. A
  lock cannot see across machines, and that is how it went on 10-31.
- on this machine: a lock on a file next to the credentials. The system lets go of it when the
  process ends, however it ends, so a crash never leaves her locked out.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TextIO

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

LOCK_AT = 1 << 20  # Windows locks a byte, and others can't read it: one far from the pid at the start


class SecondHer(Exception):
    """She may not start here; the message says why and what to do."""


def _lock(f: TextIO) -> bool:
    try:
        if fcntl is not None:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            f.seek(LOCK_AT)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return False
    return True


def hold_the_line(box: str, lock_file: Path) -> TextIO:
    """Returns the open lock file: keep it for as long as she runs. Raises SecondHer."""
    if box:
        raise SecondHer(f"她住在 {box}（这台机器的 .env 里写着 BOX={box}），这里不能再连微信："
                        "两条她会一起回你，还会把旧消息重放一遍（决定 49）。看她用 yu。"
                        f"真要把她搬回这台：先停掉 {box} 上的服务，再删掉这台 .env 里 BOX= 那行。")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    f = lock_file.open("a+", encoding="utf-8")
    if not _lock(f):
        f.close()
        try:
            pid = lock_file.read_text(encoding="utf-8").strip()
        except OSError:
            pid = ""
        raise SecondHer(f"这台机器上已经有一条她连着微信了（进程 {pid or '不明'}）。"
                        "要重开或重新扫码，先停掉那条（服务的话：systemctl --user stop dafeiyu-wechat）。")
    f.seek(0)
    f.truncate()
    f.write(str(os.getpid()))
    f.flush()
    return f
