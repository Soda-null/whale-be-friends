"""Only one of her on one WeChat (decision 52): a second one stops before it reaches the phone line."""

import os
import signal
import subprocess
import sys
import time

import pytest

import fish.__main__ as cli
from fish.channels import SecondHer, hold_the_line


def test_a_machine_that_only_looks_in_never_connects(tmp_path):
    """10-31: the Mac and the box each had their own data/, so no lock could have seen it."""
    with pytest.raises(SecondHer, match="她住在 thebox"):
        hold_the_line("thebox", tmp_path / "wechat.lock")
    assert not (tmp_path / "wechat.lock").exists()


def test_a_second_one_on_this_machine_is_refused_and_told_who_holds_it(tmp_path):
    lock = tmp_path / "data" / "wechat.lock"  # the folder may not be there yet
    first = hold_the_line("", lock)
    with pytest.raises(SecondHer) as e:
        hold_the_line("", lock)
    assert "已经有一条她" in str(e.value) and str(os.getpid()) in str(e.value)
    first.close()
    hold_the_line("", lock).close()  # she stopped: the next one starts


def test_a_crash_does_not_lock_her_out(tmp_path):
    """Restart=always must bring her back after a crash, with nobody tidying up a file."""
    lock = tmp_path / "wechat.lock"
    code = ("import os, sys, time; from pathlib import Path; from fish.channels import hold_the_line\n"
            "f = hold_the_line('', Path(sys.argv[1])); print(os.getpid(), flush=True); time.sleep(60)")
    other = subprocess.Popen([sys.executable, "-c", code, str(lock)], stdout=subprocess.PIPE, text=True)
    pid = 0
    try:
        # its own word for its pid: on Windows the venv's python.exe is a launcher, other.pid is that
        pid = int(other.stdout.readline())
        with pytest.raises(SecondHer, match=str(pid)):  # another process: the real case
            hold_the_line("", lock)
    finally:
        if pid:
            os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))  # no goodbye, no tidying up
        other.kill()
        other.wait()
    for _ in range(50):  # Windows lets go a moment after the process is gone
        try:
            hold_the_line("", lock).close()
            return
        except SecondHer:
            time.sleep(0.1)
    pytest.fail("still locked after the holder died")


@pytest.mark.parametrize("words", [["wechat"], ["wechat", "login"]])
def test_fish_wechat_stops_before_anything_connects(tmp_path, monkeypatch, words):
    def must_not_run(*a, **k):
        raise AssertionError("got as far as the phone line")

    monkeypatch.setenv("BOX", "thebox")
    monkeypatch.setenv("FISH_DB_PATH", str(tmp_path / "fish.db"))
    monkeypatch.setattr(cli, "WECHAT_STATE", tmp_path / "wechat.json")
    for name in ("ILinkClient", "login", "connect", "Brain"):
        monkeypatch.setattr(cli, name, must_not_run)
    with pytest.raises(SystemExit, match="她住在 thebox"):
        cli.main(words)
    assert not (tmp_path / "fish.db").exists()


def test_only_the_wechat_command_is_stopped(tmp_path, monkeypatch, capsys):
    """Looking at her from a machine that only looks in goes on working."""
    monkeypatch.setenv("BOX", "thebox")
    monkeypatch.setenv("FISH_DB_PATH", str(tmp_path / "fish.db"))
    cli.main(["me"])
    assert "你的状态" in capsys.readouterr().out
