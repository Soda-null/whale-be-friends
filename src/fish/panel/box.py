"""Where she lives, and running one command there: over SSH when `.env` says BOX=, else on this
machine. Everything he types goes through `quote` or stdin, never straight into a shell."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

REMOTE_DIR = "Dafeiyu"
PYTHON = ".venv/bin/python"
TIMEOUT = 30  # seconds; a model call or a backup passes its own


@dataclass(frozen=True)
class Result:
    ok: bool
    out: str
    err: str = ""


def read_env(repo: Path) -> dict[str, str]:
    path = repo / ".env"
    if not path.exists():
        return {}
    pairs = (line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line)
    return {k.strip(): v.strip() for k, v in pairs if not k.lstrip().startswith("#")}


class Box:
    def __init__(self, repo: Path, box: str | None = None, tz: str | None = None) -> None:
        env = read_env(repo)
        self.repo = repo
        self.box = box if box is not None else env.get("BOX") or None
        self.tz = tz if tz is not None else env.get("TZ") or None

    def shell(self, command: str, *, stdin: str | None = None, timeout: int = TIMEOUT) -> Result:
        """`command` is run in her folder; the caller has quoted anything that came from him."""
        if self.tz:
            command = f"export TZ={shlex.quote(self.tz)}; {command}"  # every command in the line, not just the first
        if self.box:
            argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", self.box,
                    f"cd {REMOTE_DIR} && {command}"]
        else:
            argv = ["sh", "-c", command]
        return self._run(argv, stdin, timeout)

    def fish(self, *args: str, stdin: str | None = None, timeout: int = TIMEOUT) -> Result:
        words = " ".join(shlex.quote(a) for a in args)
        return self.shell(f"{PYTHON} -m fish {words}", stdin=stdin, timeout=timeout)

    def here(self, *argv: str, timeout: int = TIMEOUT) -> Result:
        """A script in this checkout, on this machine (the backup, which is the Mac's job)."""
        return self._run(list(argv), None, timeout)

    def _run(self, argv: list[str], stdin: str | None, timeout: int) -> Result:
        try:
            done = subprocess.run(argv, cwd=self.repo, input=stdin, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return Result(False, "", "等太久了，没等到回音")
        except OSError as e:
            return Result(False, "", str(e))
        return Result(done.returncode == 0, done.stdout, done.stderr.strip())
