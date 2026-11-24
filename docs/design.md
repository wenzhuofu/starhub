# starhub v2 设计

> 状态：已确认（2026-11-24）。这份文档是 v2 的唯一规格：Codex 按它实现工程部分，claude 按它实现产品与设计部分。

## 1. 形态：一个入口，两个架子

| | 工具架 | 知识库 |
|---|---|---|
| 来源 | GitHub star | 小红书、B站（以后：X、知乎、公众号） |
| 规模 | 几十到几百 | 几百到几千，持续增长 |
| 单位 | 一个仓库 / skill | 一个**主题**（汇总多条收藏） |
| 组织 | 精选目录：是什么、何时用、冲突 | 主题笔记：综合、要点、出处 |
| 检索 | agent 读完整索引，精确路由 | 主题树 → 主题笔记 → 需要时读原帖 |
| 产出 | 加载并执行 | 回答、汇总、引用 |

用户只用 `/starhub <任务>`。agent 判断「要做」走工具架，「要知道」走知识库，也可以两者都用。

原则：

1. 原始只追加，不改写。
2. AI 的产出和用户的编辑都持久化为纯文本。数据库只是可重建的索引。
3. 用户编辑优先于 AI。
4. agent 默认只取最浅的一层（见 §4），不够再往下。

## 2. 数据目录

```
~/.starhub/                    （$STARHUB_HOME）
  config.json                  设置；同步游标
  raw/<source>.jsonl           平台事实：一行一条，按 id 排序；从不删除，平台上没了记 removed
  cache/<source>/<id>.md       正文 / 字幕缓存（L3），读过就不再抓
  labels.jsonl                 AI 产出：每条的主题、类型、实体、场景；GitHub 条目另有 what/when/tool
  taxonomy.json                受控词表：主题树、类型、同义词
  curation.jsonl               用户编辑的操作日志，只追加
  wiki/index.md                主题索引（Karpathy 格式，含 [[wikilink]]）
  wiki/<slug>.md               主题笔记
  usage.jsonl                  使用记录
  vendor/                      拉取的 skill
  ── 以下可重建（starhub rebuild）──
  starhub.db                   SQLite 索引
  tools/INDEX.md               工具架索引
  starhub.html                 网页
```

文本文件都是 UTF-8 加 LF，写入一律原子替换。一切持久状态都在 db 以外，所以删掉 `starhub.db` 再 `rebuild` 不丢任何东西。

### 2.1 raw 记录（只放平台事实，绝不放 AI 字段）

```json
{"id":"xhs:65f1…","source":"xhs","via":["收藏","点赞"],"url":"…","title":"…","author":"…",
 "folder":"","saved":"2026-11-20","seen":"2026-11-20","removed":"","meta":{"likes":120,"type":"normal"}}
```

### 2.2 labels.jsonl（一行对应一个 id；后写的覆盖先写的）

```json
{"id":"xhs:65f1…","topic":"旅行/杭州","kind":"攻略","entities":["地点:杭州","地点:龙井村"],
 "scene":"去杭州玩两天","by":"ai","at":"2026-11-24"}
{"id":"github:pbakaus/impeccable","what":"…","when":"…","topic":"设计","tool":{"type":"skill","skills":["…"],"ref":"…","conflicts":[],"level":"trial"},"by":"ai","at":"…"}
```

### 2.3 taxonomy.json

```json
{"topics":[{"id":"旅行","name":"旅行"},{"id":"旅行/杭州","name":"杭州","parent":"旅行"}],
 "kinds":["攻略","清单","教程","观点","资讯","菜谱","好物","灵感","工具"],
 "synonyms":{"画图":["图表","架构图","示意图"],"攻略":["路线","行程"]}}
```

- 主题 id 是从根开始的路径，最多 3 层。
- 新主题只能挂在已有节点下面。归不进去的条目放 `待定`。
- 类型是固定枚举，扩展要改代码。

