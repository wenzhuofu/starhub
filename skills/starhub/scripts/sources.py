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

from library import Error, LABELS, run

MISSING_OPENCLI = "未安装 OpenCLI：npm install -g @jackwener/opencli@2.0.3（需要 Node ≥ 20.18）"
BRIDGE = ("Chrome 扩展未连接：在 Chrome 安装 OpenCLI 扩展 "
          "https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk")
LOGIN = {
    "xhs": "小红书未登录：在 Chrome 打开 xiaohongshu.com 登录后重试",
    "bili": "B站未登录：在 Chrome 打开 bilibili.com 登录后重试",
}
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
        result = self.run(*args, "-f", "json")
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

    def xhs_saved(self, limit):
        for command, via in (("saved", "收藏"), ("liked", "点赞")):
            for row in objects(self.call("xiaohongshu", command, "--limit", str(limit), empty=True)):
                yield dict(id=f"xhs:{row['id']}", source="xhs", via=via, url=row["url"],
                           title=row["title"], author=row["author"], folder="", saved="",
                           meta=dict(likes=row.get("likes"), type=row.get("type")))

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
