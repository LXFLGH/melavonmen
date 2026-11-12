# Doc ↔ Code ↔ Wiki：状态、证据和增量同步

**区分目标与事实**：用户确认的需求与Doc是目标合同；真实源码/测试是现状证据；Wiki是实现事实的索引缓存。Doc和源码冲突时应记录差异、验证真实行为、确认目标，而不是直接选文档或直接选代码。

## 状态机（合同状态仅用于Doc）

1. `proposed`：建议/备选方案，未确认，不得擅自实施重大变更。
2. `approved`：目标合同已被用户或既定授权流程确认，可以据此开工。
3. `implemented`：代码已实现合同，但证据和文档复核仍在进行。
4. `verified`：目标合同、现有实现、测试与相关Doc/Wiki及索引一致且证据完备。
5. `deprecated`：弃用，但保留迁移/追溯记录。

**前置同步**：先读取Doc/Wiki索引和相关源文件 → 发现矛盾/更优设计 → 记录`doc/changes/<task>.json`与方案、必要时问用户 → **修正Doc目标合同**及Wiki中原本错误的现状事实 → 修改代码。禁止将计划的新签名提前记作Wiki的`current`。

**后置同步**：代码最终确定 → 测试 → 反向提取实际接口及数据 → **回写Doc中已经实施的合同、Wiki当前事实、模块index、根index、引用关系与验证记录** → 再复查一致性、测试及报告。中途发现问题同样暂停，先改Doc再继续。

| 真实变更 | 必须复核 |
|---|---|
| 函数/方法、形参/默认值、返回类型、异常 | Doc合同及模块，Wiki符号页、索引和调用者 |
| 数据结构、字段、序列化、存储协议 | Doc数据契约/兼容策略，Wiki结构、迁移及引用 |
| 模块依赖、继承、调用关系、文件路径 | Doc模块/架构，Wiki路由/跨模块引用 |
| 行为、状态机、边界条件、Bug修复 | Doc行为/验收，Wiki实际路径/陷阱/测试映射 |
| 版本、断言、行号、Hash、文件数 | 所有引用位置用当前命令重新核验 |

**差异范围**：先以git diff/源文件hash列`changed_source_paths`，结合Doc模块依赖及Wiki调用者形成`affected_contract_ids/affected_wiki_pages`。只读这些部分，不必全库扫描；但涉及公共API应扩展到调用者。

提交前保存机器可追踪结果：`observed_code_changes[], changed_doc[], changed_wiki[], validation_commands[], validation_results[], unverified[], sync_status`。当实际源码与目标合同仍不符时保持`implemented`以下状态，绝不能宣称`verified`。

## Native 增量辅助同步

在实施前用 native_cli impact <path-or-symbol> 扩展静态调用者/资源/继承反向影响，再将相关 Doc 合同标记为待复核（不是自动标 verified）。实施后 update、doctor、sync-status 对比真实文件哈希与 Wiki 中既存 source_path、签名和定位行号；机器判定只产生 tasks[]，业务语义仍须 Agent 逐条确认。现有状态机和权威性规则不变。
