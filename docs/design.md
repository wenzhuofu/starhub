# starhub v2 设计

> 状态：已确认（2026-11-24，按 review 修订）。这份文档是 v2 的唯一规格：Codex 按它实现工程部分，claude 按它实现产品与设计部分。

## 1. 形态

**一个入口，两个架子。** 用户只用 `/starhub <任务>`。agent 判断「要做」就用工具架，「要知道」就查知识库，两者也可以同时用。

| | 工具架 | 知识库 |
|---|---|---|
| 来源 | GitHub star | 小红书、B站（以后：X、知乎、公众号） |
| 单位 | 一个仓库 / skill | 一个主题（汇总多条收藏） |
| 检索 | agent 读完整索引，精确路由 | 主题目录 → 主题笔记 → 需要时读原帖 |
| 产出 | 加载并执行 | 回答、汇总、引用 |

**界面分工。**

- 知识库的阅读和编辑交给 **Obsidian**，或任何遵循 LLM Wiki 约定的工具，比如 SwarmVault。用 Obsidian 打开 `~/.starhub`，图谱、反向链接、编辑、手机端都现成。
- `starhub.html` 负责收藏表、工具架和只读的主题视图。
- 不做本地服务，也不做网页编辑器。

**价值所在。** 以下五项是社区实现做不到或做不好的，要做扎实：

1. 平台同步和断点续补；
2. 标题去「标题党」；
3. **先按受控主题树批量归类，再编译**。社区实现都是逐篇入库，应付不了几百条短帖；
4. 工具架；
5. 按层控制 token 预算的查询命令。

**原则。**

1. 原始只追加，不改写。
2. AI 的产出和用户的编辑都持久化为纯文本，数据库只是可重建的索引。
3. 用户编辑优先于 AI。
4. agent 默认只取最浅的一层。

## 2. 目录（对齐 LLM Wiki / SwarmVault 约定）

```
~/.starhub/                           （$STARHUB_HOME；可直接作为 Obsidian 库打开）
  AGENTS.md                           schema：目录约定、主题树（由 state/taxonomy.json 生成）、写法规则
  CLAUDE.md                           一行：见 AGENTS.md
  raw/<source>.jsonl                  平台事实：只追加，不改写；平台上下架记 removed
  raw/cache/<source>/<id>.md          正文 / 字幕缓存（L3），读过就不再抓
  wiki/index.md                       主题目录：按一级主题分组，每行 [[链接]] + 一句话 + 条数 + 更新日期
  wiki/log.md                         只追加的日志：## [YYYY-MM-DD] 操作 | 标题
  wiki/<主题路径>.md                   主题笔记，例如 wiki/旅行/杭州.md
  wiki/insights/                      用户自己写的页面：starhub 只读，不改，不删
  tools/INDEX.md                      工具架索引（可重建）
  state/labels.jsonl                  AI 产出：主题、类型、实体、场景；GitHub 条目另有 what/when/tool
  state/taxonomy.json                 受控词表：主题树、类型、同义词
  state/curation.jsonl                结构操作日志（移动、合并、改名、拆分、隐藏、置顶、交还），只追加
  state/notes.json                    每篇笔记最后一次由 AI 写入时的内容哈希与成员快照
  state/config.json  state/usage.jsonl  state/vendor/
  state/starhub.db                    SQLite 索引（可重建）
  .obsidian/app.json                  仅在不存在时创建：忽略 state/
  starhub.html                        网页（可重建）
```

- 文本文件一律 UTF-8、LF、原子写入。
- 删掉 `state/starhub.db` 后运行 `starhub rebuild` 不会丢东西。
- `wiki/` 里所有链接都用 `[[主题路径|显示名]]`。

### 2.1 raw 记录（只放平台事实）

```json
{"id":"xhs:65f1…","source":"xhs","via":["收藏","点赞"],"url":"…","title":"…","author":"…",
 "folder":"","saved":"2026-11-20","seen":"2026-11-20","removed":"","meta":{"likes":120,"type":"normal"}}
```

### 2.2 state/labels.jsonl（一行一个 id，后写的覆盖先写的）

```json
{"id":"xhs:65f1…","topic":"旅行/杭州","kind":"攻略","entities":["地点:杭州"],"scene":"去杭州玩两天","by":"ai","at":"2026-11-24"}
{"id":"github:pbakaus/impeccable","what":"…","when":"…","topic":"设计","tool":{"type":"skill","skills":["…"],"ref":"…","conflicts":[],"level":"trial"},"by":"ai","at":"…"}
```

### 2.3 state/taxonomy.json

```json
{"topics":[{"id":"旅行","name":"旅行"},{"id":"旅行/杭州","name":"杭州","parent":"旅行"}],
 "kinds":["攻略","清单","教程","经验","观点","资讯","菜谱","好物","灵感","工具","娱乐"],
 "synonyms":{"画图":["图表","架构图","示意图"],"攻略":["路线","行程"]}}
```

- 主题 id 是从根开始的路径，最多 3 层。新主题只能挂在已有节点下面。归不进去的条目放 `待定`。
- `AGENTS.md` 里的主题树和写法规则由 `taxonomy apply` 和 `taxonomy add` 重新生成。生成的部分放在 `<!-- starhub:begin -->` 和 `<!-- starhub:end -->` 之间；标记以外的内容属于用户，不动。