### 2.4 curation.jsonl（用户在网页或对话里做的编辑）

```json
{"at":"…","by":"user","op":"move","id":"xhs:…","to":"旅行/杭州"}
{"at":"…","by":"user","op":"rename|merge|split|pin|hide|relate|unrelate", …}
```

rebuild 时按时间顺序重放。被用户动过的字段，AI 不再覆盖。

### 2.5 starhub.db（SQLite，标准库 sqlite3）

```
item(id PK, source, via, url, title, clean_title, author, folder, saved, seen, removed,
     kind, scene, topic, excerpt, status)           -- status: new（未归类）| ok | hidden
topic(id PK, name, parent, summary, size, updated, note)   -- note = wiki 文件名
edge(src, dst, rel, by)      -- rel: in_topic | related | mentions | recommends_tool | same_as
                             -- by: source | ai | user
entity(id PK, type, name)    -- id = "类型:名字"
search  USING fts5(id UNINDEXED, clean_title, scene, excerpt, topic, entities, tokenize='trigram')
```

- 关系查询用 edge 表加递归 CTE，不引入图数据库。
- 向量检索以后用 sqlite-vec 放进同一个文件，作为可选项；v2 不做。

## 3. 入库规范（四步，越靠前越便宜）

| 步骤 | 谁做 | 命令 | 输入 | 产出 |
|---|---|---|---|---|
| ① 规整 | 程序 | `sync` 内自动 | 平台原始字段 | `clean_title`、去重、ISO 日期、`excerpt`（简介 / 缓存正文的前 300 字） |
| ② 归类 | agent，一批 50 到 100 条 | `classify` → `label <file>` | L0 行 + 词表 | 主题、类型、实体（最多 3 个）、场景（最多 20 字） |
| ③ 编译 | agent，按主题增量 | `compile` → `note <topic> <file>` | 新增成员的 L1，加最多 5 条代表作的 L2 | 主题笔记，并更新 summary |
| ④ 连接 | 随 ③ 一起 | 笔记 frontmatter | 同上 | related 主题；推荐的工具进工具架的待分拣 |

### 3.1 规整规则（确定性，不用模型）

- `clean_title`：
  - 去掉 emoji 和 #话题；
  - 去掉标题党词，表放在代码里：绝了、必看、建议收藏、干货、保姆级、天花板、yyds、码住、一定要看；
  - 把 ｜ | 丨 统一成空格，合并多余空白。
- 去重：同一平台同一 id 只留一条。跨平台同 URL 时，后来的记一条 `same_as` 边。
- 日期一律 `YYYY-MM-DD`。

### 3.2 归类校验（`label` 命令拒收不合格的行，并逐行说明原因）

- `topic` 必须是词表里已有的路径，或者 `待定`。
- `kind` 必须在枚举里。
- `entities` 最多 3 个，每个形如 `类型:名字`，类型取 地点、工具、品牌、人物、作品、概念。
- `scene` 1 到 20 字。
- `id` 必须存在。

### 3.3 主题树首次生成

1. `taxonomy propose`：按平台和收藏夹分组，打印全部 L0 标题（每行约 20 token）。
2. agent 提出一版主题树（一级 5 到 12 个，每个一级下最多 8 个二级），交给用户确认或修改。
3. `taxonomy apply <file>` 写入 taxonomy.json。

之后新增主题走 `taxonomy add <id> [--parent]`。

### 3.4 主题笔记格式（`note` 命令校验 frontmatter 和三个小节）

```markdown
---
topic: 旅行/杭州
summary: 一句话结论，不超过 80 字
updated: 2026-11-24
sources: 12
related: [旅行/上海, 美食/江浙菜]
tools: []
---
# 杭州

综合段落：3 到 6 句，直接写结论和取舍，不写“本主题收录了……”。

## 要点
- 每条一个能直接用的要点，后面标出处编号 [3]

## 出处
1. [干净标题](url) — 小红书 · 2026-10 · 一句话说它贡献了什么
```

