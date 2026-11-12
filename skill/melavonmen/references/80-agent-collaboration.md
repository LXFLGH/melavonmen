# 多Agent并发：所有权、合并与交接

## 工作分配

主Agent先确定源文件、Doc合同、Wiki子页和测试的影响图，然后为子Agent建立`task_id,owner,branch,owned_source_paths[],owned_doc_paths[],owned_wiki_paths[],dependencies[],completion_gate`。

- 同一个源码文件或Doc/Wiki页不能多Agent并发写入；交叉依赖由主Agent协调或串行化。
- 全局`doc/index.json`及`wiki/index.json`由单一协调Agent负责最终合并，或通过确定性的索引生成器统一重建；子Agent修改模块子索引与约定的自身页。
- 子Agent仅提交自己负责的路径、证据和结果；主Agent合并前检查API、数据结构、合同的互斥性与共享调用者的兼容性。
- 合并时若已有其他人改动，先重新拉取与比较最新文件/哈希，不使用强制覆盖，不能悄悄丢弃别的Agent修改。

## 交接包（机器优先）

`task_id, state, source_revision, proposed_contracts, approved_contracts, changed_sources, changed_doc, changed_wiki, index_paths, tests, unresolved, unverified, next_actions`。

仅交接引用和最小上下文，必要时新Agent再读目标模块Doc/Wiki，避免复制几万token的聊天历史。审计结果的`unverified`不可变为`verified`只因Agent交接完成。

## Native 并发索引

每个 Worktree/工作区在 .melavonmen/ 下维护自己的 SQLite（WAL + busy_timeout + IMMEDIATE 事务），即使共享同一 Git 仓库也不能将其他分支缓存覆盖到当前工作树。子 Agent 只维护自己 Worktree 的可重建缓存、代码、合同和审计证据；父 Agent 统一合并源码/Doc/Wiki 后在合并工作区执行 update→audit→sync-status。数据库异常运行 doctor；rebuild 构建临时新数据库并保留旧数据库备份，禁止无证据强行删除用户已有数据。
