"""The panel: it reads what `fish` prints, passes on what he says safely, and answers nobody else."""

import http.client
import json
import shlex
import threading
from pathlib import Path

import pytest

from fish.panel import Box, make_server, parse
from fish.panel.box import Result

LIFE = """！还缺这几天的日记：2026-11-02（下一晚会补）
== 她现在（11-04 23:00）==
  冰箱里有吃的（够 6 顿）
  窗台上：一盆小葱
  心情：很困，不太想打字
  这阵子：最近有点蔫
== 今天 ==
  09:01 给小泡泡喂了鱼食
  12:00 吃了午饭
  在读 / 在追：某本老书
== 日记 ==
  2026-11-03  今天看湖
"""
SHOW = """== 底牌（每轮都带）==
  [#3] 他住在 Springfield
== 和他相处的方式 ==
  [#4] 别催他
== 长期条目（现行）==
  [#1] world   重要 3 R=0.48 模糊  自助餐不敢多拿  ← https://example.com/a
  [#2] event   重要12 R=0.91 钉住  第一行
第二行
  [#9] self    重要 4 R=0.05 想不起  <img src=x onerror=alert(1)>
== 惦记 ==
  [#5] 2026-11-05  问他考试
== 最近的聊天 ==
  2026-11-04 20:00  聊了面
== 日记 ==
  2026-11-03  今天看湖
== 当日心情 == 很困，和他熟了  (精力 21 无聊 0 饿 15)
== 这阵子 == 有点蔫  (基调 +0.07 一般，劲头 0.37 有点蔫；在意：换鱼缸)
== 底色 == 还是刚认识时的样子
== 关系 == {'days_known': 10, 'days_talked': 9, 'streak': 3}  亲近 28（熟了）
== 空闲（两周 24 段）== cottage 15，bilibili 7，something_new 2
"""


def test_life_comes_apart_into_what_the_page_draws():
    d = parse.life(LIFE)
    assert d["alerts"] == ["还缺这几天的日记：2026-11-02（下一晚会补）"]
    assert d["at"] == "11-04 23:00" and d["mood"] == "很困，不太想打字" and d["phase"] == "最近有点蔫"
    assert d["room"] == ["冰箱里有吃的（够 6 顿）", "窗台上：一盆小葱"]
    assert d["today"][0] == {"when": "09:01", "text": "给小泡泡喂了鱼食"} and len(d["today"]) == 2
    assert d["reading"] == "某本老书"
    assert d["diary"] == [{"when": "2026-11-03", "text": "今天看湖"}]


def test_a_quiet_day_is_empty_not_a_line_saying_so():
    d = parse.life("== 她现在（11-04 08:00）==\n  心情：平静\n== 今天 ==\n  还没什么事\n== 日记 ==\n    还没写过\n")
    assert d["today"] == [] and d["diary"] == []


def test_memories_come_apart_and_keep_their_line_breaks():
    d = parse.memories(SHOW)
    assert [m["state"] for m in d["memories"]] == ["模糊", "钉住", "想不起"]
    first, second, _ = d["memories"]
    assert first == {"kind": "见闻", "importance": 3, "state": "模糊", "text": "自助餐不敢多拿",
                     "source": "https://example.com/a"}
    assert second["text"] == "第一行\n第二行" and second["kind"] == "发生的事"
    assert d["profile"] == ["他住在 Springfield"] and d["howto"] == ["别催他"] and d["howto_title"] == "和他相处的方式"
    assert d["waiting"] == [{"when": "2026-11-05", "text": "问他考试"}]
    assert d["mood"] == "很困，和他熟了" and d["body"] == {"精力": 21, "无聊": 0, "饿": 15} and d["phase"] == "有点蔫"
    assert d["relationship"] == "认识 10 天，聊过 9 天，连着 3 天；亲近 28（熟了）"
    assert d["pastimes"] == "屋里的事 15，刷 B 站 7，something_new 2"