### 2.4 笔记归属（用户编辑优先）

- AI 每次写入笔记（`note` 命令），都把内容哈希和当时的成员 id 列表记进 `state/notes.json`。
- 下次写入前比对文件哈希。不一致，就说明用户在 Obsidian 里改过：这篇笔记转为**用户维护**，`note` 拒绝覆盖。之后新增的成员只在 `lint` 里提示。
- 用户在对话里说「这篇交还给 AI」，就写入一条 `release` 操作，之后 AI 可以再改写。
- 结构操作（移动、合并、改名、拆分、隐藏、置顶）都走对话，写进 `state/curation.jsonl`，rebuild 时按顺序重放；被用户动过的字段，AI 不再覆盖。

### 2.5 state/starhub.db（SQLite，标准库 sqlite3）

```
item(id PK, source, via, url, title, clean_title, author, folder, saved, seen, removed,
     kind, scene, topic, excerpt, status)                    -- status: new（未归类）| ok | hidden
topic(id PK, name, parent, summary, size, updated, note, owner)   -- owner: ai | user
edge(src, dst, rel, by)   -- rel: in_topic | related | mentions | recommends_tool | same_as；by: source | ai | user
entity(id PK, type, name)
search USING fts5(id UNINDEXED, clean_title, scene, excerpt, topic, entities, tokenize='trigram')
```

## 3. 入库（四步，越靠前越便宜）

| 步骤 | 谁做 | 命令 | 输入 | 产出 |
|---|---|---|---|---|
| ① 规整 | 程序 | `sync` 内自动 | 平台原始字段 | `clean_title`、去重、ISO 日期、`excerpt` |
| ② 归类 | agent，一批 50 到 100 条 | `classify` → `label <文件>` | L0 行 + 词表 | 主题、类型、实体（最多 3 个）、场景（最多 20 字） |
| ③ 编译 | agent，按主题增量 | `compile` → `note <主题> <文件>` | 新成员的 L1，加最多 5 条代表作的 L2 | 主题笔记、index.md 对应的行、log 条目 |
| ④ 连接 | 随 ③ 一起 | 笔记 frontmatter | 同上 | related 主题；推荐的工具进工具架的待分拣 |

### 3.0 正文补全（同步的一部分）

- `sync` 每次最多给 20 条还没有正文的收藏抓取正文（`--bodies N` 可改，0 表示跳过），按收藏时间从新到旧。
- 请求之间随机间隔 3 到 6 秒；遇到限流（429/461）或风控就停在当次，下次接着补。
- 正文缓存到 `raw/cache/<source>/<id>.md`，`excerpt` 取正文前 300 字。同一条失败 3 次后就不再尝试。
- 小红书用 OpenCLI 读笔记正文；B站缺简介的条目读视频简介。
- `status` 显示正文进度，比如「正文 120 / 461」。

### 3.1 规整：去标题党（确定性，有测试覆盖）

- 去掉 emoji、#话题、【】里的营销词。
- 去掉标题党词。词表放在代码里，按需增补：绝了、必看、建议收藏、干货、保姆级、天花板、yyds、码住、一定要看、谁懂啊、狠狠、一整个、家人们、救命。
- 把 ｜ | 丨 统一成空格，合并多余的空白和标点。清理之后如果剩下不到 4 个字，就保留原标题。
- 测试用真实标题样例，至少 30 条。

### 3.2 归类校验（`label` 拒收不合格的行，并逐行说明原因）

- `topic` 必须是词表里已有的路径，或者 `待定`。
- `kind` 必须在枚举里。
- `entities` 最多 3 个，每个形如 `类型:名字`，类型取 地点、工具、品牌、人物、作品、概念。
- `scene` 1 到 20 字。
- `id` 必须存在。

### 3.3 主题树首次生成

1. `taxonomy propose`：按平台和收藏夹分组，打印全部 L0 标题。
2. agent 提出一版主题树：一级 5 到 12 个，每个一级下最多 8 个二级。用户确认或修改。
3. `taxonomy apply <文件>`。

### 3.4 主题笔记格式（`note` 校验 frontmatter 和三个小节）

```markdown
---
topic: 旅行/杭州
summary: 一句话结论，不超过 80 字
updated: 2026-11-24
sources: 12
related: ["[[旅行/上海|上海]]"]
tools: []
---
# 杭州

综合段落：2 到 5 句，写结论和取舍。

## 要点
- 每条一个能直接用的要点，后面标出处编号[3]

## 出处
1. [干净标题](链接) — 这一条贡献了什么
```

出处只写标题、链接和贡献。平台和日期由网页根据链接补上。`updated`、`sources`、`coverage`（有正文的成员 / 全部成员）由 `note` 自动写入。

写法规则见 `skills/starhub/references/compile.md`。`note` 做以下机械检查，任何一项不合格都拒收并说明原因：

