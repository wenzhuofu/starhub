import datetime as dt
import random
import re
import subprocess
from collections import Counter
from pathlib import Path

from library import Error, HOME, VENDOR, config, jsonl, lookup, put_items, run, today
from sources import GitHub, SOURCE_ERRORS, source_error

LEVELS = ("active", "trial", "backlog")
TOOL_FIELDS = ("type", "level", "skills", "setup", "needs", "conflicts", "ref", "notes", "host")


def repo_name(item):
    return item["id"].split(":", 1)[1]


def git(*args, cwd=None):
    try:
        result = run("git", *args, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Error("无法运行 Git，请检查安装后重试") from exc
    if result.returncode:
        raise Error("Git 操作失败，请检查网络、仓库地址和 ref")
    return result.stdout.strip()


def vendor_dir(item):
    repo = repo_name(item)
    if item["source"] != "github" or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo, re.ASCII):
        raise Error("请输入 GitHub 仓库")
    return VENDOR / repo.replace("/", "__")


def skill_roots(item):
    roots = item["tool"].get("skills") or []
    for root in roots:
        path = Path(root)
        if not root or path.anchor or ".." in path.parts or "\\" in root or ":" in root:
            raise Error("skills 须为仓库内的相对路径")
    return roots


def frontmatter(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not match:
        return {}
    out, key = {}, None
    for line in match[1].splitlines():
        field = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if field:
            key, value = field[1], field[2].strip()
            out[key] = "" if value in (">", "|", ">-", "|-") else value.strip("\"'")
        elif key and line.startswith((" ", "\t")):
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def list_skills(item):
    directory = vendor_dir(item)
    found = []
    for root in skill_roots(item) or ["."]:
        for file in sorted((directory / root).rglob("SKILL.md")):
            if any(part.startswith(".") for part in file.relative_to(directory).parts):
                continue
            fields = frontmatter(file)
            found.append((file, fields.get("name", file.parent.name), fields.get("description", "")))
    return found


def show(args, rows):
    item = lookup(args.q, rows)
    for key, value in item.items():
        print(f"{key:10} {', '.join(map(str, value)) if isinstance(value, list) else value}")
    if item["source"] != "github":
        return
    directory = vendor_dir(item)
    tools = item["tool"]
    if not (directory / ".git").exists():
        if tools.get("ref"):
            print(f"\n尚未拉取：starhub vendor {repo_name(item)}")
        return
    print(f"{'vendor':10} {directory}")
    skills = list_skills(item)
    if not skills:
        for root in skill_roots(item) or ["."]:
            folder = directory / root
            entries = sorted(path.name for path in folder.iterdir()) if folder.is_dir() else []
            print(f"\n{root}/ 下 {len(entries)} 项：{' '.join(entries[:100])}")
        return
    unique = {}
    counts = Counter(name for _, name, _ in skills)
    for file, name, desc in skills:
        unique.setdefault(name, (file, desc))
    keyword = " ".join(args.keyword).casefold()
    matches = [(name, file, desc) for name, (file, desc) in unique.items() if keyword in (name + desc).casefold()]
    print(f"\n{len(unique)} 个 skill" + (f"（匹配 {len(matches)} 个）" if keyword else "") + "。按需读取 SKILL.md：")
    for name, file, desc in matches:
        dup = f" [×{counts[name]}]" if counts[name] > 1 else ""
        if len(matches) > 25:
            print(f"- {name}{dup}：{desc[:90]} ← {file.relative_to(directory)}")
        else:
            print(f"- {name}{dup}：{desc[:180]}\n    {file}")


def vendor_one(item):
    directory = vendor_dir(item)
    ref = item["tool"].get("ref", "")
    if not ref:
        raise Error("缺少 ref")
    if not re.fullmatch(r"[\w][\w./-]*", ref, re.ASCII):
        raise Error("ref 格式有误")
    roots = skill_roots(item)
    url = f"https://github.com/{repo_name(item)}.git"
    if not (directory / ".git").exists():
        directory.mkdir(parents=True, exist_ok=True)
        git("init", "-q", cwd=directory)
    git("config", "remote.origin.url", url, cwd=directory)
    git("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", ref, cwd=directory)
    if roots:
        git("sparse-checkout", "set", "--", *roots, cwd=directory)
    else:
        git("sparse-checkout", "disable", cwd=directory)
    git("checkout", "-q", "--detach", "FETCH_HEAD", cwd=directory)
    print(f"✓ {repo_name(item)} @ {ref[:7]} → {directory}（{len(list_skills(item))} 个 skill）")


def vendor(args, rows):
    def eligible(item):
        kind = item.get("tool", {}).get("type", "")
        return item["source"] == "github" and item["status"] != "archived" and ("skill" in kind or kind == "resource")

    targets = [lookup(q, rows) for q in args.q] if args.q else [p for p in rows.values() if eligible(p)]
    failed = 0
    for item in targets:
        try:
            vendor_one(item)
        except (Error, OSError) as exc:
            print(f"跳过 {item['id']}：{exc}")
            failed += 1
    return int(bool(targets) and failed == len(targets))


def remote_head(repo):
    head = git("ls-remote", f"https://github.com/{repo}.git", "HEAD").split()
    if not head:
        raise Error("无法读取 GitHub 仓库 HEAD")
    return head[0]


def updates(rows):
    for item in rows.values():
        ref = item.get("tool", {}).get("ref")
        if item["source"] != "github" or item["status"] == "archived" or not ref:
            continue
        repo = repo_name(item)
        try:
            head = remote_head(repo)
        except Error:
            yield f"? {repo}：无法访问上游"
            continue
        if not head.lower().startswith(ref.lower()):
            yield f"↑ {repo}：{ref[:7]} → {head[:7]}  https://github.com/{repo}/compare/{ref[:12]}...{head[:12]}"


def outdated(_args, rows):
    print("\n".join(updates(rows)) or "全部是最新")


def bump(args, rows):
    item = lookup(args.q, rows)
    directory = vendor_dir(item)
    ref = args.sha or remote_head(repo_name(item))
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", ref):
        raise Error("请输入有效的提交 SHA")
    item["tool"]["ref"] = ref
    if (directory / ".git").exists():
        vendor_one(item)
    put_items(rows)
    print(f"{repo_name(item)} ref → {ref[:7]}")


def review(_args, rows):
    def section(title, records, empty="- 无"):
        print("\n## " + title)
        print("\n".join(records) or empty)

    print(f"# starhub 复盘 {today()}")
    pending = [p for p in rows.values() if p["status"] == "new" or
               "AI 草拟" in p.get("tool", {}).get("notes", "")]
    section(f"待确认的新收藏（{len(pending)}）", [f"- `{p['id']}` {p['what'] or p['title']}" for p in pending[:10]])
    cfg = config(required=False)
    if cfg["github"] and "github" in cfg["sources"]:
        try:
            starred = {p["id"].casefold(): p["id"] for p in GitHub().saved(cfg["github"], lambda _: False, True)}
            known = {p["id"].casefold() for p in rows.values() if p["source"] == "github"}
            new = [original for key, original in starred.items() if key not in known]
            if new:
                print(f"- 另有 {len(new)} 个新 star 尚未同步：" + "，".join(new) + " → `starhub sync`")
            gone = [p["id"] for p in rows.values()
                    if p["source"] == "github" and p["status"] != "archived" and p["id"].casefold() not in starred]
            section(f"已取消 star（{len(gone)}）", [f"- `{key}` → `starhub set {key} status archived`" for key in gone])
        except SOURCE_ERRORS as exc:
            section("已取消 star", ["- " + source_error("github", exc)])
    upstream = list(updates(rows))
    section(f"上游有更新（{len(upstream)}）", [f"- {line}" for line in upstream])
    if upstream:
        print("查看差异后运行 `starhub bump <仓库>`。")

    usage = jsonl(HOME / "usage.jsonl")
    count = Counter(row["id"] for row in usage)
    last = {}
    for row in usage:
        last[row["id"]] = max(last.get(row["id"], ""), row["date"])
    date = dt.date.today()
    cutoff = (date - dt.timedelta(days=90)).isoformat()
    idle = [p["id"] for p in rows.values() if p["status"] == "ok" and p.get("tool", {}).get("level") in
            ("trial", "active") and p["saved"] < cutoff and last.get(p["id"], "") < cutoff]
    section(f"90 天未使用的试用或主力工具（{len(idle)}）",
            [f"- `{key}`（最近使用：{last.get(key, '从未')}）" for key in idle])
    section("使用最多", [f"- `{key}` × {n}（最近 {last[key]}）" for key, n in count.most_common(10)],
            "- 暂无使用记录")
    cutoff = (date - dt.timedelta(days=30)).isoformat()
    old = sorted(p["id"] for p in rows.values() if p["status"] == "ok" and p["saved"] < cutoff and p["id"] not in count)
    picks = random.Random(str(date.isocalendar()[:2]))
    section("值得回看", [f"- `{key}` {rows[key]['title']}" for key in picks.sample(old, min(3, len(old)))])
