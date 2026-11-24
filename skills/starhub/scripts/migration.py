import json
import os
from collections import Counter
from pathlib import Path

import catalog
import library as lib
import notes
import taxonomy as tax
import tools

LEGACY_STATE = ("config.json", "usage.jsonl", "vendor", "labels.jsonl", "taxonomy.json", "curation.jsonl",
                "items.v1.jsonl")


def needs_migration():
    return any((lib.HOME / name).exists() for name in ("items.jsonl", "cache", *LEGACY_STATE))


def relocate_legacy():
    pairs = [(lib.HOME / name, lib.state_path(name)) for name in LEGACY_STATE]
    pairs.append((lib.HOME / "cache", lib.HOME / "raw/cache"))
    existing = [(old, new) for old, new in pairs if old.exists()]
    for old, new in existing:
        if not all(path.resolve().is_relative_to(lib.HOME) for path in (old, new)):
            raise lib.Error(f"迁移路径超出收藏库：{old.name}")
        empty_directory = old.is_dir() and new.is_dir() and not any(new.iterdir())
        if new.exists() and not empty_directory:
            raise lib.Error(f"新旧路径都有数据，请先核对：{new.relative_to(lib.HOME)}")
    for old, new in existing:
        new.parent.mkdir(parents=True, exist_ok=True)
        if new.is_dir():
            new.rmdir()
        os.replace(old, new)
    return len(existing)


def relocate_round_one_notes():
    wiki = lib.HOME / "wiki"
    for path in wiki.glob("*%2F*.md"):
        fields, _, _ = notes.split(path.read_text(encoding="utf-8"))
        topic = fields.get("topic", "")
        parts = topic.split("/")
        if (len(parts) < 2 or path.stem != topic.replace("/", "%2F")
                or not all(map(tax.valid_name, parts))
                or parts[0].casefold() in ("index", "log", "insights")):
            continue
        target = wiki / notes.filename(topic)
        if target.exists() or not target.resolve().is_relative_to(wiki.resolve()):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(path, target)

def import_items(entries):
    rows = lib.raw_items()
    keys = {key.casefold() if row["source"] == "github" else key: key for key, row in rows.items()}
    labels = catalog.labels()
    curation_path = lib.state_path("curation.jsonl")
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
        path = lib.state_path("labels.jsonl")
        lib.put_rows(path, [*lib.jsonl(path), *new_labels])
    if new_events:
        lib.put_rows(curation_path, [*events, *new_events])
    return added


def migrate_v2(_args):
    moved = relocate_legacy()
    if moved:
        relocate_round_one_notes()
    old, backup = lib.HOME / "items.jsonl", lib.state_path("items.v1.jsonl")
    if old.exists() or moved:
        lib.put_config({**lib.config(required=False), "version": 2})
    if not old.exists():
        print("已迁移收藏库目录。" if moved else "v1 收藏已迁移。" if backup.exists() else "没有需要迁移的 v1 收藏。")
        return
    if backup.exists() and old.read_bytes() != backup.read_bytes():
        raise lib.Error("items.jsonl 和 items.v1.jsonl 内容不同，请先核对备份")
    added = import_items(lib.jsonl(old))
    if backup.exists():
        old.unlink()
    else:
        os.replace(old, backup)
    print(f"已迁移 {added} 条，原文件已备份为 state/items.v1.jsonl")


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
        path = lib.state_path("usage.jsonl")
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
