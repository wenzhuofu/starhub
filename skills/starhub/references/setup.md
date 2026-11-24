# 首次设置

1. 用两句话告诉用户：starhub 会把 GitHub、小红书、B站的收藏拉到这台电脑上；GitHub 上的工具放进工具架，其他收藏整理成按主题写好的知识库，再生成一张网页；收藏不会上传到任何地方。
2. 问用户要接哪些平台：GitHub、小红书、B站，可以多选。
3. GitHub：运行 `starhub setup --github <用户名>`。不给用户名时，它会先试 `gh` 自动识别；识别不了再问用户。
4. 小红书和 B站借用用户 Chrome 里已有的登录，通过 [OpenCLI](https://github.com/jackwener/opencli) 读取：
   - 如果 `opencli --version` 运行不了，征得同意后安装：`npm install -g @jackwener/opencli@2.0.3`（需要 Node 20.18 以上）。
   - 请用户在 Chrome 里安装 OpenCLI 扩展（https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk），并在 Chrome 里登录小红书和 B站。
   - 运行 `starhub setup --sources github,xhs,bili`（只写用户选了的平台），再运行 `starhub doctor`，按每一行的提示逐项修好。
5. 运行 `starhub sync`，然后按 `references/ingest.md` 生成主题树（要让用户确认），完成第一次归类和编译。
6. 运行 `starhub page --open`。再告诉用户：用 Obsidian 打开 `~/.starhub` 这个文件夹，就能看图谱、反向链接，在手机上读，也能直接改笔记。他改过的笔记，AI 不会覆盖。
