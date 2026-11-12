# 代码检索与 Wiki 联动

插件通过自有的 `melavonmen-index` MCP 提供源码证据。只读导航直接使用下表。已知路径用定向读取，精确字面量或需要穷举时用 `rg`。

| 要解决的问题 | 工具 |
|---|---|
| 索引是否可用、是否需要建库 | `index_status`、`index_health_check`、`index_codebase` |
| 陌生模块从哪里读起 | `codebase_context`，首轮通常用 `tokenBudget: 600`、`limit: 5` |
| 按行为找路径或读取实现 | 只要位置用 `codebase_peek`，需要源码用 `codebase_search`，有参考代码时用 `find_similar` |
| 已知定义、调用者和调用路径 | `implementation_lookup`、`call_graph`、`call_graph_path`，同名符号用文件路径消歧 |
| 准备修改已知符号或检查分支和 PR | `codebase_edit_context`、`pr_impact` |
| 架构、代码社区及附加目录 | `architecture_context`、`code_communities`、知识库工具 |

索引缺失或源码已变时按需运行普通 `index_codebase`。查询前确认目标工作区和分支，刷新后抽查关键命中的当前源码。结构模式使用本地关键词和结构索引。混合模式提供向量检索和相似实现查询。图中的关系来自静态源码，动态分派和有歧义的目标需要补证。工具不可用或结果覆盖不足时，使用 Git、`rg` 和直接读取。

在 Doc/Wiki 实施任务中，用命中结果的仓库相对路径匹配 `wiki/index.json` 的 `sources[].path`，再按 `module_id` 和模块页的 `pages[].source_path` 定位 Wiki 页。用当前源码核实符号、行号、调用点及哈希，将事实同步到相应页。索引命中的历史讨论只用于解释决策来源。代码改变后刷新检索索引，并按[双向同步](40-contract-sync.md)检查涉及的合同与 Wiki 记录。

安装、模式配置及终端入口见[插件说明](../README.md)。
