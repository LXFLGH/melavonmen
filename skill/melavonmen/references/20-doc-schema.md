# Doc：意图、契约、决策和变更记录

Doc回答**预期应该如何**；Wiki回答**代码现在是什么**。默认机器友好的JSON，文本推理可用Markdown，符号流水可用JSONL。所有文件必须在根`doc/index.json`或其子索引中可被找到；不得让复杂合同堆成一份超长Markdown。

```text
doc/
  index.json                 # 根task_routes + manifest
  requirements.json          # 需求编译结果
  project.json               # 目标、架构、上下游数据流、依赖、非目标
  modules/<id>.json          # 职责/源码范围/公开接口/交叉依赖
  contracts/<id>.json        # 行为、结构、签名、返回类型、异常、验收
  decisions/<id>.json        # 取舍、选择、用户确认和风险
  changes/<task-id>.json     # 状态机、代码/文档影响面、证据、同步记录
  verification/index.json    # 验收路由、可复现验证
```

样板：`../templates/doc-index.json`、`../templates/requirements.json`。总索引包含`schema_version,project,source_revision,manifest,task_routes,unresolved`；manifest的每个条目有唯一ID和相对路径，task_routes读路径相对`doc/`。

## 强制字段与一致性

- 模块：`id, responsibilities, source_paths[], entrypoints[], public_symbols[], data_structures[], dependencies[], related_contracts[], related_wiki[]`。
- 合同：`id, status, input_schema, output_schema, errors, invariants, preconditions, postconditions, acceptance_tests, version`；`status`只可为`proposed|approved|implemented|verified|deprecated`。
- 函数接口：`qualified_name, parameters:[{name,type,default}], return_type, errors, version, source_evidence`；源码不存在时只标为**计划中的**签名。
- 变更：`baseline_revision, target_contracts[], affected_source_paths[], decisions[], planned_doc_changes[], implementation_changes[], observed_code_changes[], verification[], sync_status`。
- 决策：`options[],chosen,tradeoffs[],user_confirmation,affected_contracts[]`；不允许把“我觉得更好”覆盖掉用户已确认的行为要求。

Doc中的`status`表示该目标合同的进度，不是Wiki事实：**先提出→批准→实现→证据验证**。设计阶段可以标`approved`，但未实际实现绝不能标`implemented/verified`。

分片原则：按模块/合同/任务，建议单页4–8KiB；过长拆成`api/data/runtime/tests`等子页，父索引做路由。唯一权威事实只在一个位置，其余引用稳定ID/路径；避免重复搬运源码。路径/签名/行号/数字带来源和验证修订，过期证据显式标记。

创建流程：先只读事实 → 根index与project最小骨架 → 当前需求的合同/模块/变更单 → 验证可解析及引用有效 → 才允许代码实施。用户只要Doc时停在文档验证。
