# starhub

**把你 star 过的 GitHub 项目，变成 agent 能按需调用的工具箱。**

GitHub star 越积越多，等到真要用时，往往想不起有什么，也不知道该选哪个。starhub 把这些 star 整理成一份目录。需要时在对话里输入 `/starhub <任务>`，agent 会从目录里挑出合适的 skill 或工具来用。平时完全无感：不会自动触发，也不占上下文。

## 怎么用

| 场景 | 做法 |
|---|---|
| 日常收藏 | 在 GitHub 上点 star，不用做别的 |
| 干活时想借力 | 输入 `/starhub 帮我做一个产品落地页`，agent 先看索引挑出 1–3 个项目，说明理由，再加载其中一个 skill 来执行 |
| 定期整理（建议每半个月） | 输入 `/starhub 维护`，会同步新 star 并分拣，出一份复盘报告（取消的 star、上游更新、闲置项目），每一项由你决定怎么处理 |

## 工作原理

- **一个目录**：[`catalog.toml`](catalog.toml) 是唯一的数据源，记录每个项目的类型、用途、何时用、放在哪台机器、状态，以及固定的 commit。[`INDEX.md`](INDEX.md) 和本页下方的目录都由它生成。
- **skill 放在固定目录，不自动加载**：纯 markdown 的 skill 和资源会按固定 commit 稀疏拉取到 `~/.local/share/starhub/vendor/`（可用 `STARHUB_VENDOR` 改位置）。它们不放进 `~/.claude/skills`，所以平时不会触发。
- **只装一个入口 skill**：[`/starhub`](skills/starhub/SKILL.md) 设置了 `disable-model-invocation`，只有你手动输入时才会运行。运行时逐层加载：先看索引，再看项目详情，再读单个 SKILL.md，最后执行。
- **重型项目单独放**：需要 CLI、MCP、Docker 或 GPU 的项目标为 `pc-home`（工程机器），用到时才安装。
- **安全**：所有项目都固定到某个 commit。上游更新只会列出来，由你审阅后再 `starhub bump`。拉下来的 SKILL.md 一律当作数据，不当作指令。

## 自动维护（可选）

[`.github/workflows/maintain.yml`](.github/workflows/maintain.yml) 每月 1 日和 16 日运行，有改动时开 PR 给你审阅。

- **不做任何配置**：只同步新 star、生成复盘报告，零成本。
- **添加 secret `ANTHROPIC_API_KEY`**：额外用 Claude 草拟新项目的目录条目。默认用最便宜的 `claude-haiku-5-5`，分拣一个项目不到一分钱。设置仓库变量 `STARHUB_MODEL` 可以换模型。
- **要让 Action 能开 PR**：在 Settings → Actions → General 里勾选 *Allow GitHub Actions to create and approve pull requests*。
- **不想要自动维护**：在 Actions 页面 Disable 这个 workflow 即可，`/starhub 维护` 照样能用。

## 自己用一份

```bash
git clone git@github.com:<you>/starhub.git && cd starhub
# 1. 把 catalog.toml 里的 github_user 改成你的用户名；[[project]] 可以保留作参考，也可以全删
# 2. 安装：链接 CLI 和 /starhub skill，并拉取 VPS 类的 skill（需要 python ≥ 3.11 和 git）
bin/starhub install
# 3. 在 Claude Code 里输入：/starhub 维护
```

<details><summary>命令一览</summary>

```
starhub show <q> [关键词]   查看项目详情和其中的 skill
starhub review              复盘报告（只读）
starhub sync                同步 star 列表，新项目进入 inbox
starhub triage              用 Claude API 草拟 inbox 条目
starhub vendor [q...]       拉取 skill 到 vendor 目录
starhub outdated / bump     检查上游更新 / 审阅后升级
starhub set <q> <字段> <值>  例如：starhub set impeccable status active
starhub log <q> "备注"       记录使用情况，复盘时会用到
starhub index               重新生成 INDEX.md 和本页的目录
```
</details>

## 目录

