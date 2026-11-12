---
name: melavonmen
description: >-
  用于理解陌生仓库、按含义查源码、定位定义、追踪调用关系和分析代码变更影响。
  也用于需求编译、按 Doc 实施、核验并同步 Wiki，以及按一素材一文件交付素材图。
metadata:
  version: "3.1.0"
  author: LXFLGH
---

# melavonmen — AI-first Agent Work Stream

## 永久不变的规则

1. **先识别输入**，不猜用户的交付范围。仅提示词 → 优化、检验歧义/矛盾/缺口，影响结果的关键问题先问清楚。只要Doc则只建Doc；要求Doc后执行才继续实施。详见 [任务路由](references/00-routing.md)、[需求编译](references/10-prompt-audit.md)。
2. **按任务选源码证据**。纯代码导航按[代码检索](references/35-code-search.md)直接查源码。实施任务先读已有 Doc/Wiki 的相关合同，再对照当前源码。没有文档时，按[任务路由](references/00-routing.md)建立实施所需的文档。
3. **设计先于源码**。当前Doc是目标合同，Wiki是经验证的**现有实现事实**。想改逻辑时先更新Doc、决策/变更记录；不能提前把Wiki里的“当前签名”写成尚未实现的未来签名。实施中发现问题也要先改Doc（与相关Wiki事实纠错），再继续写码。
4. **双向同步**。代码完成后以真实源码与测试为证，回写受影响的Doc、Wiki、索引，特别是数据结构、函数签名、形参、返回类型、依赖、行为、错误、版本；同回合跑校验。不能口头宣布“零漂移”。详见 [双向同步](references/40-contract-sync.md)。
5. **最小上下文 + 解耦**。Doc/Wiki**尽可能解耦**：一页一职责（一个源文件或一组明确符号），事实只在唯一位置有权威副本，跨页只引用`path#symbol`、不复制正文；根`index.json`路由，按需读页。Wiki的**源码文件索引覆盖100%**，深度符号/调用图**按受影响面渐进完成**；两种覆盖率不得混淆。Wiki文本**以AI可读优先**（1 AI可读 → 2 机器可解析 → 3 人类可读，人类排版美观排最后）：JSON/JSONL为主，Markdown只作短解释且版面固定、声明可定位到行号，不得为人类观感牺牲可寻址性与token效率。详见 [Wiki结构](references/30-wiki-schema.md)。
6. **保护资产与并发隔离**。不得擅自删除/替换用户、AI或人工素材；破坏性操作列清单并获确认；凭据不入日志或提交；一个文件一次只允许一个写入者；用户可见文案走i18n。测试以`0 failed`为通过条件；未经运行不得宣称通过。
7. **素材图必须解耦（一素材一文件，精灵表除外）**。默认每个贴图/图标/立绘/瓦片是**独立文件**，禁止把互不相关的素材塞进同一文件（多主题拼版、UI 图集、contact sheet、靠坐标切图）。**精灵表（sprite sheet）是唯一常规例外**：同一动作的序列帧、同一用途的图块集允许一张图承载多帧，但必须 ① 配 atlas 元数据（帧名+矩形+pivot）；② 保留逐帧独立源文件；③ 清单登记`kind:"sprite_sheet"`、`sprites:帧数`、`atlas`、`source_files`；④ 由分立帧合成，不得先出表再猜边界切图。其余打包仍需用户明确要求。详见 [素材交付](references/65-asset-delivery.md)。

## 按需读取（本文件是入口，不假定子文件自动加载）

| 情况              | 必读                                                             | 后续按需                                               |
| --------------- | -------------------------------------------------------------- | -------------------------------------------------- |
| 所有任务            | [00-routing](references/00-routing.md)                         | [60-safety-memory](references/60-safety-memory.md) |
| 仅提示词/新需求        | [10-prompt-audit](references/10-prompt-audit.md)               | [20-doc-schema](references/20-doc-schema.md)       |
| 新建/审查Doc        | [20-doc-schema](references/20-doc-schema.md)                   | [40-contract-sync](references/40-contract-sync.md) |
| 大项目建Wiki/深度补页   | [30-wiki-schema](references/30-wiki-schema.md)                 | [40-contract-sync](references/40-contract-sync.md) |
| 查源码、调用链或改动影响 | [35-code-search](references/35-code-search.md)                 | [30-wiki-schema](references/30-wiki-schema.md) |
| 有Doc/Wiki并要修改源码 | [40-contract-sync](references/40-contract-sync.md)             | [50-verification](references/50-verification.md)   |
| 生成/补齐/替换素材图     | [65-asset-delivery](references/65-asset-delivery.md)           | [60-safety-memory](references/60-safety-memory.md) |
| 同步/测试/合并        | [50-verification](references/50-verification.md)               | [90-tooling](references/90-tooling.md)             |
| 多Agent并行        | [80-agent-collaboration](references/80-agent-collaboration.md) | [40-contract-sync](references/40-contract-sync.md) |
| 复用提示词模板         | [70-prompt-templates](references/70-prompt-templates.md)       | —                                                  |

## 单回合状态机

`classify → read project indexes & evidence → requirement audit → resolve blockers → Doc proposed/approved → implement (only if requested) → asset delivery check (one file per asset, manifest + hash) → tests → Wiki actual + Doc verified sync → index/schema/symbol/asset/drift checks → memory → commit`。

- 仅需评审、提示词或文档时，在相应阶段停止；未授权时不能越级编码。
- 需求/架构改动在Doc里标`proposed`→`approved`；代码落地后标`implemented`；源码/测试/文档核验后才标`verified`。Wiki事实字段永远只描述当前可证实的实现。
- 工具检查会有局限（当前跨语言语义验证并不完整），应明确报告`warnings/unverified`，不能把哈希匹配冒充语义正确。
- 素材交付的完成标准是“文件数 == 素材数、每文件只含一个素材、清单与图片头/哈希一致”；交付一张拼版图不算完成。
