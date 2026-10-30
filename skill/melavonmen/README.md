# melavonmen v2.3.1 · release bundle

此目录是安装到私有仓库 `agent-memory/skill/melavonmen/` 的**增量覆盖包**，包含精简 SKILL.md、按需加载参考规则、机器模板和实际可运行的标准库 Python 校验器。

## 本版变更（v2.3.1）

- **精灵表（sprite sheet）明确为唯一常规例外**，并给出可校验契约：`kind:"sprite_sheet"` + `sprites:帧数` + `atlas:<json>`（帧名/x/y/w/h[/pivot]）+ `source_files:[逐帧图]`。四条缺一即不合格；其余打包（多主题图标集、UI 图集）仍需用户批准。
- `validate_assets` 支持精灵表：帧数须等于 `sprites`、帧矩形不得越界、帧名唯一、`source_files` 必须存在；普通素材仍强制 `sprites == 1`。
- 规则文本去掉了自相矛盾的“禁止精灵表 vs 精灵图除外”，改为单一表述；`00-routing`、`50-verification`、`60-safety-memory`、`90-tooling` 同步。

## v2.3.0

- **Wiki 解耦与可读性优先级成文。** 新增：一页一源文件、事实唯一副本（跨页只引用 `page#symbol`）、索引不承载细节、拆分阈值（>6KiB / >40 declarations / 需同时改 ≥3 页即拆）；可读性排序明确为 **1 AI 可读 → 2 机器可解析 → 3 人类可读**，人类排版美观排最后。见 `references/30-wiki-schema.md`。
- SKILL.md 规则 5 从“最小上下文”升级为“最小上下文 + 解耦”，写入上述两条优先级；建 Wiki 的入口话术同步。

## v2.2.0

- **新增硬规则：素材图必须解耦。** 用户要求生成素材图时，每个贴图/图标/立绘/瓦片/序列帧必须单独一个文件；**禁止多个素材保存在同一个文件中**（图集、精灵表、动画条、多宫格拼版、contact sheet 一律不接受）。细则见 `references/65-asset-delivery.md`。
- 新增 `scripts/validate_assets.py`：核验素材清单 `sprites == 1`、路径、文件存在性、声明尺寸与图片头（PNG/JPEG/GIF/BMP/WebP）一致、sha256 一致，并把未登记图片报为 warning；已批准图集需 `user_approved: true` 且保留分立原图。
- 路由、安全红线、验证门禁、提示词模板、工具说明同步更新；测试从 8 例增至 14 例。

## 安装到已有仓库

在本地克隆并进入 `agent-memory` 后，把本包目录内的文件覆盖复制到仓库的 `skill/melavonmen/`，保留其他仓库文件：

```bash
cp -R /path/to/melavonmen-v2.2/. skill/melavonmen/
python -m unittest discover -s skill/melavonmen/scripts/tests -v
git add skill/melavonmen
git diff --cached --stat
git commit -m "feat(melavonmen): v2.2 one-asset-per-file delivery contract and asset validator"
git push origin main
```

如果用 PowerShell，可用 `Copy-Item -Recurse -Force` 替代 `cp -R`。提交前检查 `git diff --cached`。

## 使用检查器

```bash
python skill/melavonmen/scripts/validate_index.py --project /path/to/game-project
python skill/melavonmen/scripts/validate_schema.py --project /path/to/game-project
python skill/melavonmen/scripts/validate_symbols.py --project /path/to/game-project
python skill/melavonmen/scripts/validate_assets.py --project /path/to/game-project
python skill/melavonmen/scripts/detect_doc_drift.py --project /path/to/game-project --base HEAD
```

仅支持Python AST形式的函数签名静态核对。其他语言仅进行源码SHA层面的过期检测，不能假称其语义通过验证。素材检查能证明“清单与文件一致、每项声明只含一个素材”，**不能**从像素内容证明一张图里没塞多个素材 —— 交付前仍需按类别目视抽检。使用wiki需根据模板先建立真实来源索引和SHA；模板里的占位字段须替换。
