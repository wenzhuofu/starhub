import json
import sys
from collections import defaultdict
from pathlib import Path

import catalog
import library as lib
import notes
import queries
import taxonomy as tax
import views


def read_file(name):
    return sys.stdin.read().removeprefix("\ufeff") if name == "-" else Path(name).read_text(encoding="utf-8-sig")


def input_rows(text):
    if text.lstrip().startswith("["):
        try:
            yield from enumerate(json.loads(text), 1)
        except ValueError as exc:
            raise lib.Error(f"JSON 数组第 {exc.lineno} 行格式有误") from exc
        return
    for number, line in enumerate(text.split("\n"), 1):
        if line.strip():
            try:
                yield number, json.loads(line)
            except ValueError:
                yield number, None


def validate_entities(values):
    if not isinstance(values, list) or len(values) > 3:
        return False
    for entity in values:
        if not isinstance(entity, str):
            return False
        kind, _, name = entity.partition(":")
        if kind not in tax.ENTITY_TYPES or not name.strip() or any(c in name for c in ":\r\n"):
            return False
    return True


def validate_label(entry, rows, topics):
    if not isinstance(entry, dict):
        return ["须为 JSON 对象"]
    key = entry.get("id")
    if not isinstance(key, str) or key not in rows:
        return ["id 找不到对应收藏"]
    errors = []
    topic = entry.get("topic")
    if not isinstance(topic, str) or topic not in topics:
        errors.append("topic 须在词表里或为 待定")
    tool_fields = ("what", "when", "tool")
    has_tool = any(name in entry for name in tool_fields)
    if has_tool:
        if rows[key]["source"] != "github":
            errors.append("what、when、tool 只用于 GitHub 收藏")
        for field, size in (("what", 60), ("when", 40)):
            value = entry.get(field)
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= size:
                errors.append(f"{field} 须为 1–{size} 字")
        tool = entry.get("tool")
        if not isinstance(tool, dict):
            errors.append("tool 须为对象")
        else:
            for field in ("skills", "conflicts"):
                if field in tool and (not isinstance(tool[field], list) or
                                      any(not isinstance(item, str) for item in tool[field])):
                    errors.append(f"tool.{field} 须为字符串列表")
            for field in ("type", "level", "ref", "notes", "host", "setup", "needs"):
                if field in tool and not isinstance(tool[field], str):
                    errors.append(f"tool.{field} 须为字符串")
    if not has_tool or any(name in entry for name in ("kind", "scene", "entities")):
        if entry.get("kind") not in tax.KINDS:
            errors.append("kind 须为固定类型")
        if not validate_entities(entry.get("entities")):
            errors.append("entities 须为最多 3 个「类型:名字」")
        value = entry.get("scene")
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 20 or len(value.strip().splitlines()) != 1:
            errors.append("scene 须为一行 1–20 字")
    return errors


def label(args, state):
    rows = state[0]
    topics = {topic["id"] for topic in tax.load()["topics"] if topic["id"] in state[1]} | {tax.PENDING}
    previous = catalog.labels()
    accepted, rejected = [], []
    for number, entry in input_rows(read_file(args.file)):
        errors = validate_label(entry, rows, topics)
        if errors:
            key = queries.snippet(str(entry.get("id", "")), 120) if isinstance(entry, dict) else ""
            rejected.append(f"第 {number} 条 {key}：" + "；".join(errors))
            continue
        fields = {name: entry[name].strip() if isinstance(entry[name], str) else entry[name]
                  for name in catalog.LABEL_FIELDS if name in entry}
        key = entry["id"]
        tool = {field: previous.get(key, {})[field] for field in ("what", "when", "tool")
                if field in previous.get(key, {})}
        record = {"id": key, **tool, **fields, "by": "ai", "at": lib.now("microseconds")}
        accepted.append(record)
        previous[key] = record
    if accepted:
        path = lib.state_path("labels.jsonl")
        lib.append_text(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in accepted))
    lib.wiki_log("label", f"归类 {len(accepted)} 条，拒收 {len(rejected)} 条")
    print(f"已归类 {len(accepted)} 条，拒收 {len(rejected)} 条")
    for message in rejected:
        print(message)
    if accepted:
        views.rebuild()
    return int(bool(rejected))


def taxonomy(args, state=None):
    if args.action == "apply":
        data = tax.validate(json.loads(read_file(args.file)))
        tax.save(data)
        lib.wiki_log("taxonomy apply", f"保存 {len(data['topics'])} 个主题")
        print(f"已保存 {len(data['topics'])} 个主题")
    elif args.action == "add":
        key = tax.add(args.id, args.parent)
        print(f"已新增主题：{key}")
    else:
        rows = [row for row in state[0].values() if lib.visible(row)]
        groups = defaultdict(list)
        for row in rows:
            groups[row["source"], row["folder"]].append(row)
        for (source, folder), items in sorted(groups.items()):
            print(f"## {lib.LABELS[source]} · {queries.snippet(folder, 80) or '未分收藏夹'}")
            for row in sorted(items, key=lambda row: row["id"]):
                print(queries.l0(row))


