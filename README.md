# melavonmen

个人主页，托管于 GitHub Pages：https://lxflgh.github.io/melavonmen/

纯静态站点，零外部依赖（无框架、无 CDN），手写 HTML/CSS。

## 酸性设计（Acid Graphics）

站点视觉采用荧光黄绿、工业黑、银灰、少量紫色，配合超大字重、硬边框、网格纹理与机械编号。
- `css/style.css`：首页、作品、关于、文章的统一视觉系统。
- `heatmap.html`：保留原统计数据和 JS 交互，仅在原有 `<style>` 末尾追加 ACID GRAPHICS 视觉覆盖层。由外部工具重生成时需要重新附加该视觉覆盖层。
- 移动端响应式，支持 `prefers-reduced-motion`。


## 结构

```
index.html          首页（个人主页：入口卡片 + 文章列表）
games.html          游戏作品（作品卡片 + FCN 实机截图 + 后续作品占位）
heatmap.html        贡献热力图（自包含单页，保留 JS 数据逻辑，酸性主题内联）
about.html          关于
posts/              文章（独立 HTML，命名 YYYY-MM-DD-标题.html）
css/style.css       全站样式（heatmap.html 不使用）
assets/screenshots/fcn/godot/  FCN Godot 像素主题实机截图（PNG 原图）
```

## 页面约定

- 顶部导航顺序固定：首页 / 游戏 / 热力图 / 关于 / GitHub。
- 新增游戏作品：复制 `games.html` 里的 `<article class="game-card">` 整块，改标题、状态徽章、要点列表与 `meta-grid` 元信息；`nav-card is-placeholder` 是空位占位样式。
- FCN 作品条目可通过 `games.html#fcn` 直达；截图区为 `games.html#fcn-screenshots`，关于页的 FCN 介绍链接到此处。
- 截图使用原始 PNG，属于 2026-10-09 的 Windows Godot 历史实机画面，1200 × 760；按主页、农场、编辑器、任务、仓库、商店、股市、银行、手册、设置、剧情展示。截图不是 HTML demo，也不作为完整功能或动画验证的证据。
- 画廊使用静态 `figure` + 原图链接，标明画面名称、版本和捕获日期；首图直接加载，其余懒加载，保留宽高、替代文本和移动端单列布局，不引入脚本或外部依赖。更换截图时同步本文、图片说明与实际捕获日期。
- `heatmap.html` 由外部工具生成后整文件覆盖上传，保留顶部固定的「返回 Melavonmen」链接及数据和 JS 逻辑，发布时需保留尾部 Acid Graphics 样式覆盖。
  - 页面支持**多仓库切换**：顶部项目按钮在「全部项目 / FarmCodeNote / Artless」之间切换，全部区块（统计卡、日历、分布图、明细、tag）随之重算；合并视图里每条提交带项目标签。
  - 可用 `heatmap.html?p=<key>` 直达某个仓库（key 取 `fcn` / `artless` / `all`），默认展示全部项目。
  - 口径：日期取提交的 author date（+08:00）；行数分级用非零日 P25/P50/P75/P90 分位数；`整仓` 标记指单次新增 ≥ 5 万行。
  - **热力图是内嵌历史快照，不是实时 API 数据。** 截至 2026-10-18，HTML 内嵌的数据源仍是 2026-10-07 及之前的快照。更新页面文案不会补齐提交记录；要更新统计必须重新导出对应仓库 Git 数据、去重并重新生成页面，同时保留样式覆盖。

## 写新文章

复制 `posts/` 下任一文件为新文件（命名 `YYYY-MM-DD-标题.html`），改正文后在 `index.html` 的文章列表加一个 `post-card` 条目即可。

## 项目状态维护约定（2026-10-18）

- `games.html` / `about.html` / 首页项目简介以各项目当前 README、版本及验证文档为参考，明确区分**已运行/已验证**与**设计方向/未实现**。
- FarmCodeNote：Godot 原生 Windows 客户端已是主线（alpha0.3 起），旧 WebView 为历史版本；现有图片仍是 2026-10-09 的截图，不能代表后续 UI 改动。不要无证据称 macOS/Linux 等平台已经通过验收。
- Artless：当前仓库是黑白线稿地牢、卡牌与手绘卡牌技术原型；商旅/动态经济是游戏构想，不应写作已实现。
- 飞跃幻想乡：当前仓库已有 HD-2D 城镇漫游和分区加载原型；魔理沙扫帚飞行与完整探索游戏尚未由现有 README 证实。
- 开发日志保留其历史时间背景。要修改进度信息时一并检查首页、关于页、游戏页和本说明，修改截图时另核对实际图片与采集时间。
