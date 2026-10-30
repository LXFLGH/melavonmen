# 素材生成与交付：一素材一文件（精灵表为例外）

**触发**：用户要求生成、绘制、渲染、导出、补齐或替换**素材图**（贴图、瓦片、图标、立绘、UI 元件、粒子、遮罩、法线、背景、天空盒面等），无论一次要一张还是几十张。

## 硬规则

1. **一素材一文件（默认）**。每个贴图素材默认是**独立文件**，路径即其唯一身份；一个文件内只允许出现**一个**素材对象。
2. **禁止隐性混装**。不得把**互不相关**的素材塞进同一文件：多主题图标拼版、UI 图集、contact sheet、“1024² 里摆 4×4 个图标靠坐标切图”一律不接受。
3. **精灵表是唯一常规例外**（见下节）：同一角色/同一动作的序列帧、或同一用途的图块集，可以合法地共存于一张图，但**必须**自描述、可定位到单帧、且保留逐帧源文件。
4. **单文件可独立加载**。除精灵表外，引擎/前端按单文件路径直接可用，不依赖运行期裁剪或外部坐标表。
5. **原图与交付物分离**。生成器原始输出（拼版、带白底、多主体）存 `assets/_raw/`，保留不删不改；交付图放 `assets/<category>/`。`_raw/` 不计入交付清单，也不得被运行时引用。
6. **新增不覆盖**。生成前检查目标名是否已存在；已存在的素材一律不覆盖、不重绘、不“统一风格化”，沿用 [60-safety-memory](60-safety-memory.md)。

## 精灵表（sprite sheet）：唯一的常规例外

游戏里常见的形态：**一张 PNG 里排多帧 + 一份 atlas 元数据**。它合法，因为引擎按元数据取值，单帧仍是可寻址实体。四条同时满足才算合规：

| # | 要求 | 不满足的后果 |
|---|---|---|
| 1 | 有 **atlas 元数据**：每帧 `name/x/y/w/h`，建议带 `pivot` | 无法取帧，等于交付一堆坐标不明的像素 |
| 2 | **保留逐帧独立源文件**（`source_files`），sheet 由它们合成 | 单帧不可替换/复用，等于把素材焊死 |
| 3 | 清单登记 `kind:"sprite_sheet"`、`sprites:<帧数>`、`atlas:<path>`、`source_files:[...]` | 校验器无法核对帧数与边界 |
| 4 | 帧数与 `sprites` 一致、帧矩形不越界、帧名唯一 | 运行时越界采样 / 取错帧 |

```json
{
  "id": "char_walk_sheet",
  "path": "characters/walk.png",
  "kind": "sprite_sheet",
  "sprites": 4,
  "width": 256,
  "height": 64,
  "atlas": "characters/walk.json",
  "source_files": ["characters/walk_00.png", "characters/walk_01.png",
                   "characters/walk_02.png", "characters/walk_03.png"],
  "sha256": "<64 hex>",
  "source": "ai-generated",
  "generated_by": "ImageGen"
}
```

```json
{
  "image": "characters/walk.png",
  "frames": [
    {"name": "walk_00", "x": 0,   "y": 0, "w": 64, "h": 64, "pivot": [32, 60]},
    {"name": "walk_01", "x": 64,  "y": 0, "w": 64, "h": 64, "pivot": [32, 60]},
    {"name": "walk_02", "x": 128, "y": 0, "w": 64, "h": 64, "pivot": [32, 60]},
    {"name": "walk_03", "x": 192, "y": 0, "w": 64, "h": 64, "pivot": [32, 60]}
  ]
}
```

**顺序不能反**：先出逐帧分立图，再合成 sheet。不允许“先让模型画一张多格图，再猜边界切”，因为切出来的边界是估的，接缝和透视都对不上；猜完还得人工修，成本比逐帧生成高。

## 命名与目录

```text
assets/
  _raw/                     # 生成原件，保留，不交付、不引用
  manifest.json             # 逐文件清单
  tiles/      grass.png  dirt.png  water_shallow.png
  characters/ walk_00.png walk_01.png … walk.png walk.json   # 帧 + 合成表
  icons/      icon_coin.png  icon_gear.png
  ui/         panel_frame.png  button_normal.png
  fx/         spark_00.png  smoke_00.png
```