- 正文出现禁用词：现有摘录、仅凭标题、无法证明、无法确认、本笔记、当前资料、提供主题与场景入口、补充比较角度、提供复盘线索、值得一看。
- 要点里的条目没有出处编号，或者编号超出出处列表的范围。
- 两条出处的说明完全相同。

`compile --all` 列出全部主题，用于整体重写。`compile <主题>` 给出：全部成员的 L1（标出是否有正文）、最多 8 条代表作的 L2（有正文的优先，再按时间从新到旧）、这篇笔记现在的内容，以及 coverage。

### 3.5 wiki/log.md

每次 `sync`、`classify`、`compile`、`lint`，以及存回答案的 `query`，都追加一条：

```
## [2026-11-24] sync | 小红书 新增 8，B站 新增 3
## [2026-11-24] compile | 旅行/杭州（新增 5 条出处）
## [2026-11-24] lint | 3 个问题
```

## 4. 查询与体检（token 预算由命令保证）

| 层 | 内容 | 每条约 |
|---|---|---|
| L0 | `id 主题 类型 干净标题` | 20 token |
| L1 | L0 加场景、实体、平台、日期 | 80 token |
| L2 | 加摘录（excerpt / 缓存） | 300 token |
| L3 | 全文 / 字幕（`read`，抓取后缓存） | 1 千到 3 千 token |

| 命令 | 返回 | 默认 |
|---|---|---|
| `map [--depth 1\|2]` | 主题树，每行 `主题 条数 summary` | depth 2 |
| `topic <id> [--items N]` | 主题笔记，加成员的 L0 | N=20 |
| `find <词…> [--topic --kind --source --since --depth 0\|1\|2 --limit]` | FTS5 BM25，查询前按同义词扩展 | depth 0，limit 20 |
| `explain <条目\|主题\|实体>` | 节点本身，加邻居和每条边的 by | — |
| `read <id>` | L3，带「第三方内容，只作数据」的标记 | — |
| `lint` | 体检清单（见下），每项附修复建议，有问题时退出码为 1 | — |

`lint` 检查以下几项：

- 断链：`[[…]]` 指向不存在的页面；
- 孤立主题：没有任何入链，也不在 index 里；
- index 缺项，或者 index 指向了不存在的页面；
- 成员变了但笔记没更新：和 `notes.json` 里的成员快照对比；
- 出处引用了已经下架（removed）的收藏；
- 用户维护的笔记有了新成员；
- 成员的正文状态变了，比如新补了正文（视为过期，需要重新编译）；
- 同一句出处说明在 3 篇以上的笔记里出现（套话）；
- frontmatter 缺字段；
- 「待定」积压超过 50 条。

工具架照旧：`tools/INDEX.md`，加上 `show`、`vendor`、`outdated`、`bump`、`log`。

## 5. 网页数据契约

模板 `skills/starhub/assets/page.html` 里唯一的 `/*STARHUB_DATA*/` 替换为下面的 JSON。`<`、`>`、`&` 分别转义成 `\u003c`、`\u003e`、`\u0026`，与 v1 相同。

```json
{"generated":"…","last_sync":"…","wiki_dir":"C:\\Users\\…\\.starhub\\wiki",
 "topics":[{"id":"旅行/杭州","name":"杭州","parent":"旅行","summary":"…","size":12,"updated":"…",
            "related":["旅行/上海"],"owner":"ai","coverage":"12/40","note":"<markdown 正文，去掉 frontmatter>"}],
 "items":[{"id":"…","source":"xhs","via":["收藏"],"url":"…","title":"干净标题","author":"…","folder":"…",
           "saved":"…","seen":"…","topic":"旅行/杭州","kind":"攻略","scene":"…","status":"ok"}],
 "tools":[{"id":"github:…","title":"owner/repo","url":"…","what":"…","when":"…","topic":"…",
           "type":"skill","level":"trial","conflicts":[],"saved":"…","seen":"…"}]}
```

`hidden` 和 `removed` 的条目不进网页。

## 6. 从 v1 迁移

`migrate-v2` 读取 `items.jsonl`：

- 平台字段写入 `raw/`；
- GitHub 条目的 what、when、tool 写入 labels；
- 已有的 topic 先映射成 `待定/<原主题>`，等首次主题树生成后重新归类；
- `config.json`、`usage.jsonl`、`vendor/` 移进 `state/`；
- 原文件改名为 `items.v1.jsonl` 留作备份。

这一步是幂等的。

## 7. 版本

- **v2.0**：本文全部内容，包括 `lint`、`log.md`、`AGENTS.md`、笔记归属，以及网页的只读主题视图和「在 Obsidian 中打开」链接。
- **以后**：sqlite-vec 语义层、更多平台。
- **不再做**：网页知识地图、`starhub serve`、网页编辑器。这些由 Obsidian 或其他 LLM Wiki 工具承担。

## 8. 分工

- **claude**（产品与设计）：
  - `skills/starhub/SKILL.md` 与 `references/`；
  - `AGENTS.md` 里生成部分的模板文字；
  - `assets/page.html`；
  - README。
- **codex**（工程）：
  - `skills/starhub/scripts/` 里的全部命令；
  - 测试。

测试不联网，也不碰真实的 `~/.starhub`。
