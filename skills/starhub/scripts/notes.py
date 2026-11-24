import hashlib
import json
import re
from collections import defaultdict

import library as lib
import taxonomy as tax

INPUT_FIELDS = ("topic", "summary", "related", "tools")
FIELDS = ("topic", "summary", "updated", "sources", "coverage", "related", "tools")
BANNED = ("现有摘录", "仅凭标题", "无法证明", "无法确认", "本笔记", "当前资料",
          "提供主题与场景入口", "补充比较角度", "提供复盘线索", "值得一看")
CITATION = re.compile(r"(?<!\[)\[([0-9]+)\](?!\(|\])")
TABLE_RULE = re.compile(r":?-{3,}:?")
SOURCE = re.compile(r"([1-9]\d*)\.\s+\[(.+)\]\((https?://\S+)\)\s+—\s+(.+)")
SOURCE_METADATA = re.compile(r"(?:" + "|".join(lib.LABELS.values()) + r")\s*·\s*\d{4}-\d{2}\s*·")
LINK = re.compile(r"\[\[([^\]|\n]+)(?:\|([^\]\n]+))?\]\]")


def filename(topic):
    return topic + ".md"


def pages():
    wiki = lib.HOME / "wiki"
    return {path.relative_to(wiki).as_posix().removesuffix(".md"): path
            for path in sorted(wiki.rglob("*.md")) if path.is_file() and path.resolve().is_relative_to(wiki.resolve())}


def unquote(value):
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except ValueError:
            return value
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def split(text):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text, ["第 1 行须为 frontmatter 的 ---"]
    fields, errors, block_key, entries = {}, [], None, []
    for number, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            return fields, "".join(lines[number:]), errors
        bullet = re.fullmatch(r"[ \t]*-[ \t]+(.+?)\s*", line)
        if block_key and bullet:
            entries.append(unquote(bullet[1]))
            fields[block_key] = json.dumps(entries, ensure_ascii=False)
            continue
        block_key, entries = None, []
        key, sep, value = line.strip().partition(":")
        if not sep or not re.fullmatch(r"[\w-]+", key) or key in fields:
            errors.append(f"第 {number} 行的 frontmatter 字段无效或重复")
        else:
            value = value.strip()
            if key in ("related", "tools"):
                if not value:
                    block_key = key
                fields[key] = value
            else:
                fields[key] = unquote(value)
    return fields, "", [*errors, "frontmatter 缺少结尾的 ---"]


def inline_list(text):
    if not text.startswith("[") or not text.endswith("]"):
        return None
    try:
        values = json.loads(text)
    except ValueError:
        values = None
    if isinstance(values, list):
        return values if all(isinstance(part, str) and part.strip() for part in values) else None
    inside = text[1:-1].strip()
    if not inside:
        return []
    parts = [part.strip().strip("\"'").strip() for part in inside.split(",")]
    return parts if all(parts) else None


def related_ids(text):
    return [match[1] for word in inline_list(text) or [] if (match := LINK.fullmatch(word))]


def field_errors(fields, topic, topics):
    errors = [f"缺少 {key}" for key in INPUT_FIELDS if key not in fields]
    if fields.get("topic") != topic:
        errors.append("topic 须和命令指定的主题一致")
    if not 1 <= len(fields.get("summary", "")) <= 80:
        errors.append("summary 须为 1–80 字")
    related = inline_list(fields.get("related", ""))
    if related is None or any(not (match := LINK.fullmatch(word)) or not match[2] for word in related):
        errors.append('related 须为主题链接列表，如 ["[[旅行/上海|上海]]"]')
    elif any(key not in topics or key == topic for key in related_ids(fields["related"])):
        errors.append("related 中每项须指向其他已有主题")
    if inline_list(fields.get("tools", "")) is None:
        errors.append("tools 须为工具列表，如 [owner/repo]")
    return errors


