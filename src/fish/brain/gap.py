"""How long it has been since the last line of today's chat, said in words at his line (2026-11-10).

Earlier chats of today are shown word for word under the time they began, and the chat she is in
has no times at all, so a line from four hours ago read as "just now": after lunch she asked how
something was going that he had gone off to do in the morning. "Now" is in the middle of the
prompt; the gap is said where she answers.
Only in the prompt, never stored.
"""

from __future__ import annotations

from datetime import datetime, timedelta

LONG = timedelta(minutes=30)  # the pause after which a chat is a new one (memory/episodes.py)


def gap_words(gap: timedelta) -> str:
    minutes = int(gap.total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} 分钟"
    hours, rest = divmod(minutes, 60)
    return f"{hours} 个多小时" if rest >= 10 else f"{hours} 个小时"


def gap_note(last: datetime | None, now: datetime) -> str:
    """"" when the last line was just now, or there was none today."""
    if last is None or now - last < LONG:
        return ""
    return (f"（离上面最后一句话已经过了{gap_words(now - last)}：那时候正在做、正要去做的事多半已经过去了，"
            "别当成刚刚说的接着问）")
