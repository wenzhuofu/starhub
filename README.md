# starhub

我 star 的 GitHub 项目的目录，以及按需调用它们的方式。

- **日常添加**：在 GitHub 上点 star 就行。之后运行 `starhub sync`，新项目会进入 inbox，由 agent 分拣。
- **数据源**：[`catalog.toml`](catalog.toml)。[`INDEX.md`](INDEX.md) 和下面的目录都是由它生成的。
- **使用**：VPS 上装了一个 [`starhub` skill](skills/starhub/SKILL.md)。agent 遇到任务时会逐层查看：先看 INDEX，再看项目详情，再加载单个 SKILL.md，最后执行。

## 部署分工

| 位置 | 放什么 | 怎么用 |
|---|---|---|
| **VPS** | 纯 markdown 或只有轻量脚本的 skill、资源 | 按固定 ref 稀疏拉取到 `~/.local/share/starhub/vendor/`，**不进** `~/.claude/skills`，由 starhub skill 按需加载 |
| **pc-home** | CLI、MCP、Docker、需要 GPU 的应用 | 用到时经 desk 在工程机器上安装和运行 |
| 远程读取 / 在线版 / 独立服务器 | 榜单、在线服务、代理面板 | 不落地 |

## 命令

```
starhub show <q>        # 查看项目详情和其中的 skill
starhub vendor [q...]   # 拉取 VPS 上的 skill
starhub sync            # 同步 star 列表
starhub outdated        # 检查上游更新
starhub bump <q>        # 审阅后升级 ref
starhub set <q> status active
starhub log <q> "备注"   # 记录使用情况
starhub index           # 重新生成 INDEX/README
```

## 目录

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