- 小写 + 下划线 + ASCII，语义化名词；禁止 `final.png`、`final2.png`、`未命名.png`、`output(1).png`。
- 同一组素材尺寸/朝向/锚点一致，但除精灵表外**仍是多个文件**。
- 序列帧默认逐帧独立文件（`_00`、`_01`…）；需要 strip/sheet 时按上节补齐元数据与源文件。

## 逐文件清单

生成即登记，一个交付文件一条：

```json
{
  "schema_version": "melavonmen.assets/1",
  "root": "assets",
  "assets": [
    {
      "id": "tile_grass",
      "path": "tiles/grass.png",
      "kind": "tile",
      "sprites": 1,
      "width": 64,
      "height": 64,
      "alpha": true,
      "sha256": "<64 hex>",
      "source": "ai-generated",
      "generated_by": "ImageGen",
      "prompt": "<实际使用的提示词>",
      "used_by": ["src/render/tiles.cpp"]
    }
  ]
}
```

- 普通素材 `sprites` **必须为 1**；精灵表填**帧数**。这个字段是“一图一素材”的机器可读断言。
- `sha256/width/height` 要来自**实际文件**，不是估计值；`validate_assets.py` 会读图片头核对。
- `source`：`ai-generated|user|manual|external`；用户提供或外部解包得到的素材同样登记，但不受生成流程约束（见 [60-safety-memory](60-safety-memory.md)）。

## 其它打包：仍需用户明确要求

除精灵表外的任何多素材合图（多主题图标集、UI 图集、批绘制合图）都**不是默认交付**。要做时必须：

1. 决策落盘 `doc/decisions/<id>.json`：`user_confirmation: true`、原因、受影响合同与渲染路径。
2. **先有分立图，再合成**；不允许“先出一张图集再切图当交付”。
3. 清单里成员各自仍有条目与文件；合图条目用 `"kind": "atlas"` + `"atlas_of": [id...]` + `"user_approved": true`。

## 交付前自检（必须报数字）

| 检查 | 判据 |
|---|---|
| 文件数 == 素材数 | 清单条目数 == 交付目录内图片文件数（`_raw/` 除外） |
| 一图一素材 | 每个 `category` 至少目视抽检 1 个文件，确认只含 1 个素材 |
| 精灵表自描述 | `sprites` == atlas 帧数；帧矩形不越界；帧名唯一；`source_files` 全部存在 |
| 尺寸与声明一致 | `width/height` 与图片头一致，`validate_assets.py` 输出 `0 errors` |
| 可复现 | 逐文件 `sha256` 已记录且与文件一致 |
| 无隐性混装 | 除 `sprite_sheet`/已批准 `atlas` 外，文件名与清单不出现 `sheet/atlas/grid/tileset` |
| 原件在位 | `_raw/` 保留生成原图，未删除、未覆盖 |

## 常见错误（一律禁止）

| 做法 | 为什么不行 |
|---|---|
| 4 个不相关 UI 图标合成一张四宫格 | 图标无法单独替换/复用；属隐性混装，需批准 |
| 8 帧动画出 strip，**无 atlas** | 帧取不出来，等于交付坐标不明的像素 |
| 8 帧动画出 strip + atlas，但**没有逐帧源** | 改一帧要重出整条；违反例外第 2 条 |
| 三种材质放一张 PNG 靠 UV 分区 | 材质与文件不再一一对应，清单无法验证 |
| 用 `"sprites": 16` 把拼版写成合法 | 普通素材只允许 1；精灵表要 atlas 契约，不是改个数字 |
| 只交图集、分立原图丢失 | 不可逆，违反例外第 2 条 |

## 与其它文档的关系

- Doc：素材作为交付物时，合同需列出 `asset_id → path → 尺寸 → 用途`，精灵表额外记 `atlas` 与帧数，状态仍走 `proposed→approved→implemented→verified`。
- Wiki：登记“当前真实存在哪些素材文件及其引用点”，不写计划中的素材。
- 验证：涉及素材变更的回合把 `validate_assets.py` 纳入自检序列（[50-verification](50-verification.md)、[90-tooling](90-tooling.md)）。
