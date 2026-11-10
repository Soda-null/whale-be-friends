"""WeChat's own little faces arrive as English codes ("[Doge]", "[Sob]"); she reads Chinese.

Left as they were, she read the English word aloud ("喂 咋了" to [Hey]) or had nothing to react to
(2026-11-10, about half of his emoji-only messages). Here they become what the face shows, before
the line reaches the brain: the brain never learns it was WeChat. A code not in the table is left
as it is. The words avoid anything her room listens for (吃, 饭, 留: brain/prompt.py HOME_WORDS).
"""

from __future__ import annotations

import re

FACES = {
    "Doge": "狗头，在开玩笑", "Hey": "嘿哈", "Sob": "大哭", "Facepalm": "捂脸", "Emm": "呃，无语", "Smart": "机智",
    "Terror": "惊恐", "Grin": "呲牙笑", "BrokenHeart": "心碎", "Whimper": "委屈", "Toasted": "裂开", "Sweats": "流汗",
    "Smile": "微笑", "Laugh": "笑", "Chuckle": "偷笑", "Joyful": "开心", "Lol": "笑哭", "Cry": "流泪", "Awkward": "尴尬",
    "Sly": "坏笑", "Shy": "害羞", "Blush": "脸红", "Angry": "生气", "Shocked": "震惊", "Surprise": "惊讶", "Sleep": "睡了",
    "Drowsy": "困", "Yawn": "打哈欠", "Hug": "抱抱", "Heart": "爱心", "Kiss": "亲亲", "ThumbsUp": "点赞", "OK": "好的",
    "Clap": "鼓掌", "Fight": "加油", "Party": "庆祝", "Bye": "再见", "Wave": "挥手", "Concerned": "皱眉", "Duh": "无语",
    "Wow": "哇", "Onlooker": "围观", "Yeah!": "耶", "Sigh": "叹气", "Hurt": "难受", "Let Down": "失望", "Happy": "高兴",
    "Sick": "不舒服", "Worship": "膜拜", "Salute": "敬礼", "Shrunken": "皱脸", "Pout": "嘟嘴", "Tremble": "发抖",
}
_CODE = re.compile(r"\[([A-Za-z][A-Za-z !]*)\]")


def readable(text: str) -> str:
    """"[Doge][Doge]" -> "[表情：狗头，在开玩笑][表情：狗头，在开玩笑]"."""
    return _CODE.sub(lambda m: f"[表情：{FACES[m.group(1)]}]" if m.group(1) in FACES else m.group(0), text)
