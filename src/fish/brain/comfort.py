"""When his line says he is hurting or letting off steam, she is told so right at that line
(decision 57).

Left to itself the model calms and corrects: to "他们会后悔的" it answered that he should not count
on it, and a third bubble went to dinner. A friend takes his side first. The rule for it is in
chat.md, but rules in the middle of the prompt lose to the chat around them (prompt.py,
FACE_NOW); this note stands at his line. Only in the prompt, never stored.
"""

from __future__ import annotations

import re

# how he feels, said in so many words or with one of WeChat's faces; and words people vent with
_HURT = re.compile(r"难受|难过|郁闷|伤心|心酸|想哭|哭了|哭出来|哭死|崩溃|绝望|心累|好累|累死|烦死|好烦|委屈|想家|焦虑"
                   r"|睡不着|失眠|压力好大|压力很大|撑不住|扛不住|受不了|气死|窝火|憋屈|不甘心|报复|凭什么"
                   r"|傻逼|(?<![a-z])sb(?![a-z])|妈的|我操|卧槽|tmd|\[表情：(?:大哭|流泪|心碎|委屈|难受|裂开)", re.I)
_NOT = re.compile(r"[不没别](?:是)?(?:太|怎么|那么)?(?:难受|难过|郁闷|伤心|焦虑|委屈|想家|累)")

COMFORT_NOTE = ("（他这会儿不好受，或者在撒气：先接住他这句，站在他那边，一两句就够；别劝、别讲道理、别纠正他的用词，"
                "也别岔到叮嘱和你自己的事上）")


def comfort_note(his: str) -> str:
    """The note for his line, "" when nothing in it says he is hurting."""
    return COMFORT_NOTE if _HURT.search(his) and not _NOT.search(his) else ""
