import datetime as dt
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

HOME = Path(os.environ.get("STARHUB_HOME") or Path.home() / ".starhub").expanduser().resolve()
VENDOR = Path(os.environ.get("STARHUB_VENDOR") or HOME / "vendor").expanduser()
LABELS = {"github": "GitHub", "xhs": "小红书", "bili": "B站"}
XHS_ACTIONS = ("收藏", "点赞")
SETUP_HINT = "还没有设置。运行：starhub setup"


class Error(Exception):
    pass


def today():
    return dt.date.today().isoformat()


def write(name, text):
    HOME.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=HOME, delete=False) as file:
        tmp = Path(file.name)
        try:
            file.write(text)
            file.close()
            os.replace(tmp, HOME / name)
        finally:
            tmp.unlink(missing_ok=True)


@contextmanager
def writing():
    HOME.mkdir(parents=True, exist_ok=True)
    with (HOME / ".lock").open("a+", encoding="utf-8") as file:
        try:
            if os.name == "nt":
                import msvcrt
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise Error("另一个 starhub 正在写入，请稍后重试") from exc
        yield


def config(required=True):
    path = HOME / "config.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if required:
        raise Error(SETUP_HINT)
    return {"version": 1, "github": "", "sources": ["github"], "last_sync": ""}


def put_config(data):
    write("config.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def put_rows(name, rows):
    write(name, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def items():
    return {row["id"]: row for row in jsonl(HOME / "items.jsonl")}


def xhs_actions(row):
    recorded = row.get("actions", (row["via"],))
    return [action for action in XHS_ACTIONS if action in recorded]


def put_items(rows):
    put_rows("items.jsonl", (rows[key] for key in sorted(rows)))


def lookup(q, rows):
    if q in rows:
        return rows[q]
    needle = q.casefold()
    exact, partial = [], []
    for row in rows.values():
        keys = (row["id"].casefold(), row["title"].casefold())
        if needle in keys:
            exact.append(row)
        elif any(needle in key for key in keys):
            partial.append(row)
    hits = exact or partial
    if len(hits) == 1:
        return hits[0]
    if hits:
        raise Error(f"“{q}”匹配到 {len(hits)} 条：" + "，".join(row["id"] for row in hits))
    raise Error(f"没有匹配“{q}”的收藏")


def run(exe, *args, **kwargs):
    command = [exe, *args]
    if os.name == "nt" and Path(exe).suffix.lower() in (".cmd", ".bat"):
        # Quote each argument before cmd processes metacharacters in note URLs.
        if any(re.search(r'["\r\n]', arg) for arg in command):
            raise Error("OpenCLI 参数含无效字符")
        quoted = " ".join(f'"{arg}"' for arg in command)
        kwargs["env"] = {**os.environ, "STARHUB_BATCH_COMMAND": quoted}
        command = [os.environ["ComSpec"], "/d", "/v:off", "/c", "%STARHUB_BATCH_COMMAND%"]
    return subprocess.run(command, encoding="utf-8", errors="replace", timeout=90,
                          capture_output=True, **kwargs)
