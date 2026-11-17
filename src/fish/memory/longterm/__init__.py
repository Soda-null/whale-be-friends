"""Long-term memories: the `memories` table and a memory's lifecycle.

add -> (recall) touch -> correct (supersede) / merge -> never deleted.
Data and math only; the text of a memory is written by the brain or the nightly routine.
Field meanings: docs/memory_design_zh.md §4.

record     one memory: the `Memory` record, its kinds, how it reads and fades
words      comparing words: overlap, what a line is about, whose words a note holds
rows       the table one row at a time: add, get, alive, touch, supersede
choosing   `note`: choosing before writing, repeats, gists (decisions 19-21, 57)
replacing  correct, merge, and what she used to think
promises   promises between them, results, which memory a follow-up is about
cards      her card of facts about him, the how-to card, the other fixed reads

`MemoryStore` is these parts put together. A new group of things to do with memories is one
more file here and one more name in the line below.
"""

from fish.memory.longterm.cards import PROFILE_IMPORTANCE, PROFILE_SIZE, Cards, card_order
from fish.memory.longterm.choosing import (ABOUT_HIM_KINDS, KIND_CAPS, REPEAT_SIMILARITY, SELF_REPEAT_SIMILARITY,
                                           Choosing)
from fish.memory.longterm.promises import PACT_LINK, Promises
from fish.memory.longterm.record import (KINDS, UNASKED, WHYS, Memory, _from_row, about_of, ceiling_of,
                                         days_between, iso)
from fish.memory.longterm.replacing import Replacing, strongest_about, why_before_v3
from fish.memory.longterm.words import content_words, echoes_her, overlap


class MemoryStore(Choosing, Replacing, Promises, Cards):
    """Everything she does with her long-term memories, over one database connection."""


__all__ = [
    "ABOUT_HIM_KINDS", "KINDS", "KIND_CAPS", "PACT_LINK", "PROFILE_IMPORTANCE", "PROFILE_SIZE", "REPEAT_SIMILARITY",
    "SELF_REPEAT_SIMILARITY", "UNASKED", "WHYS", "Memory", "MemoryStore", "_from_row", "about_of", "card_order",
    "ceiling_of", "content_words", "days_between", "echoes_her", "iso", "overlap", "strongest_about", "why_before_v3",
]
