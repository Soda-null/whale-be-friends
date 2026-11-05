"""The backup script end to end, with a pretend box: `ssh` runs locally, `rsync` loses the host name."""

import os
import shutil
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "scripts" / "snapshot_db.py"
pytestmark = pytest.mark.skipif(os.name == "nt" or shutil.which("rsync") is None, reason="sh and rsync")


def database(path: Path, messages: int) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, text TEXT)")
    conn.execute("DELETE FROM messages")
    conn.executemany("INSERT INTO messages (text) VALUES (?)", [("x",)] * messages)
    conn.commit()
    conn.close()


def tool(folder: Path, name: str, body: str) -> None:
    path = folder / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def world(tmp_path):
    """A box's home with her in it, and a PATH where ssh and rsync reach it."""
    home = tmp_path / "box"
    her = home / "Dafeiyu"
    (her / "data" / "cottage").mkdir(parents=True)
    (her / "scripts").mkdir()
    (her / ".venv" / "bin").mkdir(parents=True)
    (her / ".venv" / "bin" / "python").symlink_to(sys.executable)
    shutil.copy(SNAPSHOT, her / "scripts")
    database(her / "data" / "fish.db", 5)
    (her / "data" / "wechat.lock").write_text("123")
    (her / "data" / "cottage" / "now.json").write_text("{}")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    real_rsync = shutil.which("rsync")
    tool(bin_dir, "ssh", f'while [ "$1" = -o ]; do shift 2; done; shift; cd "{home}" && exec sh -c "$1"\n')
    tool(bin_dir, "rsync", f'''for a in "$@"; do
  case "$a" in testbox:*) a="{home}/${{a#testbox:}}" ;; esac
  set -- "$@" "$a"; shift
done
exec "{real_rsync}" "$@"
''')
    dest = tmp_path / "backups"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "BOX": "testbox", "FISH_BACKUP_DIR": str(dest),
           "FISH_BACKUP_KEEP": "3"}

    def run(*args):
        return subprocess.run(["sh", str(ROOT / "scripts" / "backup_box.sh"), *args], env=env, encoding="utf-8", errors="replace",
                              capture_output=True)
    return run, her, dest


def backups(dest: Path) -> list[Path]:
    return sorted(dest.glob("20*"))


def count(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT count(*) FROM messages").fetchone()[0]
    finally:
        conn.close()


def test_a_backup_holds_all_of_her_and_leaves_no_litter(world):
    run, her, dest = world
    done = run()
    assert done.returncode == 0, done.stderr
    copy = backups(dest)[0]
    assert count(copy / "fish.db") == 5
    assert (copy / "cottage" / "now.json").exists()
    assert not (copy / "wechat.lock").exists()
    assert not list(dest.glob(".partial*"))
    assert not (her / "data" / ".snapshot-fish.db").exists()


def test_auto_skips_when_fresh_and_check_only_speaks_when_stale(world):
    run, _, dest = world
    assert "还没有自动备份" in run("--check").stdout
    assert run().returncode == 0
    assert run("--check").stdout == ""
    assert run("--auto").returncode == 0
    assert len(backups(dest)) == 1
    os.utime(backups(dest)[0] / ".done", (1, 1))
    assert "超过 3 天" in run("--check").stdout
    assert run("--auto").returncode == 0
    assert len(backups(dest)) == 2


def only_the_newest_stay(run, dest, n):
    for i in range(n):
        assert run().returncode == 0
        import time
        time.sleep(1.01)  # the folder's name has seconds in it


def test_only_the_newest_are_kept_and_nothing_else_is_touched(world):
    run, _, dest = world
    dest.mkdir()
    (dest / "backup.log").write_text("log")
    (dest / "keep-me").mkdir()
    only_the_newest_stay(run, dest, 4)
    assert len(backups(dest)) == 3
    assert (dest / "backup.log").exists() and (dest / "keep-me").exists()
    assert all(count(b / "fish.db") == 5 for b in backups(dest))


def test_when_she_has_lost_messages_no_old_copy_is_deleted(world):
    run, her, dest = world
    only_the_newest_stay(run, dest, 3)
    database(her / "data" / "fish.db", 2)
    done = run()
    assert done.returncode == 1
    assert "比上一份少了" in done.stderr
    assert len(backups(dest)) == 4
    assert count(backups(dest)[0] / "fish.db") == 5


def test_a_damaged_database_is_not_kept_as_a_backup(world):
    run, her, dest = world
    assert run().returncode == 0
    (her / "data" / "fish.db").write_bytes(b"not a database at all" * 200)
    assert run().returncode != 0
    assert len(backups(dest)) == 1
    assert not list(dest.glob(".partial*"))


def test_snapshot_keeps_the_old_copy_if_the_source_is_damaged(tmp_path):
    good, bad, dst = tmp_path / "good.db", tmp_path / "bad.db", tmp_path / "copy.db"
    database(good, 2)
    bad.write_bytes(b"junk" * 2000)
    assert subprocess.run([sys.executable, str(SNAPSHOT), str(good), str(dst)]).returncode == 0
    assert subprocess.run([sys.executable, str(SNAPSHOT), str(bad), str(dst)], capture_output=True).returncode == 1
    assert count(dst) == 2
