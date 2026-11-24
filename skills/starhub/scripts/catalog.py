import datetime as dt
import re
from collections import defaultdict

import library as lib
import notes
import taxonomy as tax

CLICKBAIT = re.compile(r"绝了|必看|建议收藏|干货|保姆级|天花板|yyds|码住|一定要看", re.I)
EMOJI = re.compile("[\U0001f000-\U0001faff\u2300-\u23ff\u25a0-\u27bf\ufe0e\ufe0f\u200d\u20e3\U000e0020-\U000e007f]")
HASHTAG = re.compile(r"#[^\s#，。！？、,!?]+#?")
DIVIDERS = str.maketrans({"｜": " ", "|": " ", "丨": " "})
LABEL_FIELDS = ("topic", "kind", "scene", "entities", "what", "when", "tool")


def clean_title(title):
    text = HASHTAG.sub(" ", title.translate(DIVIDERS))
    text = CLICKBAIT.sub("", EMOJI.sub("", text))
    return " ".join(text.split())


def excerpt(raw):
    cache = lib.cache_path(raw)
    if cache.exists():
        with cache.open(encoding="utf-8") as file:
            body = file.read(300).strip()
        if body:
            return body
    meta = raw["meta"]
    return str(meta.get("intro") or meta.get("desc") or "")[:300]


def labels():
    return {row["id"]: row for row in lib.jsonl(lib.HOME / "labels.jsonl")}


def project(raw, label):
    row = {**raw, "clean_title": clean_title(raw["title"]), "excerpt": excerpt(raw),
           "topic": tax.PENDING, "kind": "", "scene": "", "entities": [],
           "what": "", "when": "", "status": "new", "pinned": False}
    if raw["source"] == "github":
        row["tool"] = {}
    row.update({field: label[field] for field in LABEL_FIELDS if field in label})
    if label and (label.get("by") != "migration" or row["source"] == "github" and not row["topic"].startswith(tax.PENDING)):
        row["status"] = "ok"
    return row


def related_key(src, dst):
    return (*sorted((src, dst)), "related")


def curation_time(row):
    try:
        stamp = dt.datetime.fromisoformat(row.get("at", ""))
        return stamp.replace(tzinfo=stamp.tzinfo or dt.timezone.utc)
    except (TypeError, ValueError):
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def replay(rows, topics, edges):
    aliases = {}

    def resolve(key):
        while key in aliases:
            key = aliases[key]
        return key

    for event in sorted(lib.jsonl(lib.HOME / "curation.jsonl"), key=curation_time):
        op, key = event.get("op"), event.get("id", event.get("from", ""))
        target = resolve(event.get("to", ""))
        first = resolve(key)
        if op == "rename" and first in topics:
            name = event.get("name", event.get("to"))
            if tax.valid_name(name):
                topics[first]["name"] = name
        elif op == "merge" and first in topics and target in topics and first != tax.PENDING:
            if target == first or target.startswith(first + "/"):
                continue
            moved = {name for name in topics if name == first or name.startswith(first + "/")}
            aliases.update(dict.fromkeys(moved, target))
            for name in moved:
                del topics[name]
            for row in rows.values():
                if row["topic"] in moved:
                    row.update(topic=target, user_topic=True)
            for (src, dst, rel), by in list(edges.items()):
                if src not in moved and dst not in moved:
                    continue
                del edges[src, dst, rel]
                src, dst = resolve(src), resolve(dst)
                if src != dst:
                    link = related_key(src, dst) if rel == "related" else (src, dst, rel)
                    if edges.get(link) != "user":
                        edges[link] = by
        elif op == "split" and target in topics:
            for item in event.get("items", []):
                if item in rows:
                    rows[item].update(topic=target, user_topic=True)
        elif op == "move" and key in rows and target in topics:
            rows[key].update(topic=target, user_topic=True)
        elif op in ("pin", "hide", "unpin", "unhide") and key in rows:
            row = rows[key]
            if op in ("pin", "unpin"):
                row["pinned"] = op == "pin" and event.get("value", True)
            elif op == "hide" and event.get("value", True):
                row["status"] = "hidden"
            else:
                row["status"] = "ok" if row["kind"] or row["what"] else "new"
        elif op == "set" and key in rows:
            row, field, value = rows[key], event.get("field", ""), event.get("value")
            if field.startswith("tool.") and "tool" in row:
                row["tool"] = {**row["tool"], field[5:]: value}
            elif field in ("kind", "scene", "entities", "what", "when", "status"):
                row[field] = value
                if field == "entities":
                    row["user_entities"] = True
        elif op in ("relate", "unrelate"):
            src = resolve(event.get("src", key))
            dst = resolve(event.get("dst", target))
            if src != dst and src in rows.keys() | topics.keys() and dst in rows.keys() | topics.keys():
                if op == "relate":
                    edges[related_key(src, dst)] = "user"
                else:
                    edges.pop(related_key(src, dst), None)


def state():
    generated = tax.load()
    topics = {topic["id"]: {**topic} for topic in generated["topics"]}
    topics[tax.PENDING] = {"id": tax.PENDING, "name": tax.PENDING}
    classified = labels()
    rows = {key: project(raw, classified.get(key, {})) for key, raw in lib.raw_items().items()}
    for row in rows.values():
        key = row["topic"]
        if key.startswith(tax.PENDING + "/"):
            while key not in topics:
                parent, _, name = key.rpartition("/")
                topics[key] = {"id": key, "name": name, "parent": parent}
                key = parent
        elif key not in topics:
            row.update(topic=tax.PENDING, status="new")
    wiki = notes.load()
    edges, entities = {}, {}
    repos = {item.casefold(): item for item in rows if rows[item]["source"] == "github"}
    for key, note in wiki.items():
        if key not in topics:
            continue
        fields = note["fields"]
        for other in notes.inline_list(fields.get("related", "")) or []:
            if other in topics and other != key:
                edges[related_key(key, other)] = "ai"
        for tool in notes.inline_list(fields.get("tools", "")) or []:
            name = re.sub(r"^https?://github\.com/|^github:", "", tool, flags=re.I).rstrip("/")
            repo = f"github:{name}".removesuffix(".git")
            dst = repos.get(repo.casefold(), f"tool:{name}")
            edges[key, dst, "recommends_tool"] = "ai"
    replay(rows, topics, edges)
    groups = defaultdict(dict)
    for row in sorted(rows.values(), key=lambda row: (row["seen"], row["saved"], row["id"])):
        key, topic = row["id"], row["topic"]
        edges[key, topic, "in_topic"] = "user" if row.get("user_topic") else "ai" if key in classified else "source"
        for entity in row["entities"]:
            kind, _, name = entity.partition(":")
            entities[entity] = kind, name
            edges[key, entity, "mentions"] = "user" if row.get("user_entities") else "ai"
        if row["url"]:
            others = groups[row["url"]]
            previous = next((item for source, item in others.items() if source != row["source"]), None)
            if previous:
                edges[key, previous, "same_as"] = "source"
            others.setdefault(row["source"], key)
    return rows, topics, wiki, entities, edges