def test_real_commands_print_what_the_parser_expects(tmp_path, capsys):
    """If `fish life` or `fish show` change their headings, this fails rather than the page going blank."""
    from fish.__main__ import life, show
    from fish.config import Settings
    from fish.storage import connect

    conn = connect(tmp_path / "fish.db")
    settings = Settings(api_key="", base_url="", model="fake", db_path=tmp_path / "fish.db")
    life(conn, settings)
    d = parse.life(capsys.readouterr().out)
    assert d["at"] and d["mood"]
    show(conn)
    m = parse.memories(capsys.readouterr().out)
    assert m["mood"] and "亲近" in m["relationship"] and m["howto_title"]


class FakeBox(Box):
    """Records the shell lines it is asked for; answers from a table."""

    def __init__(self, repo: Path, *, box="testbox", answers=None):
        self.repo, self.box, self.tz = repo, box, None
        self.answers = answers if answers is not None else {}
        self.commands: list[tuple[str, str | None]] = []

    def shell(self, command, *, stdin=None, timeout=30):
        self.commands.append((command, stdin))
        for word, result in self.answers.items():
            if word in command:
                return result
        return Result(False, "", "ssh: connect to host testbox: timed out")

    def here(self, *argv, timeout=30):
        self.commands.append((" ".join(argv), None))
        return Result(True, "2026-11-04 备份好了\n" if len(argv) == 1 else "")