状态说明：`active` 主力 · `trial` 试用 · `backlog` 待试 · `inbox` 待分拣 · `archived` 归档

<!-- catalog:start -->
| 部署位置 | 数量 |
|---|---|
| pc-home | 11 |
| VPS | 10 |
| 独立服务器 | 2 |
| 在线版 | 2 |
| 未部署 | 1 |
| 远程读取 | 1 |

### 设计与前端审美

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | skill | VPS | trial | 前端设计词汇与审查：design / redesign / critique / audit / polish / animate，覆盖网页、Dashboard、原生 App 和 DESIGN.md | 从零做或改造前端 UI，或要对现有界面做设计审查 |
| [Nutlope/hallmark](https://github.com/Nutlope/hallmark) | skill | VPS | trial | 反 AI 味的新页面设计 skill，让网站看起来是设计出来的而不是生成的 | 新建网站或新页面；改既有设计必须显式 /hallmark redesign |
| [emilkowalski/skills](https://github.com/emilkowalski/skills) | skill | VPS | trial | 20 个动效与 UI 工艺 skill：animate、review-animations、gestures、apple-design、pick-ui-library、prototype、break-ui 等 | 加动效、审查交互手感、选 UI 库、做原型；可与 impeccable/hallmark 搭配 |
| [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) | resource | VPS | trial | 约 80 个知名品牌设计系统的 DESIGN.md（Airbnb、Apple、Airtable…），放进项目让 agent 照此风格出 UI | 需要明确的品牌风格参考时，挑一份复制进项目 |

### 图表与可视化

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [tt-a1i/archify](https://github.com/tt-a1i/archify) | skill | VPS | trial | 架构/流程/时序/数据流/状态/ERD/类图/时间线等可探索 HTML 图，带校验，可导出 SVG/WebM | 代码库架构图、需要交互探索的技术图 |
| [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) | skill | VPS | trial | 45 种编辑风格图表（架构、泳道、象限、雷达、组织图、飞轮…），自包含 HTML+SVG，不用 Mermaid | 文档、方案、汇报里的精美配图 |

### 代码库理解

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph) | tool | pc-home | backlog | 预建代码知识图谱，保存即自动同步，通过 MCP 供 agent 查询，减少 token 与工具调用 | 长期开发同一个代码库 |
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | tool+skill | pc-home | backlog | 代码（tree-sitter 本地解析）+ 文档 + SQL + PDF + 图片 → 可查询知识图谱；/graphify、graphify explain/path | 代码与文档、Schema、PDF 混杂的项目 |
| [Egonex-AI/Understand-Anything](https://github.com/Egonex-AI/Understand-Anything) | skill+tool | pc-home | backlog | 代码 → 可交互知识图谱 + dashboard；understand / onboard / explain / diff / chat 等 9 个 skill，偏学习与上手 | 接手、学习陌生代码库，做 onboarding |

### Agent 效率与约束

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | tool | pc-home | backlog | 在工具输出、日志、JSON、RAG 片段送进 LLM 前压缩；库 / 代理（headroom proxy）/ MCP 三种形态 | 自建 LLM 应用或 agent 管线要降 token 成本 |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | skill | VPS | trial | “最懒的资深工程师”模式：用最小改动彻底解决问题；附 audit（全仓审计）、review（变更审查）、debt（捷径台账）等 | 任何编码任务防过度设计；仓库质量审计；代码审查 |

### 知识转 Skill

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [virgiliojr94/book-to-skill](https://github.com/virgiliojr94/book-to-skill) | skill+tool | VPS | trial | 把 PDF/EPUB/DOCX/HTML/MD 等书籍文档转成结构化 agent skill，提取框架、心智模型、原则与技巧 | 系统学习一本书，或把参考资料变成可复用的 skill |

### Agent 基础设施

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [stablyai/orca](https://github.com/stablyai/orca) | app | VPS | active | 多 agent 编排：用自有订阅并行跑 Claude Code、Codex 等，桌面/手机/远程运行时 | 多任务并行、远程驱动 agent（当前正在使用） |
| [pingdotgg/t3code](https://github.com/pingdotgg/t3code) | app | 未部署 | backlog | 从任意电脑或手机控制 Claude Code、Codex 等 | 需要另一套远程控制 agent 的界面 |
| [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) | tool+skill | pc-home | backlog | 给 GUI 软件生成 agent 可用的 CLI；CLI-Hub 已收录 69 款（Blender、GIMP、Kdenlive、OBS、Zotero、Obsidian、drawio…） | 要让 agent 操作某个桌面软件 |
| [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) | tool+skill | pc-home | backlog | 让 agent 读取和搜索 Twitter、Reddit、YouTube、B站、小红书、GitHub、V2EX 等，零 API 费用 | 调研、抓取社媒与社区内容 |
| [router-for-me/CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) | tool | 独立服务器 | backlog | 把 Claude Code、Codex、Antigravity、Grok 等订阅型 CLI 包装成 OpenAI/Gemini/Claude 兼容 API | 需要用订阅额度对接只支持 API 的工具 |

### 信息监控与情报

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) | app | pc-home | backlog | 多平台热点 + RSS + 定时联网搜索聚合，关键词/AI 筛选、AI 简报、多渠道推送，自带 MCP 服务 | 长期追踪某些话题、做个人信息流 |
| [koala73/worldmonitor](https://github.com/koala73/worldmonitor) | app | 在线版 | backlog | 实时全球情报面板：新闻聚合、地缘政治、基础设施监控；另有 npx worldmonitor 终端面板与 MCP 工具 | 宏观态势感知 |
| [bilawalsidhu/gods-eye-view](https://github.com/bilawalsidhu/gods-eye-view) | app | 在线版 | backlog | 浏览器里的 3D 地球卫星视角模拟器，叠加真实开源空间数据 | 空间数据可视化参考、演示 |
| [OpenGithubs/github-monthly-rank](https://github.com/OpenGithubs/github-monthly-rank) | resource | 远程读取 | active | GitHub 每月飙升榜 Top30，按 年/月.md 存放，每月 1 号更新 | 每月发现新项目 |

### 内容创作

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | tool+skill | pc-home | backlog | HTML 渲染成视频的可编辑 AI 视频框架；skill 覆盖制作、CLI、素材、视频逆向重建（reverse-any-video）、幻灯片 | 做宣传片、讲解视频、字幕、可演示的幻灯片 |
| [debpalash/VoiceStudio](https://github.com/debpalash/VoiceStudio) | app | pc-home | backlog | 本地版 ElevenLabs：声音克隆/设计、配音、转写、有声书，646 种语言；提供 REST API、MCP 与 skill | 配音、旁白、转写、有声书 |

### 专业领域

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [google-research/timesfm](https://github.com/google-research/timesfm) | model+skill | pc-home | backlog | Google 时间序列预测基础模型，零样本即可预测；附 timesfm-forecasting skill | 销量、流量、业务指标预测 |
| [anthropics/financial-services](https://github.com/anthropics/financial-services) | skill | VPS | trial | Anthropic 官方金融插件集：投行、股研、PE、基金行政等垂直插件，财报复盘、DCF、KYC、月结、对账等 agent 插件，以及 LSEG、S&P Global 合作插件 | 财务建模、估值、财报分析、投行材料 |

### 安全与逆向

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [morluto/rea](https://github.com/morluto/rea) | tool+skill | pc-home | backlog | 一个 MCP 覆盖逆向工程：原生二进制、Electron/JS、固件、浏览器目标；还能为 web/Linux 应用构建 agent 环境 | 分析某个应用功能的实现原理（仅限有权分析的目标） |

### 网络与运维

| 项目 | 类型 | 部署 | 状态 | 作用 | 何时用 |
|---|---|---|---|---|---|
| [MHSanaei/3x-ui](https://github.com/MHSanaei/3x-ui) | app | 独立服务器 | backlog | Xray 多协议代理服务器的 Web 管理面板（VLESS/VMess/Trojan/SS/WireGuard/Hysteria 等，多用户） | 自建网络代理服务器 |
<!-- catalog:end -->
