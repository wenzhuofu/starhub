import base64
import datetime as dt
import hashlib
import itertools
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import suppress
from pathlib import Path

from library import Error, LABELS, run

MISSING_OPENCLI = "未安装 OpenCLI：npm install -g @jackwener/opencli@2.0.3（需要 Node ≥ 20.18）"
BRIDGE = ("Chrome 扩展未连接：在 Chrome 安装 OpenCLI 扩展 "
          "https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk")
LOGIN = {
    "xhs": "小红书未登录：在 Chrome 打开 xiaohongshu.com 登录后重试",
    "bili": "B站未登录：在 Chrome 打开 bilibili.com 登录后重试",
}
XHS_URL = "https://www.xiaohongshu.com"
XHS_PROFILE = Path(__file__).resolve().parents[1] / "assets" / "xhs-profile.js"
XHS_SELF_JS = """(async()=>{ for (let i=0; i<20; i++) {
  const raw=window.__INITIAL_STATE__?.user?.userInfo;
  const user=raw?._value??raw;
  const id=user?.user_id||user?.userId||user?.userID;
  if (id) return id;
  await new Promise(resolve=>setTimeout(resolve,250));
} return ''; })()"""
WBI_ORDER = (
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
)


def gh(*args):
    exe = shutil.which("gh")
    if exe:
        with suppress(OSError, subprocess.TimeoutExpired):
            result = run(exe, *args)
            if result.returncode == 0:
                return result.stdout.strip()
    return ""


