#!/usr/bin/env python3
"""Download the small Chinese sentence model she finds memories by meaning with (decision 58).

  .venv/bin/python scripts/get_meaning_model.py

Two files of BAAI's bge-small-zh-v1.5 (MIT licence; the ONNX build, about 24 MB) go next to
her database, in data/models/bge-small-zh/. Run once on the machine she lives on; she uses
them from her next start. Free, nothing is sent anywhere: the model runs on this machine.
Each file is checked against a fixed SHA-256, so a broken or swapped download is thrown away.
huggingface.co is tried first, then a mirror reachable from mainland China. Standard library
only. Without the files she finds memories by words, as before.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fish.config import load_settings  # noqa: E402

REPO = "Xenova/bge-small-zh-v1.5"
HOSTS = ("https://huggingface.co", "https://hf-mirror.com")
FILES = {  # name here -> (path in the repo, sha256)
    "tokenizer.json": ("tokenizer.json", "48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26"),
    "model_quantized.onnx": ("onnx/model_quantized.onnx",
                             "15b717c382bcb518ba457b93ea6850ede7f4f1cd8937454aa06972366cd19bcc"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(name: str, target: Path) -> bool:
    remote, want = FILES[name]
    if target.is_file() and sha256(target) == want:
        print(f"{name}：已经有了")
        return True
    part = target.with_suffix(target.suffix + ".part")
    for host in HOSTS:
        try:
            req = urllib.request.Request(f"{host}/{REPO}/resolve/main/{remote}", headers={"User-Agent": "fish"})
            with urllib.request.urlopen(req, timeout=60) as res, part.open("wb") as out:
                for block in iter(lambda: res.read(1 << 20), b""):
                    out.write(block)
        except OSError as e:
            print(f"{name}：{host} 下不动（{e}）")
            continue
        if sha256(part) == want:
            part.replace(target)
            print(f"{name}：下好了（{target.stat().st_size // 1024} KB）")
            return True
        print(f"{name}：{host} 给的文件对不上校验，扔掉")
    part.unlink(missing_ok=True)
    return False


def main() -> None:
    folder = load_settings().meaning_dir
    if folder is None:
        raise SystemExit(".env 里 FISH_MEANING 关着，不用下。")
    folder.mkdir(parents=True, exist_ok=True)
    if not all([fetch(name, folder / name) for name in FILES]):
        raise SystemExit("没下全。她照旧按字面找记忆；网络好了再跑一次。")
    print(f"在 {folder}。她下次启动就会按意思找记忆。")


if __name__ == "__main__":
    main()
