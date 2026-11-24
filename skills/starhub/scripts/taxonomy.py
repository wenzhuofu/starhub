import json
import re

import library as lib

PENDING = "待定"
KINDS = ("攻略", "清单", "教程", "观点", "资讯", "菜谱", "好物", "灵感", "工具")
ENTITY_TYPES = ("地点", "工具", "品牌", "人物", "作品", "概念")
DEFAULT = {"topics": [], "kinds": list(KINDS), "synonyms": {}}


def load():
    path = lib.state_path("taxonomy.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else DEFAULT


def save(data):
    lib.write(lib.state_path("taxonomy.json"), json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def valid_name(value):
    return (isinstance(value, str) and bool(value) and value == value.strip()
            and not re.search(r'[/\\<>:"|?*#\[\],\x00-\x1f]', value)
            and not value.endswith(".")
            and not re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", value))


def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get("topics"), list):
        raise lib.Error("词表须包含 topics 列表")
    topics, paths = {}, set()
    for number, topic in enumerate(data["topics"], 1):
        if not isinstance(topic, dict) or not isinstance(topic.get("id"), str):
            raise lib.Error(f"第 {number} 个主题缺少 id")
        key = topic["id"]
        segments = key.split("/")
        if not 1 <= len(segments) <= 3 or not all(map(valid_name, segments)):
            raise lib.Error(f"主题路径有误：{key}（最多三层）")
        if key.casefold() in paths or segments[0].casefold() in (PENDING, "index", "log", "insights"):
            raise lib.Error(f"主题重复或使用了保留路径：{key}")
        paths.add(key.casefold())
        parent = key.rpartition("/")[0]
        name = topic.get("name", segments[-1])
        if topic.get("parent", "") != parent or not valid_name(name):
            raise lib.Error(f"主题名称或 parent 有误：{key}")
        topics[key] = {"id": key, "name": name, **({"parent": parent} if parent else {})}
    for key, topic in topics.items():
        if "parent" in topic and topic["parent"] not in topics:
            raise lib.Error(f"找不到上级主题：{key}")
    kinds = data.get("kinds", list(KINDS))
    if not isinstance(kinds, list) or len(kinds) != len(KINDS) or any(kind not in kinds for kind in KINDS):
        raise lib.Error("类型为固定词表：" + "、".join(KINDS))
    synonyms = data.get("synonyms", {})
    if not isinstance(synonyms, dict):
        raise lib.Error("synonyms 须为对象")
    for key, words in synonyms.items():
        if not key.strip() or not isinstance(words, list) or any(not isinstance(w, str) or not w.strip() for w in words):
            raise lib.Error(f"同义词须为非空文本的列表：{key}")
    return {"topics": list(topics.values()), "kinds": list(KINDS), "synonyms": synonyms}


def add(key, parent=None):
    data = load()
    if parent and "/" not in key:
        key = f"{parent}/{key}"
    expected, _, name = key.rpartition("/")
    if not expected or (parent and parent != expected):
        raise lib.Error("新主题须挂在已有节点下，请提供完整路径或 --parent")
    data = {**data, "topics": [*data["topics"], {"id": key, "name": name, "parent": expected}]}
    save(validate(data))
    return key


def alternatives(term, synonyms):
    words = {term.casefold()}
    groups = [{word.strip().casefold() for word in (key, *values)} for key, values in synonyms.items()]
    while True:
        expanded = words.union(*(group for group in groups if words & group))
        if expanded == words:
            return sorted(words)
        words = expanded
