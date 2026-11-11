"""She finds a memory by what it means, not only by shared characters (decision 58). The model
itself is not needed here: a made-up encoder stands in for it. Without the model's files she
is exactly who she was."""

from datetime import datetime

from fish.brain.meaning import ASKING, COS_HI, COS_LO, Meaning, embedder
from fish.memory import BigramEmbedder, MemoryStore, recall
from fish.storage import connect

T0 = datetime(2027, 1, 9, 20, 0)
TIRED = ("累", "熬夜", "困")


def fake_encode(text: str) -> list[float]:
    """Two directions: lines about being worn out, and everything else."""
    return [1.0, 0.0] if any(w in text for w in TIRED) else [0.0, 1.0]


def store_with(tmp_path, *texts):
    store = MemoryStore(connect(tmp_path / "fish.db"))
    return store, [store.add("event", t, importance=5, now=T0) for t in texts]


def test_a_line_finds_a_memory_it_shares_no_character_with(tmp_path):
    store, (late, lunch) = store_with(tmp_path, "他天天熬夜赶项目", "他中午吃了牛肉面")
    cue = "最近好累"
    assert BigramEmbedder().relevance(cue, late) == 0  # by words she never thinks of it
    assert recall(store, cue, T0) == []
    back = recall(store, cue, T0, embedder=Meaning(fake_encode))
    assert [r.memory.id for r in back] == [late.id]


def test_words_still_find_what_they_found(tmp_path):
    store, (lunch,) = store_with(tmp_path, "他中午吃了牛肉面")
    by_words = BigramEmbedder().relevance("牛肉面好吃吗", lunch)
    assert by_words > 0 and Meaning(lambda t: [0.0, 1.0] if ASKING in t else [1.0, 0.0]).relevance(
        "牛肉面好吃吗", lunch) == by_words  # meaning says nothing: the words' answer stands


def test_a_weak_likeness_says_nothing():
    m = Meaning(lambda t: [1.0, 0.0] if ASKING in t else [COS_LO, (1 - COS_LO ** 2) ** 0.5])
    assert m.by_meaning("随便说的一句", "不相干的事") == 0.0
    same = Meaning(lambda t: [1.0, 0.0])
    assert same.by_meaning("说的是这件事", "同一件事") == 1.0 and COS_LO < COS_HI
    for nod in ("嗯", "哈哈哈", "好的吧"):  # nothing to go looking with
        assert same.by_meaning(nod, "同一件事") == 0.0


def test_each_memory_is_worked_out_once():
    calls = []
    m = Meaning(lambda t: calls.append(t) or [1.0, 0.0])
    for _ in range(3):
        m.by_meaning("最近好累", "他天天熬夜赶项目")
    assert calls == [ASKING + "最近好累", "他天天熬夜赶项目"]


def test_without_the_model_she_finds_by_words(tmp_path):
    assert isinstance(embedder(None), BigramEmbedder)
    assert isinstance(embedder(tmp_path / "nothing-here"), BigramEmbedder)