@pytest.fixture
def panel(tmp_path):
    fake = FakeBox(tmp_path, answers={
        "fish life": Result(True, LIFE), "fish show": Result(True, SHOW),
        "fish me": Result(True, "== 你的状态（她看到的就是这些）==\n  在哪：他不在\n  在干嘛：躺着\n"),
        "fish home": Result(True, "放好了两盒牛奶\n== 她的小屋（/home/x）==\n  冰箱满了\n"),
        "is-active": Result(True, "active\nThu 2026-11-05 03:30:00 CST\n/dev/x 100 50 15728640 80% /\n")})
    server = make_server(fake)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    def call(method, path, body=None, *, token=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        headers = {"Host": host or f"127.0.0.1:{port}"}
        if token:
            headers["X-Panel-Token"] = token
        conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
        reply = conn.getresponse()
        data = reply.read()
        conn.close()
        return reply, data

    page = call("GET", "/")[1].decode()
    token = page.split('const TOKEN = "')[1].split('"')[0]
    yield call, token, fake, server
    server.shutdown()


def test_it_listens_only_on_this_computer(panel):
    _, _, _, server = panel
    assert server.server_address[0] == "127.0.0.1"


def test_another_site_cannot_reach_it(panel):
    call, token, fake, _ = panel
    assert call("GET", "/api/life")[0].status == 403  # no token
    assert call("GET", "/api/life", token="wrong")[0].status == 403
    assert call("POST", "/api/room", {"words": "放炸弹"})[0].status == 403
    assert call("GET", "/", host="evil.example")[0].status == 403  # a site renaming itself to 127.0.0.1
    assert call("GET", "/api/life", token=token, host="evil.example:8765")[0].status == 403
    assert fake.commands == []


def test_the_page_loads_nothing_from_outside_and_has_no_html_from_data(panel):
    call, _, _, _ = panel
    reply, body = call("GET", "/")
    policy = reply.getheader("Content-Security-Policy")
    assert "default-src 'none'" in policy and "connect-src 'self'" in policy
    page = body.decode()
    assert "innerHTML" not in page and "https://" not in page and "http://" not in page.replace("http://www.w3.org", "")


def test_life_and_memories_arrive(panel):
    call, token, _, _ = panel
    life = json.loads(call("GET", "/api/life?days=7", token=token)[1])
    assert life["ok"] and life["data"]["mood"] == "很困，不太想打字"
    memories = json.loads(call("GET", "/api/memories", token=token)[1])
    assert memories["data"]["memories"][2]["text"] == "<img src=x onerror=alert(1)>"  # the page shows it as text


def test_what_he_types_cannot_become_a_command(panel):
    call, token, fake, _ = panel
    nasty = "躺着; rm -rf ~ $(whoami) `id` 'x"
    assert json.loads(call("POST", "/api/me", {"words": nasty}, token=token)[1])["ok"]
    command = next(c for c, _ in fake.commands if "fish me" in c)
    assert shlex.split(command)[-1] == nasty
    assert json.loads(call("POST", "/api/room", {"words": nasty}, token=token)[1])["ok"]
    command, stdin = next((c, s) for c, s in fake.commands if "fish home" in c)
    assert stdin == nasty and "rm" not in command


def test_room_says_what_happened_without_the_whole_room(panel):
    call, token, _, _ = panel
    reply = json.loads(call("POST", "/api/room", {"words": "放两盒牛奶"}, token=token)[1])
    assert reply["data"] == ["放好了两盒牛奶"]


def test_empty_or_long_words_stop_here(panel):
    call, token, fake, _ = panel
    assert "还没写字" in json.loads(call("POST", "/api/me", {"words": "   "}, token=token)[1])["error"]
    assert "太长了" in json.loads(call("POST", "/api/me", {"words": "长" * 201}, token=token)[1])["error"]
    assert call("POST", "/api/me", {"words": "长" * 5000}, token=token)[0].status == 413
    assert fake.commands == []


def test_days_are_numbers_and_bounded(panel):
    call, token, fake, _ = panel
    call("GET", "/api/life?days=;reboot", token=token)
    call("GET", "/api/life?days=99999", token=token)
    lives = [c for c, _ in fake.commands if "fish life" in c]
    assert lives[0].endswith("life 5") and lives[1].endswith("life 90")


def test_a_box_it_cannot_reach_is_said_plainly(tmp_path):
    fake = FakeBox(tmp_path, answers={})
    server = make_server(fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/")
    token = conn.getresponse().read().decode().split('const TOKEN = "')[1].split('"')[0]
    conn.request("GET", "/api/me", headers={"X-Panel-Token": token})
    reply = json.loads(conn.getresponse().read())
    conn.close()
    server.shutdown()
    assert reply["ok"] is False and reply["unreachable"] is True


def test_machine_page_reads_service_and_disk(panel):
    call, token, _, _ = panel
    data = json.loads(call("GET", "/api/machine", token=token)[1])["data"]
    assert data["online"] is True and data["free_gb"] == 15 and data["next_night"] == "11-05 03:30"
    assert data["backups"] == 0 and data["has_box"] is True


def test_review_is_only_offered_once_the_script_is_here(panel, tmp_path):
    call, token, fake, _ = panel
    assert json.loads(call("GET", "/api/features", token=token)[1])["data"] == {"review": False}
    assert "还没合进来" in json.loads(call("GET", "/api/review", token=token)[1])["error"]
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "review.py").write_text("print('hi')")
    fake.answers["python - 7"] = Result(True, "== 这周 ==\n  说了 10 句\n")
    assert json.loads(call("GET", "/api/review", token=token)[1])["data"][0]["lines"] == ["说了 10 句"]


def test_real_shell_keeps_his_words_whole(tmp_path):
    """No pretending: a real `sh`, and the words come out the other side untouched."""
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    shim = tmp_path / ".venv" / "bin" / "python"
    shim.write_text('#!/bin/sh\nprintf "%s" "$4"\n')
    shim.chmod(0o755)
    box = Box(tmp_path, box="", tz="Asia/Shanghai")
    nasty = "躺着; touch hacked $(touch hacked2) 'x\""
    assert box.fish("me", nasty).out == nasty
    assert box.shell("true; echo $TZ").out.strip() == "Asia/Shanghai"  # for every command in the line
    assert not (tmp_path / "hacked").exists() and not (tmp_path / "hacked2").exists()
