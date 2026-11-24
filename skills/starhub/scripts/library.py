import datetime as dt
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

HOME = Path(os.environ.get("STARHUB_HOME") or Path.home() / ".starhub").expanduser().resolve()
LABELS = {"github": "GitHub", "xhs": "小红书", "bili": "B站"}
XHS_ACTIONS = ("收藏", "点赞")
SETUP_HINT = "还没有设置。运行：starhub setup"


class Error(Exception):
    pass


def today():
    return dt.date.today().isoformat()


def now(timespec="seconds"):
    return dt.datetime.now().astimezone().isoformat(timespec=timespec)


def state_path(name):
    return HOME / "state" / name


def vendor_path():
    return Path(os.environ.get("STARHUB_VENDOR") or state_path("vendor")).expanduser()


def date(value):
    try:
        return dt.date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return ""


def write(name, text):
    target = HOME / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=target.parent, delete=False) as file:
        tmp = Path(file.name)
        try:
            file.write(text)
            file.close()
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)


@contextmanager
def writing():
    path = state_path(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as file:
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
    path = state_path("config.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if required:
        raise Error(SETUP_HINT)
    return {"version": 2, "github": "", "sources": ["github"], "last_sync": ""}


def put_config(data):
    write(state_path("config.json"), json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def put_rows(name, rows):
    write(name, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def append_text(path, text):
    existing = path.read_bytes().decode("utf-8") if path.exists() else ""
    separator = "\n" if existing and not existing.endswith("\n") else ""
    write(path, existing + separator + text)


def wiki_log(op, title):
    append_text(HOME / "wiki/log.md", f"\n## [{today()}] {op} | {' '.join(title.split())}\n")


def raw_items():
    return {row["id"]: row for source in LABELS for row in jsonl(HOME / f"raw/{source}.jsonl")}


def raw_record(row):
    via = row.get("via", [])
    if isinstance(via, str):
        via = [via] if via else []
    via = xhs_actions(row) if row["source"] == "xhs" else list(dict.fromkeys(via))
    return {"id": row["id"], "source": row["source"], "via": via,
            **{field: row.get(field) or "" for field in ("url", "title", "author", "folder")},
            **{field: date(row.get(field)) for field in ("saved", "seen", "removed")},
            "meta": row.get("meta") or {}}


def xhs_actions(row):
    recorded = row.get("actions", row["via"])
    if isinstance(recorded, str):
        recorded = [recorded]
    return [action for action in XHS_ACTIONS if action in recorded]


def put_raw(rows, sources=LABELS):
    for source in sources:
        path = HOME / f"raw/{source}.jsonl"
        previous = {row["id"]: row for row in jsonl(path)}
        records = [raw_record(rows[key]) for key in sorted(rows) if rows[key]["source"] == source]
        changes = [row for row in records if row != previous.get(row["id"])]
        if changes:
            append_text(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in changes))


def cache_path(item):
    name = quote(item["id"].split(":", 1)[1], safe="")
    if re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name):
        name = f"%{ord(name[0]):02X}" + name[1:]
    return HOME / "raw" / "cache" / item["source"] / f"{name}.md"


def visible(row):
    return row["status"] != "hidden" and not row["removed"]


def event_time(row):
    try:
        stamp = dt.datetime.fromisoformat(row.get("at", ""))
        return stamp.astimezone()
    except (TypeError, ValueError):
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def curation():
    return sorted(jsonl(state_path("curation.jsonl")), key=event_time)


def append_curation(op, **values):
    event = {"at": now("microseconds"), "by": "user", "op": op, **values}
    append_text(state_path("curation.jsonl"), json.dumps(event, ensure_ascii=False) + "\n")


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
