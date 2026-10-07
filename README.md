# melavonmen

个人主页，托管于 GitHub Pages：https://lxflgh.github.io/melavonmen/

纯静态站点，零外部依赖（无框架、无 CDN），手写 HTML/CSS。

## 结构

```
index.html          首页（个人主页：入口卡片 + 文章列表）
games.html          游戏作品（作品卡片 + 后续作品占位）
heatmap.html        贡献热力图（自包含单页，样式内联，独立于全站主题）
about.html          关于
posts/              文章（独立 HTML，命名 YYYY-MM-DD-标题.html）
css/style.css       全站样式（heatmap.html 不使用）
```

## 页面约定

- 顶部导航顺序固定：首页 / 游戏 / 热力图 / 关于 / GitHub。
- 新增游戏作品：复制 `games.html` 里的 `<article class="game-card">` 整块，改标题、状态徽章、要点列表与 `meta-grid` 元信息；`nav-card is-placeholder` 是空位占位样式。
- `heatmap.html` 由外部工具生成后整文件覆盖上传，只保留顶部固定的「返回 Melavonmen」链接与其 `.site-back` 样式，其余内容不要手改。

## 写新文章

复制 `posts/` 下任一文件为新文件（命名 `YYYY-MM-DD-标题.html`），改正文后在 `index.html` 的文章列表加一个 `post-card` 条目即可。
