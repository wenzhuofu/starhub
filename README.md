# starhub

**让收藏不再吃灰。**

你在 GitHub 上点的 star，在小红书、B站上点的收藏和赞，starhub 会把它们拉回你的电脑，整理成两样东西：

- **工具架**：你 star 过的工具和 skill，每个都写好「是什么、什么时候用得上」。agent 做事时会从这里挑工具来用。
- **知识库**：小红书、B站的收藏按主题归好类，每个主题由 agent 写成一篇笔记，笔记里的每个要点都标着出自哪条收藏。你可以问 agent，也可以用 Obsidian 直接读。

你的习惯不用变：照常在各个 App 里收藏就行。

## 安装

```bash
npx skills add wenzhuofu/starhub -g
```

装好后在 agent 里输入 `/starhub`（Codex 里是 `$starhub`），它会带你完成设置：选平台、连接账号、确认主题树、第一次整理。

需要准备：

- Python 3.10 以上；
- 接小红书和 B站时，还要 Chrome 和 [OpenCLI](https://github.com/jackwener/opencli)，设置时会一步步引导你；
- `npx skills` 需要 Node 22.20 以上。也可以不用它，直接把 `skills/starhub` 文件夹复制进你的 agent 的 skills 目录。

## 用法

| 输入 | 作用 |
|---|---|
| `/starhub 同步` | 拉取新收藏，顺带补一批正文，再整理 |
| `/starhub 整理` | 把新收藏归到主题，更新主题笔记 |
| `/starhub 打开` | 打开网页：知识、工具、全部收藏，三种视图 |
| `/starhub <任务>` | 要做事就从工具架挑工具，要知道就查知识库。比如 `/starhub 准备风控策略面试`、`/starhub 给这个仓库画架构图` |
| `/starhub 体检` | 检查知识库：断链、过期笔记、引用了已下架的收藏…… |
| `/starhub 复盘` | 取消了的 star、有更新的工具、很久没用的东西 |

平时它完全不会出现：只有你输入 `/starhub` 时才运行。

## 它怎么工作

- **同步**：GitHub 走公开 API；小红书和 B站通过 OpenCLI 借用你 Chrome 里的登录，只读。每次只拉新增的部分，翻历史和补正文都能断点续上。正文每次补 20 条，慢慢补全，尽量不触发平台风控。
- **归类再编译**：先由你确认一棵主题树，agent 只看标题，一批几十条地快速归类；再按主题编译笔记，只给有新内容的主题重写。几百条短帖也处理得过来，不用一条条入库。
- **标题清理**：去掉「绝了」「建议收藏」这类标题党用词，目录和笔记更干净。
- **按需取用，省 token**：agent 查知识库时先看主题目录（大约 1 千 token），再打开需要的那篇笔记，确实需要时才读原帖。
- **库就是一个文件夹**：`~/.starhub` 遵循 [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 约定：
  - `AGENTS.md` 写着主题树和写作规则；
  - `wiki/index.md` 是目录，`wiki/log.md` 是日志，每个主题一篇 markdown。

  用 Obsidian 打开就能看图谱、反向链接，在手机上读；其他 LLM Wiki 工具也能直接读写。你在 Obsidian 里改过的笔记，AI 不会再覆盖。

## 隐私与安全

- 数据只在你的电脑上，没有服务器，也不上传。
- 平台内容和第三方 skill 一律当作数据，不当作指令。
- 对平台只读，不点赞也不评论。
- 安装任何东西之前都会先问你。

<details>
<summary>命令行</summary>

agent 会替你运行这些命令，一般不用手动用。

```
starhub status / setup / doctor        状态、设置、检查连接
starhub sync [平台] [--bodies N]        同步，顺带补正文
starhub taxonomy propose|apply|add     主题树
starhub classify / label               归类
starhub compile / note                 编译主题笔记
starhub map / topic / find / explain   分层查询
starhub read <id>                      读原文（会缓存）
starhub lint [--fix]                   体检
starhub curate / release               移动、合并、隐藏；把笔记交还给 AI
starhub page [--open]                  生成网页
starhub show / vendor / outdated / bump / log   工具架
starhub migrate-v2                     从 v1 迁移
```

</details>

## 致谢

小红书和 B站的读取靠 [OpenCLI](https://github.com/jackwener/opencli)；知识库的组织方式来自 Karpathy 的 [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)。

## 许可

MIT
