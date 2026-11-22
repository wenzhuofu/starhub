# starhub INDEX

<!-- 由 bin/starhub index 生成，勿手改 -->
格式：`repo [类型·位置·状态] 作用 → 何时用 ⚔冲突`。详情：`starhub show <repo>`。

## 设计与前端审美
- pbakaus/impeccable [skill·vps·trial] 前端设计词汇与审查：design / redesign / critique / audit / polish / animate，覆盖网页、Dashboard、原生 App 和 DESIGN.md → 从零做或改造前端 UI，或要对现有界面做设计审查 ⚔hallmark
- Nutlope/hallmark [skill·vps·trial] 反 AI 味的新页面设计 skill，让网站看起来是设计出来的而不是生成的 → 新建网站或新页面；改既有设计必须显式 /hallmark redesign ⚔impeccable
- emilkowalski/skills [skill·vps·trial] 20 个动效与 UI 工艺 skill：animate、review-animations、gestures、apple-design、pick-ui-library、prototype、break-ui 等 → 加动效、审查交互手感、选 UI 库、做原型；可与 impeccable/hallmark 搭配
- VoltAgent/awesome-design-md [resource·vps·trial] 约 80 个知名品牌设计系统的 DESIGN.md（Airbnb、Apple、Airtable…），放进项目让 agent 照此风格出 UI → 需要明确的品牌风格参考时，挑一份复制进项目

## 图表与可视化
- tt-a1i/archify [skill·vps·trial] 架构/流程/时序/数据流/状态/ERD/类图/时间线等可探索 HTML 图，带校验，可导出 SVG/WebM → 代码库架构图、需要交互探索的技术图 ⚔diagram-design
- cathrynlavery/diagram-design [skill·vps·trial] 45 种编辑风格图表（架构、泳道、象限、雷达、组织图、飞轮…），自包含 HTML+SVG，不用 Mermaid → 文档、方案、汇报里的精美配图 ⚔archify

## 代码库理解
- colbymchenry/codegraph [tool·pc-home·backlog] 预建代码知识图谱，保存即自动同步，通过 MCP 供 agent 查询，减少 token 与工具调用 → 长期开发同一个代码库 ⚔graphify,Understand-Anything
- Graphify-Labs/graphify [tool+skill·pc-home·backlog] 代码（tree-sitter 本地解析）+ 文档 + SQL + PDF + 图片 → 可查询知识图谱；/graphify、graphify explain/path → 代码与文档、Schema、PDF 混杂的项目 ⚔codegraph,Understand-Anything
- Egonex-AI/Understand-Anything [skill+tool·pc-home·backlog] 代码 → 可交互知识图谱 + dashboard；understand / onboard / explain / diff / chat 等 9 个 skill，偏学习与上手 → 接手、学习陌生代码库，做 onboarding ⚔codegraph,graphify

## Agent 效率与约束
- DietrichGebert/ponytail [skill·vps·trial] “最懒的资深工程师”模式：用最小改动彻底解决问题；附 audit（全仓审计）、review（变更审查）、debt（捷径台账）等 → 任何编码任务防过度设计；仓库质量审计；代码审查
- headroomlabs-ai/headroom [tool·pc-home·backlog] 在工具输出、日志、JSON、RAG 片段送进 LLM 前压缩；库 / 代理（headroom proxy）/ MCP 三种形态 → 自建 LLM 应用或 agent 管线要降 token 成本

## 知识转 Skill
- virgiliojr94/book-to-skill [skill+tool·vps·trial] 把 PDF/EPUB/DOCX/HTML/MD 等书籍文档转成结构化 agent skill，提取框架、心智模型、原则与技巧 → 系统学习一本书，或把参考资料变成可复用的 skill

## Agent 基础设施
- stablyai/orca [app·vps·active] 多 agent 编排：用自有订阅并行跑 Claude Code、Codex 等，桌面/手机/远程运行时 → 多任务并行、远程驱动 agent（当前正在使用） ⚔t3code
- pingdotgg/t3code [app·none·backlog] 从任意电脑或手机控制 Claude Code、Codex 等 → 需要另一套远程控制 agent 的界面 ⚔orca
- HKUDS/CLI-Anything [tool+skill·pc-home·backlog] 给 GUI 软件生成 agent 可用的 CLI；CLI-Hub 已收录 69 款（Blender、GIMP、Kdenlive、OBS、Zotero、Obsidian、drawio…） → 要让 agent 操作某个桌面软件
- Panniantong/Agent-Reach [tool+skill·pc-home·backlog] 让 agent 读取和搜索 Twitter、Reddit、YouTube、B站、小红书、GitHub、V2EX 等，零 API 费用 → 调研、抓取社媒与社区内容
- router-for-me/CLIProxyAPI [tool·server·backlog] 把 Claude Code、Codex、Antigravity、Grok 等订阅型 CLI 包装成 OpenAI/Gemini/Claude 兼容 API → 需要用订阅额度对接只支持 API 的工具

## 信息监控与情报
- OpenGithubs/github-monthly-rank [resource·remote·active] GitHub 每月飙升榜 Top30，按 年/月.md 存放，每月 1 号更新 → 每月发现新项目
- sansan0/TrendRadar [app·pc-home·backlog] 多平台热点 + RSS + 定时联网搜索聚合，关键词/AI 筛选、AI 简报、多渠道推送，自带 MCP 服务 → 长期追踪某些话题、做个人信息流
- koala73/worldmonitor [app·hosted·backlog] 实时全球情报面板：新闻聚合、地缘政治、基础设施监控；另有 npx worldmonitor 终端面板与 MCP 工具 → 宏观态势感知
- bilawalsidhu/gods-eye-view [app·hosted·backlog] 浏览器里的 3D 地球卫星视角模拟器，叠加真实开源空间数据 → 空间数据可视化参考、演示

## 内容创作
- heygen-com/hyperframes [tool+skill·pc-home·backlog] HTML 渲染成视频的可编辑 AI 视频框架；skill 覆盖制作、CLI、素材、视频逆向重建（reverse-any-video）、幻灯片 → 做宣传片、讲解视频、字幕、可演示的幻灯片
- debpalash/VoiceStudio [app·pc-home·backlog] 本地版 ElevenLabs：声音克隆/设计、配音、转写、有声书，646 种语言；提供 REST API、MCP 与 skill → 配音、旁白、转写、有声书

## 专业领域
- anthropics/financial-services [skill·vps·trial] Anthropic 官方金融插件集：投行、股研、PE、基金行政等垂直插件，财报复盘、DCF、KYC、月结、对账等 agent 插件，以及 LSEG、S&P Global 合作插件 → 财务建模、估值、财报分析、投行材料
- google-research/timesfm [model+skill·pc-home·backlog] Google 时间序列预测基础模型，零样本即可预测；附 timesfm-forecasting skill → 销量、流量、业务指标预测

## 安全与逆向
- morluto/rea [tool+skill·pc-home·backlog] 一个 MCP 覆盖逆向工程：原生二进制、Electron/JS、固件、浏览器目标；还能为 web/Linux 应用构建 agent 环境 → 分析某个应用功能的实现原理（仅限有权分析的目标）

## 网络与运维
- MHSanaei/3x-ui [app·server·backlog] Xray 多协议代理服务器的 Web 管理面板（VLESS/VMess/Trojan/SS/WireGuard/Hysteria 等，多用户） → 自建网络代理服务器

_共 27 个项目，其中归档 0 个未列出。_