class GitHub:
    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN") or gh("auth", "token")

    def get(self, path, accept="application/vnd.github+json", limit=-1):
        headers = {"Accept": accept, "User-Agent": "starhub"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request("https://api.github.com" + path, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read(limit).decode("utf-8", errors="replace")

    def stars(self, login, page, size=100):
        if not login:
            raise Error("需要 GitHub 用户名：starhub setup --github <用户名>")
        user = urllib.parse.quote(login, safe="")
        rows = json.loads(self.get(f"/users/{user}/starred?per_page={size}&page={page}",
                                   "application/vnd.github.star+json"))
        return objects(rows)

    def saved(self, login, known, full):
        for page in itertools.count(1):
            batch = self.stars(login, page)
            rows = [github_item(row) for row in batch]
            yield from rows
            if len(batch) < 100 or (not full and all(known(row["id"]) for row in rows)):
                break

    def read(self, item):
        repo = urllib.parse.quote(item["id"].split(":", 1)[1], safe="/")
        notable = {"SKILL.md", "package.json", "pyproject.toml", "Dockerfile", ".mcp.json"}
        lines = [item["meta"].get("desc") or ""]
        try:
            tree = json.loads(self.get(f"/repos/{repo}/git/trees/HEAD?recursive=1"))["tree"]
            paths = [entry["path"] for entry in tree if entry["type"] == "blob" and
                     (entry["path"].rsplit("/", 1)[-1] in notable or
                      entry["path"].endswith(".claude-plugin/marketplace.json"))]
            lines += ["", "关键文件", "\n".join(paths)[:2000]]
        except urllib.error.HTTPError as exc:
            if exc.code not in (404, 409):
                raise
        try:
            lines += ["", "README", self.get(f"/repos/{repo}/readme", "application/vnd.github.raw", 32000)]
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        return "\n".join(lines)


def github_item(row):
    repo = row["repo"]
    title = repo["full_name"]
    return dict(id=f"github:{title}", source="github", via="star", url=repo["html_url"],
                title=title, author=repo["owner"]["login"], folder="", saved=(row.get("starred_at") or "")[:10],
                meta=dict(desc=repo.get("description") or "", language=repo.get("language"),
                          stars=repo.get("stargazers_count", 0), topics=repo.get("topics", [])))


def objects(rows):
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise Error("平台返回的数据格式有误，请稍后重试")
    return rows


class OpenCLI:
    def __init__(self, source):
        self.source = source
        self.exe = shutil.which("opencli")
        if not self.exe:
            raise Error(MISSING_OPENCLI)

    def run(self, *args):
        try:
            return run(self.exe, *args)
        except subprocess.TimeoutExpired as exc:
            raise Error("OpenCLI 超时，请稍后重试") from exc
        except OSError as exc:
            raise Error("无法运行 OpenCLI，请检查安装") from exc

    def call(self, *args, empty=False):
        if args[0] in ("xiaohongshu", "bilibili"):
            args += ("-f", "json")
        result = self.run(*args)
        if empty and result.returncode == 66:
            return []
        try:
            response = json.loads(result.stdout)
        except ValueError:
            response = {}
        error = response.get("error", {}).get("exitCode", result.returncode)
        if error == 69:
            raise Error(BRIDGE)
        if error == 77:
            raise Error(LOGIN[self.source])
        if error == 75:
            raise Error("OpenCLI 超时，请稍后重试")
        if error == 78:
            raise Error("OpenCLI 配置有误，请运行 opencli doctor")
        if result.returncode or response.get("ok") is not True:
            raise Error("OpenCLI 读取失败，请运行 opencli doctor")
        return response.get("data")

    def version(self):
        version = self.run("--version")
        if version.returncode or not version.stdout.strip():
            raise Error("无法读取 OpenCLI 版本，请检查安装")
        return "OpenCLI " + version.stdout.strip()

    def probe(self):
        if not self.call("doctor").get("extensionConnected"):
            raise Error(BRIDGE)
        if self.source == "xhs":
            self.call("xiaohongshu", "saved", "--limit", "1", empty=True)
        else:
            self.uid()

    def uid(self):
        uid = str(self.call("bilibili", "me").get("uid", ""))
        if not re.fullmatch(r"[1-9][0-9]*", uid):
            raise Error(LOGIN["bili"])
        return uid

    def xhs_saved(self, known, history, full):
        # The profile's lists scroll inside their own pane. Use its own
        # sequential page-loading action and the cursor it already maintains.
        script = " ".join(XHS_PROFILE.read_text(encoding="utf-8").splitlines())
        browser = ("browser", "--session", f"starhub-{uuid.uuid4().hex}", "--window", "background")
        try:
            self.call(*browser, "open", f"{XHS_URL}/explore")
            user_id = self.call(*browser, "eval", " ".join(XHS_SELF_JS.splitlines()))
            if not isinstance(user_id, str) or not re.fullmatch(r"[0-9a-f]{24}", user_id):
                raise Error(LOGIN["xhs"])
            account = hashlib.sha256(user_id.encode("ascii")).hexdigest()
            if history.get("account") != account:
                history.clear()
                history["account"] = account
            tabs = history.setdefault("tabs", {})
            if full and all(tabs.get(tab, {}).get("done") for tab in ("fav", "liked")):
                tabs.clear()
            unfinished = sum(not tabs.get(tab, {}).get("done") for tab in ("fav", "liked"))
            pages = None if full else 4 // max(1, unfinished)
            for tab, via in (("fav", "收藏"), ("liked", "点赞")):
                checkpoint = tabs.setdefault(tab, {})
                yield from self.xhs_list(browser, script, tab, user_id, via, known, checkpoint, pages)
        finally:
            with suppress(Error):
                self.call(*browser, "close")

    def xhs_list(self, browser, script, tab, user_id, via, known, checkpoint, history_pages):
        url = f"{XHS_URL}/user/profile/{user_id}?tab={tab}&subTab=note"
        self.call(*browser, "open", url)
        seen = set()

        def read(offset, pages, resume=None):
            resume = resume or {}
            cursor = base64.b64encode(resume.get("cursor", "").encode("utf-8")).decode("ascii")
            page = int(resume.get("page") or 1)
            args = f"('{tab}','{user_id}',{offset},{pages},'{cursor}',{page})"
            result = self.call(*browser, "eval", f"({script}){args}")
            if "rows" not in result:
                self.xhs_failure(via, result)
                raise Error("小红书没有返回有效的列表")
            return result

        def emit(result):
            for row in objects(result["rows"]):
                note_id = row.get("id")
                if not isinstance(note_id, str) or not re.fullmatch(r"[0-9a-f]{24}", note_id):
                    continue
                key = f"xhs:{note_id}"
                if key in seen:
                    continue
                seen.add(key)
                yield dict(id=key, source="xhs", via=via, url=row["url"],
                           title=row["title"], author=row["author"], folder="", saved="",
                           meta=dict(likes=row.get("likes"), type=row.get("type")))

        def advance(state, result):
            state.update(cursor=result.get("cursor") or "", page=result.get("page") or 1,
                         count=state.get("count", 0) + len(result["rows"]),
                         done=not result["more"] and not result.get("error"))

        head = read(0, 0)
        yield from emit(head)
        self.xhs_failure(via, head)
        if not head["more"]:
            checkpoint.update(cursor=head.get("cursor") or "", page=head.get("page") or 1,
                              count=len(head["rows"]), done=True)
            return
        if not checkpoint:
            advance(checkpoint, head)
        else:
            recent = head
            while recent["more"] and not any(known(f"xhs:{row.get('id')}", via) for row in recent["rows"]):
                result = read(recent["offset"], 1)
                if result.get("stalled") and not result["rows"]:
                    self.call(*browser, "open", url)
                    result = read(0, 1, recent)
                yield from emit(result)
                self.xhs_failure(via, result)
                recent = result

        while not checkpoint.get("done"):
            result = read(0, 8 if history_pages is None else history_pages, checkpoint)
            if result.get("stalled") and not result["rows"]:
                self.call(*browser, "open", url)
                result = read(0, 8 if history_pages is None else history_pages, checkpoint)
            yield from emit(result)
            advance(checkpoint, result)
            self.xhs_failure(via, result)
            if history_pages is not None:
                break

    def xhs_failure(self, via, result):
        error = result.get("error")
        if error == "login":
            raise Error(LOGIN["xhs"])
        if error == "profile":
            raise Error(f"小红书{via}页结构有变，无法确认读取的是本人的笔记列表")
        if error == "rate":
            raise Error(f"小红书{via}页限制了请求，已停止；下次同步可接着补历史")
        if error == "request" or result.get("stalled"):
            raise Error(f"小红书{via}页未继续加载，已停止；下次同步可从已记录的位置继续")

    def bili_saved(self, known, first, full):
        uid = self.uid()
        browser = ("browser", "--session", f"starhub-{uuid.uuid4().hex}", "--window", "background")
        try:
            self.call(*browser, "open", "https://www.bilibili.com/")
            nav = self.bili_get(browser, "/x/web-interface/nav")
            wbi = nav["wbi_img"]
            raw = "".join(wbi[key].rsplit("/", 1)[-1].split(".", 1)[0] for key in ("img_url", "sub_url"))
            if len(raw) <= max(WBI_ORDER):
                raise Error("B站返回的数据格式有误，请稍后重试")
            key = "".join(raw[i] for i in WBI_ORDER)[:32]
            folders = self.bili_get(browser, "/x/v3/fav/folder/created/list-all", key, up_mid=uid)
            for folder in objects(folders["list"] or []):
                for page in itertools.count(1):
                    data = self.bili_get(browser, "/x/v3/fav/resource/list", key,
                                         media_id=int(folder["id"]), pn=page, ps=20)
                    batch = objects(data["medias"] or [])
                    rows = [bili_item(row, folder["title"]) for row in batch if row.get("bvid")]
                    yield from rows
                    if not batch or not data["has_more"]:
                        break
                    if not full and ((first and page >= 10) or
                                     (rows and all(known(row["id"]) for row in rows))):
                        break
        finally:
            with suppress(Error):
                self.call(*browser, "close")

    def bili_get(self, browser, path, key="", **params):
        if key:
            params["wts"] = int(dt.datetime.now().timestamp())
            query = urllib.parse.urlencode(sorted(params.items()))
            params["w_rid"] = hashlib.md5((query + key).encode("ascii")).hexdigest()
        url = "https://api.bilibili.com" + path + ("?" + urllib.parse.urlencode(params) if params else "")
        js = f"fetch('{url}', {{credentials: 'include'}}).then(res => res.json())"
        payload = self.call(*browser, "eval", js)
        code = payload["code"]
        if code in (-101, -111, -403):
            raise Error(LOGIN["bili"])
        if code != 0:
            raise Error(f"B站读取失败（{code}），请稍后重试")
        return payload["data"]

    def read(self, item):
        def fields(rows):
            return "\n".join(f"{row['field']}：{row['value']}" for row in objects(rows))

        if self.source == "xhs":
            return fields(self.call("xiaohongshu", "note", item["url"]))
        bvid = item["id"].split(":", 1)[1]
        video = fields(self.call("bilibili", "video", bvid))[:3850]
        captions = self.call("bilibili", "subtitle", bvid, empty=True)
        if captions:
            text = "\n".join(row["content"] for row in objects(captions))[:4000]
            return f"{video}\n\n字幕\n{text}"
        return video


def bili_item(row, folder):
    bvid, stamp = row["bvid"], row.get("fav_time")
    saved = dt.datetime.fromtimestamp(int(stamp)).date().isoformat() if stamp else ""
    return dict(id=f"bili:{bvid}", source="bili", via="收藏", url=f"https://www.bilibili.com/video/{bvid}",
                title=row["title"], author=(row.get("upper") or {}).get("name", ""), folder=folder,
                saved=saved, meta={name: row.get(name) for name in ("intro", "duration", "cover")})


def source_error(source, exc):
    if isinstance(exc, Error):
        return str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        return f"GitHub API 返回 {exc.code}，请检查用户名或登录 gh"
    if isinstance(exc, OSError):
        return f"无法连接 {LABELS[source]}，请检查网络后重试"
    return f"{LABELS[source]} 返回的数据格式有误，请稍后重试"


SOURCE_ERRORS = (Error, OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError)
