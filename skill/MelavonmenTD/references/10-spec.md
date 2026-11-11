# 10 · spec 与单位

一份 spec 同时喂三条后端：cad（参数化 CAD 引擎）、blend（worker）、js（three.js）。
**它是唯一尺寸源**，模型里出现的任何数字都必须能追到它。

## 结构

```json
{
  "schema": "maker.spec/v1",
  "name": "ibm-5120",
  "unit_mm": 118,
  "refs": [
    { "id": "r1", "path": "ref/ibm5120-wiki.jpg",
      "claims": ["front panel inclined ~8deg", "drives: two vertical 8in slots"] }
  ],
  "parts": [
    { "name": "shell", "owner": "js", "bbox_mm": [446, 507, 203], "tris": 9000 },
    { "name": "panel", "owner": "blend", "src": "blend/panel.py" },
    { "name": "keycaps", "owner": "js", "recipe": "capGeometry(w,h)", "count": 84 }
  ],
  "scene": { "tone": "aces/0.95", "shadows": "pcf-soft", "env": "procedural-room" },
  "shots": [
    { "name": "hero", "cam": "auto", "margin": 0.12, "coverage": [0.25, 0.55] }
  ],
  "budgets": { "calls": 250, "tris": 150000, "texel": 1.2 }
}
```

## 单位

- `unit_mm` = 1 个场景单位等于多少毫米。**全项目只能有一个。**
- 换算只有一条公式：`scene_units = meters × 1000 / unit_mm`。
  例：446 mm 的机身，`unit_mm=118` → `0.446 × 1000 / 118 = 3.78`。
- 忘了这条的典型症状是把 GLB 拖进场景后大 8.4 倍（或小到看不见）。
  `glbcheck.mjs` 会先算这个比例再比 bbox。
- Blender 侧一律用米；导出 glTF 再用上面的公式缩放，不要在 Blender 里改单位。

## provenance：每个数字都要有出处

| 值 | 用法 |
| --- | --- |
| `ref:<id>` | 来自 `refs[]` 里的参考图/手册，必须写清是哪一条 claim |
| `measured` | 从已建模型里量出来的（`describe` / `probe`） |
| `assumed` | 拍脑袋的，必须给理由，并且会被写进 receipt 的 `assumptions[]` |

没出处的数字 **不许** 进 spec。这条防的是“看着差不多”累积成整体比例失真：
键盘缩 0.86、面板高度吃掉开孔、布局中心偏 36 mm，都是这么来的。

## bbox 与容差

`bbox_mm` 用区间而不是单值，默认容差取实机公差的 2 倍：

```json
"bbox_mm": { "x": [444, 448], "y": [506, 508], "z": [202, 204] }
```

闸门比的是 `describe` 量出来的世界 bbox（换算回 mm），不是设计值。

## 什么时候要新建 spec

- 换机器/换零件族 → 新建（不要在一个 spec 里塞两个产品）
- 只改观感（材质、光、机位）→ 不新建，改 `scene` / `shots`
- 只改一个尺寸 → 改 `parts[].bbox_mm` 与相关 `recipe` 参数，**重跑 S3**
