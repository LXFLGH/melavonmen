# 内置可执行检查器与范围说明

本Skill携带五个CLI入口（Python 3.10+，仅标准库）：

```bash
python scripts/validate_index.py --project /path/to/project
python scripts/validate_schema.py --project /path/to/project
python scripts/validate_symbols.py --project /path/to/project
python scripts/validate_assets.py --project /path/to/project [--manifest assets/manifest.json]
python scripts/detect_doc_drift.py --project /path/to/project --base HEAD
python -m unittest discover -s scripts/tests -v
```

注意：上面`scripts/`是**Skill包内的脚本路径**；若在项目中从别处运行，写绝对路径或先切换到Skill脚本目录。`--project`必须指向含`doc/`/`wiki/`及源文件的项目仓库根。

| 命令 | 真正可验证的事项 | 目前不能证明的事项 |
|---|---|---|
| `validate_index` | 根任务路由/清单文件存在、路径不越界、模块/深度页、源文件覆盖统计一致 | Wiki语义真实性 |
| `validate_schema` | 索引必要字段、合同状态、SHA格式与manifest ID合法性 | 所有自定义JSON Schema的完全正确性 |
| `validate_symbols` | Wiki清单源码SHA-256匹配；Python AST解析的函数/类签名及定位行号 | JS/TS/C++/C#等语言的函数签名及任何业务行为；会明确产生warning/unverified数 |
| `validate_assets` | 素材清单可解析、普通素材`sprites==1`、精灵表`sprites`==atlas帧数且帧矩形不越界/帧名唯一/`source_files`存在、路径不越界且文件存在、声明尺寸与实际图片头（PNG/JPEG/GIF/BMP/WebP）一致、sha256匹配、未登记图片与命名可疑项 | **一张图里是否真塞了多个不相关素材**（像素级内容无法静态判定，只能靠清单/命名+人工目视抽检）；pivot 是否落在角色脚底、帧与帧是否对齐等视觉质量 |
| `detect_doc_drift` | Git差异中哪些已有源码SHA过期、哪些新源码不在Wiki清单、哪类文档有候选更新 | 静态无法证明的Doc业务语义；仅warning的“未更新Doc”需人工判断 |

CLI统一输出JSON（`ok,errors,warnings,stats,details`），发现确定错误返回退出码1；没有确定错误返回0，即使存在warnings也不能宣称全部语义验证完成。不存在Doc或Wiki时按路由决定是否先创建，非编码的提示词阶段无需运行。`git diff`默认以`HEAD`为基线，使用其他比较基线时明确传`--base <revision>`。

## 例子：素材清单（一素材一文件）

`assets/manifest.json`按[素材交付](65-asset-delivery.md)的字段登记，清单`root`相对项目根，条目`path`相对`root`。`validate_assets`会拒绝：普通条目`sprites != 1`、精灵表缺`atlas`/`source_files`、帧数与`sprites`不符、帧矩形越界或帧名重复、重复路径、越界路径、缺失文件、尺寸/hash不符。除`kind:"sprite_sheet"`外，多素材合图仍需`kind:"atlas"` + `user_approved: true`。对`assets/`下未登记的图片只报warning，须人工归类或补登记。像素内容无法静态证明“一图一素材”，交付前仍需按类别抽检。

## 例子：Wiki根索引

`wiki/index.json`维护：`sources:[{path,sha256,module_id,coverage}]`、`modules:[{id,index}]`、`task_routes`、`total_sources`、`indexed_sources`、`deep_sources`。相同项目的全部首方源码须在`sources[]`登记；运行前应实际计算sha256。

## 待升级的解析能力

该版本不自带TS/C++/C#全语言AST解析器，不能将源码文件hash当成函数语义审计的替代。具体项目可加基于TypeScript Compiler API、Clang、Roslyn、Tree-sitter的适配器，在通过验收后接入`validate_symbols`；之前将非Python结果标为`unverified`。此限制必须在交付报告中披露。
