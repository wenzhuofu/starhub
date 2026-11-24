import json
import os
from collections import Counter
from pathlib import Path

import catalog
import library as lib
import taxonomy as tax
import tools


def import_items(entries):
    rows = lib.raw_items()
    keys = {key.casefold() if row["source"] == "github" else key: key for key, row in rows.items()}
    labels = catalog.labels()
    curation_path = lib.HOME / "curation.jsonl"
    events = lib.jsonl(curation_path)
    hidden = {event.get("id") for event in events if event.get("op") in ("hide", "unhide")}
    changed, new_labels, new_events, added = set(), [], [], 0
    for entry in entries:
        source, key = entry["source"], entry["id"]
        identity = key.casefold() if source == "github" else key
        if identity not in keys:
            raw = lib.raw_record(entry)
            if entry.get("status") == "archived" and source == "github":
                raw["removed"] = raw["removed"] or raw["seen"] or lib.today()
            rows[key] = raw
            keys[identity] = key
            changed.add(source)
            added += 1
        key = keys[identity]
        topic = entry.get("topic", "")
        if key not in labels and (source == "github" or topic):
            fields = {name: entry.get(name, {} if name == "tool" else "") for name in ("what", "when", "tool")
                      if source == "github"}
            label = {"id": key, "topic": f"{tax.PENDING}/{topic}" if topic else tax.PENDING,
                     **fields, "by": "migration", "at": lib.today()}
            new_labels.append(label)
            labels[key] = label
        if entry.get("status") == "archived" and source != "github" and key not in hidden:
            new_events.append({"at": rows[key]["seen"] or lib.today(), "by": "user", "op": "hide", "id": key})
            hidden.add(key)
    lib.put_raw(rows, sorted(changed))
    if new_labels:
        path = lib.HOME / "labels.jsonl"
        lib.put_rows(path, [*lib.jsonl(path), *new_labels])
    if new_events:
        lib.put_rows(curation_path, [*events, *new_events])
    return added


def migrate_v2(_args):
    old, backup = lib.HOME / "items.jsonl", lib.HOME / "items.v1.jsonl"
    if not old.exists():
        print("v1 收藏已迁移。" if backup.exists() else "没有需要迁移的 v1 收藏。")
        return
    if backup.exists() and old.read_bytes() != backup.read_bytes():
        raise lib.Error("items.jsonl 和 items.v1.jsonl 内容不同，请先核对备份")
    added = import_items(lib.jsonl(old))
    lib.put_config({**lib.config(required=False), "version": 2})
    if backup.exists():
        old.unlink()
    else:
        os.replace(old, backup)
    print(f"已迁移 {added} 条，原文件已备份为 items.v1.jsonl")


def migrate_catalog(args):
    try:
        import tomllib
    except ImportError as exc:
        raise lib.Error("迁移需要 Python 3.11 或更高版本") from exc
    data = tomllib.loads(Path(args.catalog).read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    categories = meta.get("categories", {})
    cfg = lib.config(required=False)
    cfg["github"] = cfg["github"] or meta.get("github_user", "")
    entries = []
    for project in data.get("project", []):
        repo = project["repo"]
        status = project.get("status", "")
        category = project.get("category", "")
        date = str(project.get("added") or lib.today())
        excluded = {"repo", "added", "category", "summary", "when", "status"}
        tool = {name: value for name, value in project.items() if name not in excluded}
        if status in tools.LEVELS:
            tool["level"] = status
        entries.append(dict(id=f"github:{repo}", source="github", via="star", url=f"https://github.com/{repo}",
                            title=repo, author=repo.split("/", 1)[0], saved=date, seen=date,
                            what=project.get("summary", ""), when=project.get("when", ""),
                            topic=categories.get(category, category), status=status,
                            tool=json.loads(json.dumps(tool, default=str))))
    added = import_items(entries)
    if args.usage:
        path = lib.HOME / "usage.jsonl"
        usage = lib.jsonl(path)
        counts = Counter((row["date"], row["id"], row["note"]) for row in usage)
        for row in lib.jsonl(Path(args.usage)):
            record = row["date"], f"github:{row['repo']}", row["note"]
            if counts[record]:
                counts[record] -= 1
            else:
                usage.append({**{name: value for name, value in row.items() if name != "repo"}, "id": record[1]})
        lib.put_rows(path, usage)
    lib.put_config(cfg)
    print(f"已迁移 {added} 条")
