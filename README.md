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
games.html          游戏作品（作品卡片 + 后续作品占位）
heatmap.html        贡献热力图（自包含单页，保留 JS 数据逻辑，酸性主题内联）
about.html          关于
posts/              文章（独立 HTML，命名 YYYY-MM-DD-标题.html）
css/style.css       全站样式（heatmap.html 不使用）
```

## 页面约定

- 顶部导航顺序固定：首页 / 游戏 / 热力图 / 关于 / GitHub。
- 新增游戏作品：复制 `games.html` 里的 `<article class="game-card">` 整块，改标题、状态徽章、要点列表与 `meta-grid` 元信息；`nav-card is-placeholder` 是空位占位样式。
- `heatmap.html` 由外部工具生成后整文件覆盖上传，保留顶部固定的「返回 Melavonmen」链接及数据和 JS 逻辑，发布时需保留尾部 Acid Graphics 样式覆盖。
  - 页面支持**多仓库切换**：顶部项目按钮在「全部项目 / FarmCodeNote / Artless」之间切换，全部区块（统计卡、日历、分布图、明细、tag）随之重算；合并视图里每条提交带项目标签。
  - 可用 `heatmap.html?p=<key>` 直达某个仓库（key 取 `fcn` / `artless` / `all`），默认展示全部项目。
  - 口径：日期取提交的 author date（+08:00）；行数分级用非零日 P25/P50/P75/P90 分位数；`整仓` 标记指单次新增 ≥ 5 万行。

## 写新文章

复制 `posts/` 下任一文件为新文件（命名 `YYYY-MM-DD-标题.html`），改正文后在 `index.html` 的文章列表加一个 `post-card` 条目即可。
