import json
from collections import defaultdict
from pathlib import Path

import catalog
import index_db
import library as lib
import notes
import taxonomy as tax
from tools import LEVELS, repo_name

TEMPLATE = Path(__file__).resolve().parents[1] / "assets/page.html"
PAGE = "starhub.html"
INDEX = "tools/INDEX.md"
ITEM_KEYS = ("id", "source", "via", "url", "author", "folder", "saved", "seen", "topic", "kind", "scene", "status")
TOOL_KEYS = ("id", "url", "what", "when", "topic", "saved", "seen")


def page_data(state, conn):
    rows, topics, wiki, _, edges = state
    related = defaultdict(list)
    for src, dst, rel in sorted(edges):
        if rel == "related" and src in topics and dst in topics:
            related[src].append(dst)
            related[dst].append(src)
    data = {"generated": lib.now(), "last_sync": lib.config(required=False)["last_sync"],
            "topics": [], "items": [], "tools": []}
    for topic in conn.execute("SELECT * FROM topic ORDER BY id"):
        entry = dict(topic)
        key = entry["id"]
        entry.update(related=sorted(related[key]), note=wiki.get(key, {}).get("body", ""))
        data["topics"].append(entry)
    for _, row in sorted(rows.items(), key=lambda pair: (not pair[1]["pinned"], pair[0])):
        if not lib.visible(row):
            continue
        if row["source"] == "github":
            tool = row["tool"]
            entry = {key: row[key] for key in TOOL_KEYS}
            entry.update(title=repo_name(row), type=tool.get("type", ""),
                         level=tool.get("level", ""), conflicts=tool.get("conflicts", []))
            data["tools"].append(entry)
        else:
            entry = {key: row[key] for key in ITEM_KEYS}
            entry["title"] = row["clean_title"]
            data["items"].append(entry)
    return data


def write_page(state, conn):
    template = TEMPLATE.read_text(encoding="utf-8")
    marker = "/*STARHUB_DATA*/"
    if template.count(marker) != 1:
        raise lib.Error("网页模板缺少唯一的数据位置")
    raw = json.dumps(page_data(state, conn), ensure_ascii=False)
    escaped = raw.translate(str.maketrans({"<": r"\u003c", ">": r"\u003e", "&": r"\u0026"}))
    lib.write(PAGE, template.replace(marker, escaped))


def write_tools(state):
    rows, topics, _, _, edges = state
    groups = defaultdict(list)
    for row in rows.values():
        if row["source"] == "github" and lib.visible(row):
            groups[row["topic"]].append(row)
    lines = ["# starhub INDEX", "", "详情：`starhub show <仓库>`。", ""]
    order = {level: i for i, level in enumerate(LEVELS)}
    for topic, group in sorted(groups.items()):
        lines.append("## " + topics[topic]["name"])
        for row in sorted(group, key=lambda item: (not item["pinned"], order.get(item["tool"].get("level"), len(order)),
                                                    item["id"])):
            info = row["tool"]
            conflicts = ",".join(name.rsplit("/", 1)[-1] for name in info.get("conflicts", ()))
            suffix = f" ⚔{conflicts}" if conflicts else ""
            tag = f"[{info.get('type') or '?'}·{info.get('level') or '?'}]"
            lines.append(f"- {repo_name(row)} {tag} {row['what']} → {row['when']}{suffix}")
        lines.append("")
    pending = defaultdict(list)
    for src, dst, rel in sorted(edges):
        if rel == "recommends_tool" and (dst not in rows or lib.visible(rows[dst]) and not rows[dst]["what"]):
            pending[dst.partition(":")[2]].append(src)
    if pending:
        lines.extend(["## 笔记推荐 · 待分拣", ""])
        lines.extend(f"- {tool} ← {'、'.join(origins)}" for tool, origins in sorted(pending.items()))
        lines.append("")
    lib.write(INDEX, "\n".join(lines))


def write_wiki_index(conn):
    start, end = "<!-- starhub:topics -->", "<!-- /starhub:topics -->"
    lines = [start]
    for row in conn.execute("SELECT * FROM topic ORDER BY id"):
        slug = (row["note"] or notes.filename(row["id"])).removesuffix(".md")
        lines.append(f"{'  ' * row['id'].count('/')}- [[{slug}]] {row['name']} ({row['size']}) {row['summary']}".rstrip())
    block = "\n".join([*lines, end])
    path = lib.HOME / "wiki/index.md"
    old = path.read_text(encoding="utf-8") if path.exists() else "# starhub 主题索引\n"
    before, marker, rest = old.partition(start)
    if marker and end in rest:
        text = before + block + rest.partition(end)[2]
    else:
        text = old.rstrip() + "\n\n" + block + "\n"
    if text != old:
        lib.write("wiki/index.md", text)


def init_layout():
    if not (lib.HOME / "taxonomy.json").exists():
        tax.save(tax.DEFAULT)
    for name in ("labels.jsonl", "curation.jsonl"):
        if not (lib.HOME / name).exists():
            lib.write(name, "")


def rebuild():
    init_layout()
    state = catalog.state()
    index_db.write(state)
    with index_db.open_index() as conn:
        write_wiki_index(conn)
        write_page(state, conn)
    write_tools(state)
    return len(state[0]), len(state[1])
