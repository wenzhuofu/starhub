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
INDEX_START, INDEX_END = "<!-- starhub:topics -->", "<!-- /starhub:topics -->"
AGENTS_START, AGENTS_END = "<!-- starhub:begin -->", "<!-- starhub:end -->"
ITEM_KEYS = ("id", "source", "via", "url", "author", "folder", "saved", "seen", "topic", "kind", "scene", "status")
TOOL_KEYS = ("id", "url", "what", "when", "topic", "saved", "seen")


def page_data(state, conn):
    rows, topics, wiki, _, edges = state
    groups = notes.member_groups(rows)
    related = defaultdict(list)
    for src, dst, rel in sorted(edges):
        if rel == "related" and src in topics and dst in topics:
            related[src].append(dst)
            related[dst].append(src)
    data = {"generated": lib.now(), "last_sync": lib.config(required=False)["last_sync"],
            "wiki_dir": str((lib.HOME / "wiki").resolve()),
            "topics": [], "items": [], "tools": []}
    for topic in conn.execute("SELECT * FROM topic ORDER BY id"):
        entry = dict(topic)
        key = entry["id"]
        entry.update(related=sorted(related[key]), note=wiki.get(key, {}).get("body", ""),
                     coverage=notes.coverage(groups[key]))
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


def managed_block(path, start, end, lines, initial):
    block = "\n".join([start, *lines, end])
    old = path.read_bytes().decode("utf-8") if path.exists() else initial
    before, marker, rest = old.partition(start)
    if marker and end in rest:
        text = before + block + rest.partition(end)[2]
    elif marker or end in old:
        raise lib.Error(f"{path.name} 的生成区缺少成对标记，请修复标记后重试")
    else:
        separator = "\n" if old.endswith("\n") else "\n\n" if old else ""
        text = old + separator + block + "\n"
    if text != old or not path.exists():
        lib.write(path, text)


def write_wiki_index(conn):
    lines, previous = [], None
    tree = list(conn.execute("SELECT * FROM topic ORDER BY replace(id, '/', char(1))"))
    names = {row["id"]: row["name"] for row in tree}
    for row in tree:
        if not row["note"]:
            continue
        root = row["id"].partition("/")[0]
        if root != previous:
            lines.extend(["", "## " + names[root], ""])
            previous = root
        slug = row["note"].removesuffix(".md")
        summary, updated = " ".join(row["summary"].split()) or "—", row["updated"] or "—"
        lines.append(f"- [[{slug}|{row['name']}]] — {summary}（{row['size']} 条，{updated}）")
    managed_block(lib.HOME / "wiki/index.md", INDEX_START, INDEX_END, lines, "# starhub 主题目录\n")


def write_agents(topics):
    reference = TEMPLATE.parent.parent / "references/compile.md"
    rules = reference.read_text(encoding="utf-8").split("## 怎么写\n", 1)[1]
    rules = rules.split("\n## 两个风格示例", 1)[0].strip()
    active = {topic["id"] for topic in tax.load()["topics"]} | {tax.PENDING}
    lines = ["", "## 目录约定", "",
             "- wiki/index.md 是主题目录，wiki/log.md 是入库日志。",
             "- 主题笔记放在 wiki/<主题路径>.md，主题之间使用 Wikilink。",
             "- wiki/insights/ 由用户维护。raw/ 保存平台事实，state/ 保存程序状态。",
             "", "## 主题树", ""]
    for key in sorted(topics.keys() & active, key=lambda key: key.replace("/", "\x01")):
        lines.append(f"{'  ' * key.count('/')}- {key}（{topics[key]['name']}）")
    lines.extend(["", "## 写法要求", "", rules, ""])
    managed_block(lib.HOME / "AGENTS.md", AGENTS_START, AGENTS_END, lines, "# starhub 知识库\n")


def init_layout():
    if not lib.state_path("taxonomy.json").exists():
        tax.save(tax.DEFAULT)
    for name, text in (("labels.jsonl", ""), ("curation.jsonl", ""), ("notes.json", "{}\n"), ("usage.jsonl", "")):
        path = lib.state_path(name)
        if not path.exists():
            lib.write(path, text)
    for name in ("wiki/insights", "raw/cache", "state/vendor"):
        (lib.HOME / name).mkdir(parents=True, exist_ok=True)
    for name, text in (("CLAUDE.md", "见 AGENTS.md\n"), ("wiki/log.md", "# starhub 日志\n"),
                       (".obsidian/app.json", '{"userIgnoreFilters": ["state/"]}\n')):
        if not (lib.HOME / name).exists():
            lib.write(name, text)


def rebuild():
    init_layout()
    state = catalog.state()
    write_agents(state[1])
    index_db.write(state)
    with index_db.open_index() as conn:
        write_wiki_index(conn)
        write_page(state, conn)
    write_tools(state)
    return len(state[0]), len(state[1])
