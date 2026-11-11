# MelavonmenTD

three.js + Blender 的 3D 制作与验收流水线。给模型一套**可判定的收尾标准**：
几何用事实（bbox / 断面 / 射线），观感用数字（覆盖率 / texel 密度 / 周期 / 预算），
两边都出 receipt，缺一份不许交付。

与 `melavonmen` 的关系：那个管「文档先行 + 双向同步」的项目纪律，这个只管 3D 那一段，
共用同一套「证据优先」的脾气。

## 一分钟上手

```bash
S=./scripts

node $S/doctor.mjs                        # 环境体检（node / puppeteer / chrome / blender / cad）

# 对一个 three.js 页面量这一帧
node $S/frame.mjs --url file:///…/index.html \
  --root window.CRT.aio.group \
  --texel 'screen=window.CRT.aio.screen:1.2' \
  --budget calls=250,tris=150000,mats=200 \
  --json out/frame.json
```

输出是一张表 + 一份 `maker.receipt/v1`：

```
coverage 77.5%   rect 1347x921px
calls 169   tris 48966   geos 83   mats 114   tex 96 (17.6 MB)
texel screen: 3.11  (tex 1240px / screen 399px)
```

## 目录

| 路径 | 内容 |
| --- | --- |
| `SKILL.md` | 入口：三条红线、六道闸门、错误码速查 |
| `references/` | 按症状分的 7 篇（spec / ownership / frame-metrics / shader / geometry / blender / troubleshooting） |
| `scripts/` | harness / doctor / cad / compile / frame / shot / compare / glbcheck / install_harness |
| `mcp/` | 九个动词的 MCP 服务（stdio），只做路由与闸门校验 |
| `templates/` | `maker.spec.example.json`、`maker.spec.cad.example.json`、`views.example.json` |

## 设计取舍

- **不重写几何后端**：cad 件交给参数化 CAD 引擎，blend 件交给 Blender worker，js 件才写 three.js。
- **不用像素判几何**：截图只回答「这一帧的观感」，几何问题一律走 probe / bbox / 断面。
- **MCP 只做闸门**：能写成脚本的能力就写成脚本，MCP 只负责把调用方和脚本接起来。
