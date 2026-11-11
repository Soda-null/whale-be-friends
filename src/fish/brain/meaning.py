"""Finding a memory by what it means, not only by the characters it shares (decision 58).

"最近好累" and "天天熬夜赶项目" share no character, so by words alone she never thinks of it.
A small Chinese sentence model on this machine (bge-small-zh, about 24 MB, no API, no money)
turns a line into numbers; two lines that mean the same land close together. `Meaning` is an
Embedder (memory/retrieval.py): a memory is as relevant as the better of the two ways says.

The memory layer calls no model, so this lives in the brain and is handed to the memory node.
Everything here is optional: without the model's files or its libraries `embedder` gives back
the words-only one and she is exactly who she was. Get the files with
scripts/get_meaning_model.py.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Sequence

from fish.memory import BigramEmbedder, Embedder, Memory

log = logging.getLogger(__name__)

FILES = ("tokenizer.json", "model_quantized.onnx")
# what bge-small-zh wants in front of a question that is looking for a passage
ASKING = "为这个句子生成表示以用于检索相关文章："
# Cosine between two lines: below COS_LO it says nothing (unrelated Chinese lines sit around
# 0.3), at COS_HI they are the same thing. Measured with scripts/recall_bench.py on the 小周
# checkup: answers in the first six places 46 -> 49 of 50 (0.35 lets ~90 memories in per
# line, 0.45 finds no more than words do); 48 with the two limits below.
COS_LO, COS_HI = 0.40, 0.80
# A likeness weaker than this is noise, and a line with fewer than MIN_CUE different characters
# ("嗯", "哈哈哈", "好的吧") means nothing to go looking with: without these two every such line
# brought six unrelated memories in front of her. With them the same checkup finds 48 of 50.
MIN_LIKENESS = 0.1
MIN_CUE = 4
MAX_TOKENS = 256

Encode = Callable[[str], Sequence[float]]  # a line -> a vector of length 1


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


class Meaning:
    """Words or meaning, whichever finds more. A memory's vector is worked out once and kept
    while the process lives (a few hundred memories, about a millisecond each)."""

    def __init__(self, encode: Encode, words: Embedder | None = None) -> None:
        self.encode = encode
        self.words = words or BigramEmbedder()
        self._memories: dict[str, Sequence[float]] = {}
        self._cue: tuple[str, Sequence[float]] | None = None

    def relevance(self, cue: str, memory: Memory) -> float:
        return max(self.words.relevance(cue, memory), self.by_meaning(cue, memory.text))

    def by_meaning(self, cue: str, text: str) -> float:
        if len({c for c in cue if c.isalnum()}) < MIN_CUE or not text.strip():
            return 0.0
        if self._cue is None or self._cue[0] != cue:
            self._cue = (cue, self.encode(ASKING + cue))
        if text not in self._memories:
            self._memories[text] = self.encode(text)
        cos = dot(self._cue[1], self._memories[text])
        likeness = min(1.0, (cos - COS_LO) / (COS_HI - COS_LO))
        return likeness if likeness >= MIN_LIKENESS else 0.0


def load(model_dir: Path) -> Encode | None:
    """The model as a function, or None when its files or libraries are not on this machine."""
    if not all((model_dir / name).is_file() for name in FILES):
        return None
    try:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(model_dir / FILES[0]))
        tokenizer.enable_truncation(MAX_TOKENS)
        session = ort.InferenceSession(str(model_dir / FILES[1]), providers=["CPUExecutionProvider"])
    except Exception as e:  # a missing library, a half-downloaded file: she goes on by words
        log.warning("meaning model not loaded (%s); finding memories by words only", e)
        return None
    wanted = [i.name for i in session.get_inputs()]

    def encode(text: str):
        enc = tokenizer.encode(text)
        feed = {"input_ids": np.array([enc.ids], dtype=np.int64),
                "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
                "token_type_ids": np.zeros((1, len(enc.ids)), dtype=np.int64)}
        first = session.run(None, {k: feed[k] for k in wanted})[0][0, 0]  # the [CLS] place
        return (first / np.linalg.norm(first)).tolist()

    return encode


def embedder(model_dir: Path | None) -> Embedder:
    """What the memory node finds with: by meaning too when the model is here, else by words."""
    encode = load(model_dir) if model_dir else None
    return Meaning(encode) if encode else BigramEmbedder()
