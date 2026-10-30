# 需求编译：从自然语言到可追踪合同

只有提示词/无工程证据时，先生成`normalized_prompt`而非直接写实现；检查实体指代、范围边界、输入输出、异常、平台/依赖、性能、安全、权限、验收、矛盾、隐含前提和迁移成本。

建议把结构化结果放入`doc/requirements.json`（创建正式Doc之前可先在会话中输出草案）。参考`../templates/requirements.json`：

- `mode`: `prompt_only|doc_only|doc_then_execute|implementation`，由用户要求决定；
- `normalized_prompt`: 不加入未经用户同意的要求；
- `requirements[]`: 每条独立ID、优先级、验收条件、来源；
- `issues[]`: `id/type/evidence/impact/blocking/options/question/resolution`；
- `assumptions[]`: 仅非阻断假设，含回滚说明；
- `acceptance[]`: 可测试的完成条件。

对关键歧义要向用户询问，而不是偷选一个“最佳方案”；方案优化涉及行为、兼容、数据迁移或架构偏移时，提出代价并请用户选择。无法回答的不阻断问题可做明确记录，绝不能把`assumed`标为`confirmed`。

**入口阶段**：只要求优化提示词 → 交付优化稿，不创建工程；只要求Doc → 关键问题澄清后构建可解析Doc/索引便停止；要求Doc+实施 → Doc先落盘并审核后才编写代码。没有项目访问权限时交付草案并说明未落盘，不宣称已经执行。

**不重复问**：先检查本轮对话及项目既有决策；用户已确定的数值和约束不应被重新包装成问题。输出尽可能聚合与架构直接相关的阻断问题。
