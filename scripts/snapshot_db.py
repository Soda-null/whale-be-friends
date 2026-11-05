#!/usr/bin/env python3
"""A safe copy of her database while she is running, and a check that a copy opens (decision 53).

    snapshot_db.py <src> <dst>     copy with SQLite's own backup, then check it; dst appears only if good
    snapshot_db.py --check <file>  print how many messages it holds; exit 1 if it is damaged

Copying the file itself while she writes could catch it half written. Standard library only.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


def check(path: Path) -> int:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise sqlite3.DatabaseError(result)
        return conn.execute("SELECT count(*) FROM messages").fetchone()[0]
    finally:
        conn.close()


def snapshot(src: Path, dst: Path) -> int:
    partial = dst.with_name(dst.name + ".partial")
    partial.unlink(missing_ok=True)
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    target = sqlite3.connect(partial)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    count = check(partial)
    os.replace(partial, dst)
    return count


def main(args: list[str]) -> int:
    try:
        if len(args) == 2 and args[0] == "--check":
            print(check(Path(args[1])))
        elif len(args) == 2:
            print(snapshot(Path(args[0]), Path(args[1])))
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except sqlite3.Error as e:
        print(f"damaged or unreadable: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
