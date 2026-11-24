# starhub

**让收藏不再吃灰。**

你在 GitHub 上点的 star，在小红书、B站上点的收藏和赞，starhub 会把它们拉回你的电脑。每条都写好“是什么”和“什么时候用得上”，放进一张离线网页。以后你在 agent 里做事，它会从这些收藏里挑出用得上的。

你的习惯不用变：照常在各个 App 里收藏就行。

## 安装

```bash
npx skills add wenzhuofu/starhub -g
```

然后在你的 agent（Claude Code、Codex 等）里输入 `/starhub`，它会带你完成设置：选平台、连接账号、第一次同步。

需要准备：

- Python 3.10 以上。
- 接小红书和 B站时，还要 Chrome 和 [OpenCLI](https://github.com/jackwener/opencli)。设置过程中会一步步引导你安装，并在你的 Chrome 里登录这两个平台。
- `npx skills` 需要 Node 22.20 以上。也可以不用它，直接把 `skills/starhub` 文件夹复制进你的 agent 的 skills 目录，比如 Claude Code 的 `~/.claude/skills/`。

## 用法

| 输入 | 作用 |
|---|---|
| `/starhub 同步` | 拉取新收藏，写好说明，更新网页 |
| `/starhub 打开` | 在浏览器里打开网页，可以搜索，也能按平台、主题筛选 |
| `/starhub <任务>` | 从收藏里找出能用的。比如 `/starhub 下周去杭州玩两天`、`/starhub 给这个仓库画架构图` |
| `/starhub 复盘` | 列出取消了的 star、有更新的工具、很久没用的，再挑几条值得回看的 |

平时它完全不会出现：只有你输入 `/starhub` 时才运行。

## 支持的平台

| 平台 | 拉取什么 | 怎么读取 |
|---|---|---|
| GitHub | star | GitHub API；公开数据，不用登录 |
| 小红书 | 收藏、点赞 | 通过 OpenCLI 借用你 Chrome 里的登录；只读 |
| B站 | 所有收藏夹 | 同上 |

OpenCLI 也能读 X、YouTube、知乎、微博、Reddit 等平台的收藏列表，后面会陆续接进来。

## 它怎么工作

- **说明由你的 agent 来写。** 同步时 agent 会读标题和简介，必要时再读正文或字幕，然后给每条写一句“是什么”、一句“什么时候用得上”，再标一个主题。不需要额外的 API key。
- **数据只在你的电脑上。** 所有收藏都在 `~/.starhub/` 里：`items.jsonl` 一行一条，`starhub.html` 是网页，`INDEX.md` 是给 agent 看的工具索引。没有服务器，也不会上传。
- **GitHub 上的工具能直接用。** 你 star 过的 skill 按固定 commit 拉到 `~/.starhub/vendor/`，平时不会自动加载，用到时 agent 才去读。
- **安全。** 平台内容和第三方 skill 一律当数据，不当指令；对平台只读，不点赞也不评论；安装任何东西之前都会先问你。

## 隐私

starhub 用你自己的登录读取你自己的收藏，读到的内容只存在你的电脑上。平台可能会限制自动访问，所以它尽量少读：同步时只拉新增的部分，请求一个接一个发。

<details>
<summary>命令行</summary>

agent 会替你运行这些命令，一般不需要你手动用。

```
starhub status                 当前状态：多少条、待整理多少、上次同步
starhub setup                  设置平台和 GitHub 用户名
starhub doctor                 检查每个平台能不能用，并给出修复办法
starhub sync [平台]            拉取新收藏
starhub pending / read / apply 整理：列出待整理的、读正文、写入说明
starhub find <词>              搜索收藏
starhub page [--open]          生成并打开网页
starhub show / set / log       查看和修改单条，记录一次使用
starhub review                 复盘报告
starhub vendor / outdated / bump  管理 star 过的 skill
starhub migrate <catalog.toml> 从旧版目录迁移
```

</details>

## 致谢

小红书和 B站的读取靠 [OpenCLI](https://github.com/jackwener/opencli) 完成。
