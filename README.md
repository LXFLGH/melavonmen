# melavonmen

个人博客，托管于 GitHub Pages：https://lxflgh.github.io/melavonmen/

纯静态站点，零外部依赖（无框架、无 CDN），手写 HTML/CSS。

## 结构

```
index.html          首页（文章列表）
about.html          关于
posts/              文章（独立 HTML，命名 YYYY-MM-DD-标题.html）
css/style.css       全站样式
```

## 写新文章

复制 `posts/` 下任一文件为新文件（命名 `YYYY-MM-DD-标题.html`），改正文后在 `index.html` 的文章列表加一个 `post-card` 条目即可。