def body_errors(body):
    errors = [f"正文含禁用词「{phrase}」" for phrase in BANNED if phrase in body]
    lines = [(number, line.strip()) for number, line in enumerate(body.splitlines(), 1) if line.strip()]
    sections = [line for _, line in lines if line.startswith("## ")]
    if not lines or not re.fullmatch(r"#\s+\S.*", lines[0][1]) or sections != ["## 要点", "## 出处"]:
        return 0, [*errors, "正文须依次包含一级标题、综合段落、## 要点、## 出处"]
    points = lines.index(next(pair for pair in lines if pair[1] == "## 要点"))
    sources = lines.index(next(pair for pair in lines if pair[1] == "## 出处"))
    intro = " ".join(line for _, line in lines[1:points])
    sentences = re.split(r"[。！？!?]+|\.(?=\s|$)", intro)
    if not 2 <= sum(bool(sentence.strip()) for sentence in sentences) <= 5:
        errors.append("综合段落须为 2–5 句")
    refs, explanations = set(), set()
    for index, (number, line) in enumerate(lines[sources + 1:], 1):
        match = SOURCE.fullmatch(line)
        if not match or match[1] != str(index):
            errors.append(f"正文第 {number} 行的出处须有连续编号、标题、链接和贡献")
        elif SOURCE_METADATA.match(match[4]):
            errors.append(f"正文第 {number} 行的出处只需写贡献，平台和日期由网页补齐")
        else:
            refs.add(match[1])
            explanation = " ".join(match[4].split())
            if explanation in explanations:
                errors.append(f"正文第 {number} 行的出处说明与另一条相同")
            explanations.add(explanation)
    if sources == points + 1 and refs:
        errors.append("要点不能为空")
    in_table = False
    for i, (number, line) in enumerate(lines[1:sources], 1):
        citations = CITATION.findall(line)
        if any(ref not in refs for ref in citations):
            errors.append(f"正文第 {number} 行的出处编号超出范围")
        if i <= points:
            continue
        if line.startswith("### "):
            in_table = False
            continue
        bullet = re.match(r"(?:[-*+]|\d+[.)])\s", line)
        has_cells = "|" in line and not bullet
        if has_cells and i + 1 < sources and table_rule(lines[i + 1][1]):
            in_table = True
            continue
        in_table = in_table and has_cells
        if in_table and table_rule(line):
            continue
        if not citations:
            errors.append(f"正文第 {number} 行的要点缺少出处编号")
        if not (bullet or in_table):
            errors.append(f"正文第 {number} 行的要点须为列表条目或表格行")
    return len(refs), errors


def table_rule(line):
    cells = line.strip("|").split("|")
    return "|" in line and all(TABLE_RULE.fullmatch(cell.strip()) for cell in cells)


def source_lines(body):
    parts = re.split(r"(?m)^## 出处[ \t]*$", body, maxsplit=1)
    if len(parts) == 2:
        yield from re.split(r"(?m)^## ", parts[1], maxsplit=1)[0].splitlines()


def validate(text, topic, topics):
    fields, body, errors = split(text)
    if body:
        errors.extend(field_errors(fields, topic, topics))
        count, problems = body_errors(body)
        errors.extend(problems)
        fields.update(updated=lib.today(), sources=str(count))
    elif not errors:
        errors.append("正文不能为空")
    return fields, body, errors


def metadata():
    path = lib.state_path("notes.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def member_groups(rows):
    groups = defaultdict(list)
    for row in rows.values():
        if row["source"] != "github" and lib.visible(row):
            groups[row["topic"]].append(row)
    return groups


def coverage(group):
    return f"{sum(row['has_body'] for row in group)}/{len(group)}"


def snapshot(rows):
    fields = ("clean_title", "source", "kind", "scene", "entities", "saved", "url", "excerpt", "has_body")
    return {row["id"]: digest(json.dumps([row[key] for key in fields], ensure_ascii=False).encode("utf-8"))
            for row in rows}


def load(events):
    records, result = metadata(), {}
    releases = {event["id"]: event for event in events if event.get("op") == "release" and "id" in event}
    for slug, path in pages().items():
        if slug in ("index", "log") or slug.casefold().startswith("insights/"):
            continue
        data = path.read_bytes()
        text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        fields, body, errors = split(text)
        # Identity follows the note's path, even if its frontmatter was edited.
        result[slug] = {"file": filename(slug), "text": text, "body": body, "fields": fields,
                        "errors": errors, "hash": digest(data)}
    for topic in result.keys() | records.keys() | releases.keys():
        note, record, release = result.get(topic, {}), records.get(topic, {}), releases.get(topic, {})
        baseline = release if lib.event_time(release) > lib.event_time(record) else record
        owner = "ai" if baseline and "hash" in baseline and note.get("hash") == baseline["hash"] else "user"
        members = record.get("members", [])
        snapshot = record.get("fingerprints", dict.fromkeys(members))
        result[topic] = {**note, "snapshot": snapshot, "owner": owner,
                         "generated": bool(note) and note["hash"] == record.get("hash")}
    return result


def save_text(topic, text, snapshot):
    wiki = lib.HOME / "wiki"
    target = wiki / filename(topic)
    if (not all(map(tax.valid_name, topic.split("/"))) or topic.split("/")[0].casefold() in ("index", "log", "insights")
            or not target.resolve().is_relative_to(wiki.resolve())):
        raise lib.Error("主题路径不能用作笔记文件名")
    records = metadata()
    lib.write(target, text)
    records[topic] = {"hash": digest(text.encode("utf-8")), "members": sorted(snapshot),
                      "fingerprints": snapshot, "at": lib.now("microseconds")}
    lib.write(lib.state_path("notes.json"), json.dumps(records, ensure_ascii=False, indent=2) + "\n")


def save(topic, fields, body, snapshot):
    fields = {**fields, "summary": json.dumps(fields["summary"], ensure_ascii=False)}
    lines = [f"{key}: {fields[key]}" for key in FIELDS]
    header = "\n".join(["---", *lines, "---", ""])
    save_text(topic, header + body + ("" if body.endswith("\n") else "\n"), snapshot)