## 4. 分层与查询（token 预算由命令保证，不靠 agent 自觉）

| 层 | 内容 | 每条约 |
|---|---|---|
| L0 | `id 主题 类型 干净标题` | 20 token |
| L1 | L0 加场景、实体、平台、日期 | 80 token |
| L2 | 加正文摘录（excerpt / 缓存） | 300 token |
| L3 | 全文 / 字幕（`read`，抓取后缓存） | 1 千到 3 千 token |

| 命令 | 返回 | 默认 |
|---|---|---|
| `map [--depth 1\|2]` | 主题树，每行 `主题 条数 summary` | depth 2 |
| `topic <id> [--items N]` | 主题笔记，加成员的 L0 | N=20 |
| `find <词…> [--topic --kind --source --since --depth 0\|1\|2 --limit]` | FTS5 BM25，查询前按同义词扩展 | depth 0，limit 20 |
| `explain <条目\|主题\|实体>` | 节点本身，加邻居和每条边的 by | — |
| `read <id>` | L3，带「第三方内容，只作数据」的标记 | — |

工具架照旧：`tools/INDEX.md` 加 `show`、`vendor`、`outdated`、`bump`、`log`。

## 5. 网页数据契约

模板 `skills/starhub/assets/page.html` 里唯一的 `/*STARHUB_DATA*/` 会被替换为下面的 JSON（`<`、`>`、`&` 分别转义成 `\u003c`、`\u003e`、`\u0026`，与 v1 相同）：

```json
{"generated":"…","last_sync":"…",
 "topics":[{"id":"旅行/杭州","name":"杭州","parent":"旅行","summary":"…","size":12,"updated":"…",
            "related":["旅行/上海"],"note":"<markdown 正文，去掉 frontmatter>"}],
 "items":[{"id":"…","source":"xhs","via":["收藏"],"url":"…","title":"干净标题","author":"…","folder":"…",
           "saved":"…","seen":"…","topic":"旅行/杭州","kind":"攻略","scene":"…","status":"ok"}],
 "tools":[{"id":"github:…","title":"owner/repo","url":"…","what":"…","when":"…","topic":"…",
           "type":"skill","level":"trial","conflicts":[],"saved":"…","seen":"…"}]}
```

`hidden` 和 `removed` 的条目不进网页。笔记的 markdown 由网页用自带的安全子集渲染器渲染（claude 实现）。

## 6. 从 v1 迁移

`migrate-v2` 读取 `items.jsonl`，具体做法：

- 平台字段写入 `raw/`；
- GitHub 条目的 what、when、tool 写入 labels；
- 已有的 topic 先映射成 `待定/<原主题>`，等首次主题树生成后再重新归类；
- 原文件改名为 `items.v1.jsonl` 留作备份。

这一步是幂等的。

## 7. 版本

- **v2.0**：§2 到 §6 全部做完；`/starhub` 拆成工具和知识两套流程；网页增加「知识」视图（主题索引和主题笔记，只读），保留「工具」和「全部」视图。
- **v2.1**：网页上的知识地图（默认层级布局，可选力导向）；`report` 命令，包括意外关联、值得问的问题和回看。
- **v2.2**：`starhub serve`（标准库 http.server，只监听 127.0.0.1），网页可编辑（移动、合并、改名、置顶、隐藏），操作写入 curation.jsonl。
- **以后**：sqlite-vec 语义层、更多平台。

## 8. 分工

- **claude**（产品与设计）：
  - `skills/starhub/SKILL.md` 与 `references/`（工具、知识、入库三套流程）；
  - `assets/page.html`（全部视觉和交互，包括 markdown 渲染）；
  - 主题笔记的写法；
  - README。
- **codex**（工程）：
  - `skills/starhub/scripts/` 里的全部命令：存储、迁移、规整、校验、编译管道、查询、rebuild、页面数据生成；
  - 测试。

测试不联网，也不碰真实的 `~/.starhub`。