def classify(args, state):
    data = tax.load()
    print("# 词表")
    names = [topic for topic in data["topics"] if topic["id"] in state[1]]
    shown = [key if key.rsplit("/", 1)[-1] == state[1][key]["name"] else f"{key}（{state[1][key]['name']}）"
             for key in (topic["id"] for topic in names)]
    print("主题：" + "、".join([tax.PENDING, *shown]))
    print("类型：" + "、".join(tax.KINDS))
    print("实体类型：" + "、".join(tax.ENTITY_TYPES))
    rows = (row for row in state[0].values() if (row["status"] == "new" or args.pending and row["topic"] == tax.PENDING)
            and lib.visible(row)
            and (not args.source or row["source"] == args.source))
    newest = sorted(rows, key=lambda row: (row.get("needs_relabel", False), row["saved"], row["seen"], row["id"]),
                    reverse=True)
    lib.wiki_log("classify", f"本批 {min(len(newest), args.limit)} 条，待归类 {len(newest)} 条")
    print(f"\n# 待归类（{len(newest)}）")
    for row in newest[:args.limit]:
        print(queries.l0(row))


def compile_topic(args, state):
    rows, topics, wiki, _, _ = state
    if args.id and args.id not in topics:
        raise lib.Error(f"找不到主题：{args.id}")
    groups = notes.member_groups(rows)
    dirty = []
    for key in ([args.id] if args.id else sorted(topics)):
        group = groups[key]
        note = wiki.get(key, {})
        if note.get("owner") == "user":
            continue
        previous = note.get("snapshot", {}) if note.get("file") else {}
        current = notes.snapshot(group)
        is_pending = key == tax.PENDING or key.startswith(tax.PENDING + "/")
        if (args.id or not is_pending) and previous != current:
            dirty.append((key, group, previous, current))
    if not dirty:
        lib.wiki_log("compile", "0 个主题待编译")
        print("没有待编译的主题。")
        return
    key, group, previous, current = dirty[0]
    changed = [row for row in group if previous.get(row["id"]) != current[row["id"]]]
    gone = sorted(previous.keys() - current.keys())
    lib.wiki_log("compile", f"{key}（新增或更新 {len(changed)} 条，移出 {len(gone)} 条）")
    print(f"# {key} · 新增或更新 {len(changed)} 条，移出 {len(gone)} 条")
    if len(dirty) > 1:
        print(f"另有 {len(dirty) - 1} 个主题待编译")
    body = wiki.get(key, {}).get("body", "")
    if body:
        print("\n## 现有笔记\n" + body[:queries.NOTE_LIMIT].rstrip())

    end = args.offset + args.limit
    if gone[args.offset:end]:
        print("\n## 已移出\n" + "\n".join(queries.snippet(item, 120) for item in gone[args.offset:end]))
    if args.limit and end < max(len(changed), len(gone)):
        print(f"\n下一批：starhub compile {key} --offset {end} --limit {args.limit}")

    def order(row):
        return row["pinned"], bool(row["excerpt"]), row["saved"], row["id"]

    for title, batch, depth in (("新增或更新", sorted(changed, key=order, reverse=True)[args.offset:end], 1),
                                ("代表作", sorted(group, key=order, reverse=True)[:5], 2)):
        if batch:
            print(f"\n## {title}")
        for row in batch:
            print(queries.display(row, depth, " ".join(row["entities"])))
            print("  " + queries.snippet(row["url"], 350))


def note(args, state):
    rows, topics, _, _, _ = state
    if args.id not in topics:
        raise lib.Error(f"找不到主题：{args.id}")
    fields, body, errors = notes.validate(read_file(args.file), args.id, topics)
    existing = notes.load(lib.curation()).get(args.id, {})
    if existing.get("owner") == "user":
        print(f"拒收：{args.id} 由用户维护。确认交还后请运行 starhub release {args.id}。")
        views.rebuild()
        return 1
    if errors:
        for message in errors:
            print("拒收：" + message)
        return 1
    snapshot = notes.snapshot(notes.member_groups(rows)[args.id])
    notes.save(args.id, fields, body, snapshot)
    lib.wiki_log("note", f"{args.id}（{fields['sources']} 条出处）")
    print(f"已保存主题笔记：{args.id}")
