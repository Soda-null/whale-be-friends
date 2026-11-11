"""Messages that crossed (decision 58): he wrote his line before her last one reached him.

She answers his first messages; while she is thinking and her bubbles go out one by one he has
already sent the next. Or she texts first in the very seconds he is typing. In the chat it then
reads as if he were answering her line, and she answers that: both talk past each other. The
channel knows the two times, so it says so in front of his line, the way it marks what piled up
while she was offline (wechat.backlog_note). The brain never learns this was WeChat.

A message with no send time on it is never marked: without the time nothing is known.
"""

from __future__ import annotations

import time
from typing import Callable

NOTE = "（这句是他在你上一条消息发到之前就打好的，接的是他自己前面的话，不是在回你那条）"


class Crossing:
    """Remembers when her last bubble went out."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self.sent: float | None = None

    def she_sent(self) -> None:
        self.sent = self.clock()

    def note(self, his_times: list[float | None]) -> str:
        """NOTE when the first thing he sent in this batch was sent before her last bubble."""
        first = next((t for t in his_times if t is not None), None)
        return NOTE if self.sent is not None and first is not None and first < self.sent else ""
