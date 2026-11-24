import json
import re

import library as lib

FIELDS = ("topic", "summary", "updated", "sources", "related", "tools")
SNAPSHOT = "compiled"
SOURCE = re.compile(r"([1-9]\d*)\.\s+\[(.+)\]\((\S+)\)\s+—\s+([^·]+)·\s*(\d{4}-\d{2})\s*·\s*(.+)")


def filename(topic):
    slug = re.sub(r'[%/\\<>:"|?*]', lambda match: f"%{ord(match[0]):02X}", topic)
    if re.fullmatch(r"(?i:index|CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", slug):
        slug = f"%{ord(slug[0]):02X}" + slug[1:]
    return slug + ".md"


def split(text):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text, ["第 1 行须为 frontmatter 的 ---"]
    fields, errors = {}, []
    for number, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            return fields, "".join(lines[number:]), errors
        key, sep, value = line.strip().partition(":")
        if not sep or key not in (*FIELDS, SNAPSHOT) or key in fields:
            errors.append(f"第 {number} 行的 frontmatter 字段无效或重复")
        else:
            fields[key] = value.strip()
    return fields, "", [*errors, "frontmatter 缺少结尾的 ---"]


def inline_list(text):
    if not text.startswith("[") or not text.endswith("]"):
        return None
    inside = text[1:-1].strip()
    if not inside:
        return []
    parts = [part.strip().strip("\"'").strip() for part in inside.split(",")]
    return parts if all(parts) else None


def field_errors(fields, topic, topics):
    errors = [f"缺少 {key}" for key in FIELDS if key not in fields]
    if fields.get("topic") != topic:
        errors.append("topic 须和命令指定的主题一致")
    if not 1 <= len(fields.get("summary", "")) <= 80:
        errors.append("summary 须为 1–80 字")
    date = fields.get("updated", "")
    if not date or lib.date(date) != date:
        errors.append("updated 须为 YYYY-MM-DD")
    if not re.fullmatch(r"[0-9]+", fields.get("sources", "")):
        errors.append("sources 须为非负整数")
    related = inline_list(fields.get("related", ""))
    if related is None:
        errors.append("related 须为主题列表，如 [旅行/上海]")
    elif any(key not in topics or key == topic for key in related):
        errors.append("related 中每项须为其他已有主题")
    if inline_list(fields.get("tools", "")) is None:
        errors.append("tools 须为工具列表，如 [owner/repo]")
    return errors


def body_errors(body, count):
    errors = []
    lines = [(number, line.strip()) for number, line in enumerate(body.splitlines(), 1) if line.strip()]
    sections = [line for _, line in lines if line.startswith("## ")]
    if not lines or not re.fullmatch(r"#\s+\S.*", lines[0][1]) or sections != ["## 要点", "## 出处"]:
        return ["正文须依次包含一级标题、综合段落、## 要点、## 出处"]
    points = lines.index(next(pair for pair in lines if pair[1] == "## 要点"))
    sources = lines.index(next(pair for pair in lines if pair[1] == "## 出处"))
    intro = " ".join(line for _, line in lines[1:points])
    sentences = re.split(r"[。！？!?]+|\.(?=\s|$)", intro)
    if not 3 <= sum(bool(sentence.strip()) for sentence in sentences) <= 6:
        errors.append("综合段落须为 3–6 句")
    refs = set()
    for number, line in lines[sources + 1:]:
        match = SOURCE.fullmatch(line)
        if (not match or match[1] in refs or not match[3].startswith(("https://", "http://"))
                or match[4].strip() not in lib.LABELS.values()
                or not lib.date(match[5] + "-01")):
            errors.append(f"正文第 {number} 行的出处须有唯一编号、链接、平台、月份和说明")
        else:
            refs.add(match[1])
    if count.isdecimal() and count.lstrip("0") != (str(len(refs)) if refs else ""):
        errors.append("sources 须等于有效出处的条数")
    if sources == points + 1 and count != "0":
        errors.append("要点不能为空")
    for number, line in lines[points + 1:sources]:
        citations = re.findall(r"\[([1-9]\d*)\]", line)
        if (not line.startswith(("- ", "* ")) or not citations or not re.search(r"\[\d+\]$", line)
                or any(ref not in refs for ref in citations)):
            errors.append(f"正文第 {number} 行的要点须以有效出处编号结尾")
    return errors


def validate(text, topic, topics):
    fields, body, errors = split(text)
    if body:
        errors.extend(field_errors(fields, topic, topics))
        errors.extend(body_errors(body, fields.get("sources", "")))
    elif not errors:
        errors.append("正文不能为空")
    return fields, body, errors


def load():
    notes = {}
    for path in sorted((lib.HOME / "wiki").glob("*.md")):
        if path.name == "index.md":
            continue
        fields, body, errors = split(path.read_text(encoding="utf-8"))
        if not errors and fields.get("topic"):
            snapshot = json.loads(fields.get(SNAPSHOT, "{}"))
            notes[fields["topic"]] = {"file": path.name, "body": body, "fields": fields, "snapshot": snapshot}
    return notes


def save(topic, fields, body, snapshot, file=None):
    lines = [f"{key}: {fields[key]}" for key in FIELDS]
    lines.append(f"{SNAPSHOT}: " + json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
    header = "\n".join(["---", *lines, "---", ""])
    lib.write(f"wiki/{file or filename(topic)}", header + body + ("" if body.endswith("\n") else "\n"))
