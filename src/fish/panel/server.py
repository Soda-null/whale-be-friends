"""The panel's little web server: on this computer only, and only for this page.

Any web page he visits could send requests to 127.0.0.1, so: the Host header must be this machine
(a site cannot rename itself to reach us), and every /api call needs the token that is written
into our page (another site cannot read that page). The page itself loads nothing from outside.
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fish.panel import parse
from fish.panel.box import PYTHON, Box, Result

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_WORDS = 200  # characters he can say in one go
MAX_BODY = 4096
IDLE_EXIT_SECONDS = 30 * 60  # nobody has had the page open for this long: go away
MODEL_TIMEOUT = 90
BACKUP_TIMEOUT = 180
BACKUP_NAME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})\d{2}$")
NEXT_TIME = re.compile(r"\d{4}-(\d{2}-\d{2}) (\d{2}:\d{2})")
PAGE = Path(__file__).with_name("page.html")
REPO = Path(__file__).resolve().parents[3]
IMAGES = Path(__file__).with_name("img")
IMAGE_PATH = re.compile(r"^/img/([a-z_]+\.webp)$")
CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
UNREACHABLE = "连不上她那台机器。电脑是不是不在能连到它的网络上？"


class Refused(Exception):
    """He sent something we will not pass on; the words are for him."""


class Panel:
    """What each button does. No state: every answer comes from the `fish` commands."""

    def __init__(self, box: Box) -> None:
        self.box = box

    def _text(self, result: Result) -> str:
        if not result.ok:
            raise ConnectionError(result.err or UNREACHABLE)
        return result.out

    def life(self, days: int) -> dict:
        data = parse.life(self._text(self.box.fish("life", str(days))))
        if self.box.box:
            check = self.box.here("scripts/backup_box.sh", "--check")
            data["alerts"] += [line.lstrip("！") for line in check.out.splitlines() if line.strip()]
        return data

    def me(self) -> list[dict]:
        return parse.me(self._text(self.box.fish("me")))

    def tell_doing(self, words: str) -> list[dict]:
        return parse.me(self._text(self.box.fish("me", _words(words))))

    def room(self, words: str) -> list[str]:
        """His plain words for her room; one model call. What happened, without the room listing after it."""
        result = self.box.fish("home", "-", stdin=_words(words), timeout=MODEL_TIMEOUT)
        if not result.ok:
            raise Refused(result.err.splitlines()[-1] if result.err else UNREACHABLE)
        return result.out.split("== ", 1)[0].strip().splitlines()

    def memories(self) -> dict:
        return parse.memories(self._text(self.box.fish("show")))

    def review(self, days: int) -> list[dict]:
        script = self.box.repo / "scripts" / "review.py"
        if not script.exists():
            raise Refused("复盘工具还没合进来")
        run = self.box.shell(f"{PYTHON} - {days}", stdin=script.read_text(encoding="utf-8"), timeout=60)
        return parse.plain_sections(self._text(run))

    def machine(self) -> dict:
        got = self.box.shell("systemctl --user is-active dafeiyu-wechat 2>/dev/null; "
                             "systemctl --user show dafeiyu-nightly.timer -p NextElapseUSecRealtime --value 2>/dev/null; "
                             "df -k . | tail -1")
        lines = self._text_any(got)
        disk = lines[-1].split() if lines else []
        data = {"online": lines[0] == "active" if lines else False,
                "next_night": _short_time(lines[1]) if len(lines) > 2 else "",
                "free_gb": round(int(disk[3]) / 1024 ** 2) if len(disk) > 3 and disk[3].isdigit() else None,
                "has_box": bool(self.box.box)}
        data.update(self._backups())
        return data

    @staticmethod
    def _text_any(result: Result) -> list[str]:
        """`is-active` exits non-zero when she is stopped, and that is an answer, not a failure."""
        if not result.out.strip():
            raise ConnectionError(result.err or UNREACHABLE)
        return [line.strip() for line in result.out.splitlines() if line.strip()]

    def _backups(self) -> dict:
        folder = self.box.repo / "backups" / "auto"
        names = sorted(p.name for p in folder.glob("20*")) if folder.is_dir() else []
        match = BACKUP_NAME.match(names[-1]) if names else None
        log = folder / "backup.log"
        return {"backups": len(names),
                "last_backup": f"{match[2]}-{match[3]} {match[4]}:{match[5]}" if match else "",
                "backup_log": log.read_text(encoding="utf-8").splitlines()[-1] if log.exists() and log.stat().st_size else ""}

    def backup(self) -> str:
        if not self.box.box:
            raise Refused("她就住在这台电脑上，这个按钮用不上")
        result = self.box.here("scripts/backup_box.sh", timeout=BACKUP_TIMEOUT)
        if not result.ok:
            raise Refused(result.err.splitlines()[-1] if result.err else "备份没成功")
        return result.out.strip()


def _short_time(text: str) -> str:
    """"Thu 2026-11-05 03:30:00 CST" -> "11-05 03:30"."""
    match = NEXT_TIME.search(text)
    return f"{match[1]} {match[2]}" if match else text


def _words(words: object) -> str:
    text = " ".join(str(words or "").split())
    if not text:
        raise Refused("还没写字呢")
    if len(text) > MAX_WORDS:
        raise Refused(f"太长了，{MAX_WORDS} 个字以内")
    return text


def _days(query: dict, default: int) -> int:
    value = query.get("days", [str(default)])[0]
    return min(max(int(value), 1), 90) if value.isdigit() else default


def make_server(box: Box, port: int = 0) -> ThreadingHTTPServer:
    panel = Panel(box)
    token = secrets.token_urlsafe(24)
    page = PAGE.read_text(encoding="utf-8").replace("__TOKEN__", token)

    class Handler(BaseHTTPRequestHandler):
        server_version = "fish-panel"
        sys_version = ""

        def log_message(self, *args) -> None:  # his activity stays out of any log
            pass

        def _send(self, status: int, body: bytes, kind: str, cache: str = "no-store") -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", CSP)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: object) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _from_here(self) -> bool:
            port_now = self.server.server_address[1]
            return self.headers.get("Host", "") in (f"{HOST}:{port_now}", f"localhost:{port_now}")

        def _allowed(self) -> bool:
            return hmac.compare_digest(self.headers.get("X-Panel-Token", "").encode(), token.encode())

        def _answer(self, work) -> None:
            try:
                self._json(200, {"ok": True, "data": work()})
            except Refused as e:
                self._json(200, {"ok": False, "error": str(e)})
            except ConnectionError as e:
                self._json(200, {"ok": False, "error": str(e) or UNREACHABLE, "unreachable": True})

        def do_GET(self) -> None:  # noqa: N802 - the name http.server calls
            if not self._from_here():
                return self._json(403, {"ok": False})
            url = urlparse(self.path)
            query = parse_qs(url.query)
            self.server.last_seen = time.monotonic()
            if url.path == "/":
                return self._send(200, page.encode(), "text/html; charset=utf-8")
            image = IMAGE_PATH.match(url.path)
            if image and (IMAGES / image[1]).is_file():  # the same pictures the public README shows
                return self._send(200, (IMAGES / image[1]).read_bytes(), "image/webp", "max-age=86400")
            if url.path == "/api/ping":  # no token: says only that this is the panel
                return self._json(200, {"app": "fish-panel"})
            if not self._allowed():
                return self._json(403, {"ok": False})
            routes = {"/api/life": lambda: panel.life(_days(query, 5)), "/api/me": panel.me,
                      "/api/memories": panel.memories, "/api/review": lambda: panel.review(_days(query, 7)),
                      "/api/machine": panel.machine,
                      "/api/features": lambda: {"review": (box.repo / "scripts" / "review.py").exists()}}
            if url.path not in routes:
                return self._json(404, {"ok": False})
            self._answer(routes[url.path])

        def do_POST(self) -> None:  # noqa: N802
            if not (self._from_here() and self._allowed()):
                return self._json(403, {"ok": False})
            self.server.last_seen = time.monotonic()
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._json(400, {"ok": False})
            if not 0 <= length <= MAX_BODY:
                return self._json(413, {"ok": False})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json(400, {"ok": False})
            words = body.get("words") if isinstance(body, dict) else None
            routes = {"/api/me": lambda: panel.tell_doing(words), "/api/room": lambda: panel.room(words),
                      "/api/backup": panel.backup}
            if self.path not in routes:
                return self._json(404, {"ok": False})
            self._answer(routes[self.path])

    server = ThreadingHTTPServer((HOST, port), Handler)
    server.daemon_threads = True
    server.last_seen = time.monotonic()
    return server


def _already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/ping", timeout=2) as reply:
            return json.load(reply).get("app") == "fish-panel"
    except (OSError, ValueError):
        return False


def _leave_when_idle(server: ThreadingHTTPServer) -> None:
    while time.monotonic() - server.last_seen < IDLE_EXIT_SECONDS:
        time.sleep(30)
    server.shutdown()


def run(port: int = DEFAULT_PORT, open_browser: bool = True, repo: Path = REPO) -> None:
    url = f"http://{HOST}:{port}/"
    if _already_running(port):
        if open_browser:
            webbrowser.open(url)
        return
    server = make_server(Box(repo), port)
    threading.Thread(target=_leave_when_idle, args=(server,), daemon=True).start()
    if open_browser:
        webbrowser.open(url)
    print(f"panel: {url}", flush=True)
    server.serve_forever()


__all__ = ["DEFAULT_PORT", "Panel", "Refused", "make_server", "run"]
