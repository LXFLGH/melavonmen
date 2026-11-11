---
name: MelavonmenTD
description: >-
  three.js + Blender 的 3D 制作与验收流水线。用 spec 驱动分件（cad / blend / js 三个 owner），
  六道闸门逐关产出 receipt，帧级度量（主体覆盖率、texel 密度、摩尔纹周期、draw call 预算），
  Blender 常驻无头 worker，glTF 回灌校验（单位 / bbox / 命名）。
  适用于用 three.js 建场景或产品可视化、复古硬件与工业件复刻、需要 Blender 建模或烘焙、
  或需要对某一帧做量化验收。触发词：做个 3D、three.js 建模、Blender 建模、复刻老机器、
  验收这一帧、渲染对不对、字为什么糊、draw call 太多。
version: 1.2.0
author: LXFLGH
---

# MelavonmenTD — 3D 制作与验收

包办「把东西建出来」和「证明它是对的」两件事。**几何真**靠 CAD 事实，**帧真**靠度量，
两者都不过不许交付。没有 receipt 的“看着不错”不算完成。

## 三条红线

1. **不用像素判几何。** bbox、断面、遮挡关系必须用 `probe` / `describe` 回答。
   截图只回答“这一帧的观感”。用截图找几何 bug 的代价见 `references/50-geometry-pitfalls.md`。
2. **不重写几何后端。** cad 件交给内置参数化 CAD 引擎，blend 件交给 Blender worker，
   js 件才写 three.js。出现第二份同一形状的实现即为设计错误。
3. **不碰用户的 Blender 会话。** 批量渲染只走 `blender --background` 的常驻 worker，
   只写自己的临时 .blend；绝不 `taskkill` 用户开着的 GUI 进程。

## 六道闸门

| 关 | 入口 | 度量（全部可断定） | 失败码 |
| --- | --- | --- | --- |
| S0 参考 | — | 每个尺寸有 `provenance: ref\|measured\|assumed` | `E_REF_MISSING` |
| S1 规格 | S0 pass | `unit_mm` 唯一；bbox 区间自洽；owner 全覆盖 | `E_UNIT_AMBIGUOUS` `E_OWNER_MISSING` |
| S2 分件 | S1 pass | 场景图节点 ⊇ spec.parts；命名稳定 | `E_PART_MISSING` |
| S3 几何真 | S2 pass | cad 件 verify=pass；js 件 bbox/断面自洽 | `E_GEOM_*` |
| S4 帧真 | S3 pass | coverage∈区间、texel≥1.2、period≥2px、calls≤预算 | `E_FRAME_*` |
| S5 交付 | S4 pass | 各份 receipt 的 `spec_hash` 相同 | `E_NOT_VERIFIED` |

分级 `basic / standard / strict`；被跳过的检查必须写进 receipt 的 `skipped[]`，不许静默通过。

## 按需读取

| 情况 | 必读 | 后续 |
| --- | --- | --- |
| 任何 3D 任务 | [10-spec](references/10-spec.md) | [20-ownership](references/20-ownership.md) |
| 决定谁建什么 | [20-ownership](references/20-ownership.md) | [60-blender-worker](references/60-blender-worker.md) |
| 出图 / 说“糊”“暗”“不对” | [30-frame-metrics](references/30-frame-metrics.md) | [40-shader-checklist](references/40-shader-checklist.md) |
| 几何看不见 / 被埋 / 穿插 | [50-geometry-pitfalls](references/50-geometry-pitfalls.md) | [70-troubleshooting](references/70-troubleshooting.md) |
| 报错码不认识 | [70-troubleshooting](references/70-troubleshooting.md) | — |

## 单回合状态机

`intake(参考入库) → spec(写 dims/parts) → build(分件) → describe(几何事实) →
frame(取景+度量) → verify(合并 receipt) → deliver(双 pass 才出文件) → memory`

- 只被要求“设计/评审”时停在 spec，不建模型。
- 只被要求“改观感”时走 frame 闸门，不动几何。
- 每次改完必须重跑同一组 `views`，否则前后不可比（`build.freeze` 不一致）。

## 常用命令

```bash
S=./scripts
node $S/doctor.mjs                                  # 环境体检
node $S/compile.mjs --spec maker.spec.json --out out/ # 校验与拆解 spec
node $S/cad.mjs --spec maker.spec.json --out out/    # 构建与验收 cad 件 (GLB)
node $S/glbcheck.mjs --glb out/part.glb --spec maker.spec.json --part panel # glTF 回灌校验
node $S/frame.mjs --url file:///…/index.html --root window.CRT.aio.group \
     --ready 'window.__crtReady===true' --texel 'screen=window.CRT.aio.screen:1.2' \
     --budget calls=250,tris=150000,mats=200 --json out/frame.json # 帧级度量
node $S/shot.mjs --url … --views shots/views.json --out shots/
node $S/compare.mjs --mask shots/hero.png --ref ref/ibm5120.jpg --json out/silhouette.json
```

## 错误码速查

| 码 | 含义 | 先做什么 |
| --- | --- | --- |
| `E_REF_MISSING` | 尺寸没有出处 | 补 `ref/` 或标 `assumed` |
| `E_UNIT_AMBIGUOUS` | 单位/基准不唯一 | 在 spec 里钉死 `unit_mm` |
| `E_OWNER_MISSING` | 零件没人认领 | 补 `owner` 或删件 |
| `E_PART_MISSING` | spec 里的件场景里没有 | 查命名，不猜位置 |
| `E_GEOM_BURIED` | 零件被包在壳体内 | 用 `probe` 打射线，别靠肉眼 |
| `E_GEOM_FACE_Z` | 贴在挤出件正面却算错前平面 | `depth + bevelThickness` |
| `E_FRAME_COVERAGE` | 主体在画面里过大/过小/被裁 | 改机位，不改模型 |
| `E_TEXEL_LOW` | 贴图在这帧被压缩 | 抬分辨率或拉近机位 |
| `E_PERIOD_MOIRE` | 固定周期花纹 < 2px | 上 `fwidth` 淡出 |
| `E_BUDGET_CALLS` | draw call 超预算 | 合并几何 / 复用材质 |
| `E_NOT_VERIFIED` | 缺 receipt 就想交付 | 回去跑关 |
