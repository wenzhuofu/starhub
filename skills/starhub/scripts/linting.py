import json
import posixpath
import re
from collections import defaultdict

import catalog
import library as lib
import notes
import taxonomy as tax
import views

WIKILINK = re.compile(r"!?" + notes.LINK.pattern)
CODE = re.compile(r"(?ms)^ {0,3}(`{3,}|~{3,}).*?^ {0,3}\1[ \t]*(?=\r?$)|`+[^`\n]+`+")


def visit_links(text, visit):
    pieces, cursor = [], 0
    for code in CODE.finditer(text):
        pieces.extend((WIKILINK.sub(visit, text[cursor:code.start()]), code[0]))
        cursor = code.end()
    return "".join([*pieces, WIKILINK.sub(visit, text[cursor:])])


def resolver(pages):
    basenames = defaultdict(list)
    canonical = {}
    for slug in pages:
        canonical[slug.casefold()] = slug
        basenames[slug.rsplit("/", 1)[-1].casefold()].append(slug)

    def resolve(origin, target):
        path = target.partition("#")[0].strip().removeprefix("wiki/").removesuffix(".md")
        if not path:
            return origin
        relative = posixpath.normpath(posixpath.join(posixpath.dirname(origin), path))
        for candidate in (path, relative):
            if candidate.casefold() in canonical:
                return canonical[candidate.casefold()]
        hits = basenames[path.casefold()]
        return hits[0] if len(hits) == 1 else None

    return resolve


def repair_notes(wiki, pages, resolve):
    changed = 0
    for key, note in wiki.items():
        if key not in pages or not note["generated"] or note["owner"] != "ai":
            continue

        def repair(match):
            return match[0] if resolve(key, match[1]) else (match[2] or match[1])

        fields = note["fields"]
        related = notes.inline_list(fields.get("related", ""))
        text = note["text"]
        if related is not None:
            kept = [word for word in related if (match := notes.LINK.fullmatch(word)) and resolve(key, match[1])]
            if kept != related:
                field = "related: " + json.dumps(kept, ensure_ascii=False)
                text = re.sub(r"(?m)^related:.*$", lambda _: field, text, count=1)
        text = visit_links(text, repair)
        if text != note["text"] and notes.digest(pages[key].read_bytes()) == note["hash"]:
            notes.save_text(key, text, note["snapshot"])
            changed += 1
    return changed


def findings(state, pages, resolve):
    rows, topics, wiki, _, _ = state
    issues, inbound, indexed = [], set(), set()

    def add(problem, place, hint):
        issues.append(f"{problem} · {place} → {hint}")

    for slug, path in pages.items():
        def check(match):
            target = resolve(slug, match[1])
            if target is None:
                if slug == "index":
                    hint = "运行 starhub lint --fix 重建生成目录" if managed else "在目录中修正或移除该链接"
                    add("目录断链", match[0], hint)
                else:
                    hint = "检查目标，或将链接改成正文"
                    if wiki.get(slug, {}).get("generated"):
                        hint = "运行 starhub lint --fix，或补齐目标页面"
                    add("断链", f"{slug} → {match[0]}", hint)
            elif slug == "index":
                indexed.add(target)
            elif target != slug:
                inbound.add(target)
            return match[0]

        text = path.read_text(encoding="utf-8")
        before, start, rest = text.partition(views.INDEX_START)
        middle, end, after = rest.partition(views.INDEX_END)
        sections = [(before, False), (middle, True), (after, False)] if slug == "index" and start and end else [(text, False)]
        for text, managed in sections:
            visit_links(text, check)

    live_notes = {key for key, note in wiki.items() if note.get("file")}
    for key in sorted(live_notes - indexed):
        if key in topics:
            add("目录缺项", key, "运行 starhub lint --fix 补入生成目录")
        if key not in inbound:
            add("孤立主题", key, "从目录或相关主题补一条链接")

    removed = set()
    active = {row["url"] for row in rows.values() if not row["removed"]}
    for source in lib.LABELS:
        for row in lib.jsonl(lib.HOME / f"raw/{source}.jsonl"):
            if rows[row["id"]]["removed"]:
                removed.add(row["url"])
    removed -= active
    groups = notes.member_groups(rows)
    for key, note in sorted(wiki.items()):
        if key in live_notes:
            fields = note["fields"]
            gaps = [field for field in notes.FIELDS if not fields.get(field)]
            if fields.get("topic") and fields["topic"] != key:
                gaps.append("topic 与文件路径不一致")
            if note["errors"] or gaps:
                add("frontmatter 缺项或格式有误", f"{key}（{'、'.join([*gaps, *note['errors']])}）",
                    "按主题笔记格式补全字段")
            for line in note["body"].splitlines():
                match = notes.SOURCE.fullmatch(line.strip())
                if match and match[3] in removed:
                    add("出处已下架", f"{key} [{match[1]}]", "更换出处或删去对应引用")
        current, previous = notes.snapshot(groups[key]), note["snapshot"]
        new = current.keys() - previous.keys()
        if note["owner"] == "user" and new:
            add("用户维护的笔记有新成员", f"{key}（{len(new)} 条）", f"手动补充，或确认后运行 starhub release {key}")
        elif note["owner"] == "ai" and current != previous:
            add("笔记待更新", key, f"运行 starhub compile {key}")
        elif note["owner"] == "user" and current != previous:
            add("用户维护的笔记成员已变化", key, "在 Obsidian 中核对出处与当前成员")

    pending = sum(len(group) for key, group in groups.items() if key == tax.PENDING or key.startswith(tax.PENDING + "/"))
    if pending > 50:
        add("待定积压", f"{pending} 条", "补充词表后运行 starhub classify --pending")
    return issues


def lint(args, state):
    pages = notes.pages()
    repaired = 0
    if args.fix:
        repaired = repair_notes(state[2], pages, resolver(pages))
        views.rebuild()
        pages, state = notes.pages(), catalog.state()
    issues = findings(state, pages, resolver(pages))
    for issue in issues:
        print(issue)
    title = f"{len(issues)} 个问题"
    if args.fix:
        title += f"，已重建目录并修正 {repaired} 篇生成笔记"
    print(title)
    lib.wiki_log("lint", title)
    return int(bool(issues))
