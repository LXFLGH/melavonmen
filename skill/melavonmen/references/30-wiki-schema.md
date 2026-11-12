# Wiki：源码事实、渐进深度与符号路由

**Wiki只表述当前可从源码核查的事实。** Doc中的未来目标不得提前覆盖Wiki的实际签名。默认JSON索引+模块页，必要时用JSONL存大量符号、Markdown存解释；格式可更换但必须可解析和可寻址。

```text
wiki/
  index.json                  # 全部首方源文件清单、hash与路由
  <module>/index.json        # 该模块源码列表、按需深度页引用
  <module>/<file-id>.json    # 深度记录：类/函数/参数/返回/结构/调用
  crossrefs/index.json       # 可选按符号反向引用索引
  verification/index.json    # 覆盖率、编译/符号验证、过期信息
```

模板：`../templates/wiki-index.json`。路径一律相对仓库根（`sources[].path`）或相对wiki根（`modules[].index`, `pages[].page`, `task_routes[].read`）。把路径规则固定，禁止路径遍历和同名不同义的隐式路径。

## 解耦（一页一职责）

1. **一个wiki页只描述一个源文件**；`hpp+cpp`/头源成对允许合并单页，但必须用`related_sources[]`列全路径，不得顺手把同模块其他文件也塞进来。
2. **事实唯一副本**：签名、数据结构、调用关系只在所属页定义；其他页一律引用`<page>#<qualified_name>`，**复制正文即缺陷**（复制出来的那份必然先过期）。
3. **路由不承载细节**：根`index.json`与模块`index.json`只放清单、`sha256`、覆盖统计、`task_routes`，不得放结论或正文。
4. **不跨层混写**：Doc的合同/意图不抄进Wiki；Wiki的实际实现不写进Doc的期望段。
5. **拆分阈值**（任一超出即拆）：单页`>6KiB`、`declarations[]`超过40条、页内出现两个以上不相关主题、或描述一处变更需要同时改≥3页。
6. **可测判据**：改一个源文件时，期望受影响的Wiki页数为**1**（外加该模块索引的统计字段）。超过3页说明切分粒度错了——先改切分，再补内容。

## 可读性优先级：AI可读 > 机器可解析 > 人类可读

| 优先级 | 含义 | 具体做法 |
|---|---|---|
| 1 **AI可读**（最高） | 单页自洽、可定位、低token | 页首固定`page_id,purpose,source_path,source_sha256,revision`；每条声明带`qualified_name`与`line_start`；禁止“见上文/如前所述”式指代 |
| 2 机器可解析 | 结构可被脚本校验 | JSON/JSONL优先；Markdown只作短解释，二级标题顺序固定：职责→声明→结构→调用→副作用→错误路径→测试→风险→证据；表格/键值对优先于散文 |
| 3 人类可读（最低） | 排版美观、行文流畅、教程感 | 不得为它牺牲前两项；需要人读版本时另写Doc或导出阅读稿，**不塞进Wiki** |

**Markdown页的硬要求**：一级标题为`<page-id> — <purpose>`；连续超过10行无结构的自由散文视为不合格（改成表格/键值对/条目）；不写比喻、铺垫、“我们”式叙述；同一事实只在一个小节出现。

**验收**：随机抽3页检查——(a)页首字段齐全，(b)全部声明可定位到行号，(c)无`见上文/如前所述`，(d)单页≤6KiB。四项缺一即不通过；`validate_index`只能证明路由与覆盖，证明不了这四项。

## 两个不同的覆盖率

- **文件索引覆盖**：建立Wiki时，`sources[]`必须纳入100%的首方源码文件，记录`path,sha256,module_id,coverage`，`coverage=indexed|deep`；
- **深度分析覆盖**：按变更涉及的模块逐步生成源码细节页，`deep_sources`为当前完成深度分析的源码文件数，真实地报告例如`3/250`；
- 用户任务所触及的源码及影响接口必须优先深度检查并同步。可先有100%的文件路由，而不宣称有100%的符号/调用图覆盖；
- `total_sources == len(sources)`，`indexed_sources`应等于唯一、可访问路径数，`deep_sources`应等于覆盖状态为deep的文件数。

`validate_index` 用 Git 已跟踪文件独立核对文件覆盖率。普通目录按文件系统枚举。默认纳入已识别的源码后缀及自有测试，排除生成物、依赖、资产及 Doc/Wiki 目录。可在 `loc_scope.include_globs` 添加后缀或文件名，在 `loc_scope.exclude_globs` 排除具体路径。新增深度页请写入 `source_sha256`；校验器会核对该字段（若存在）和模块页记录的源码路径。

可选 `symbol_routes` 采用 `{qualified_name, page}`，其中 `page` 是已在模块中登记的 JSON 页路径，也可写为 `path#qualified_name`。同名符号可按页保留多条路由。

子索引`pages:[{source_path,page}]`，深度页推荐字段：`source_path,language,source_sha256,revision,purpose,declarations[],data_structures[],imports[],calls[],called_by[],inheritance[],side_effects[],error_paths[],tests[],hazards[],evidence[]`。
声明尽量记录：`qualified_name,kind,signature,parameters:[{name,type,default}],return_type,line_start,source_revision`；静态类型无法确定时标`unknown`，不得凭感觉补完。hpp+cpp可以合并单页并列出全部源路径，注意验证器基础版本按一个`source_path`逐页解析；复杂成对关系可通过`related_sources[]`扩展。

## 减少文档漂移成本

- 索引不可堆全部细节；根索引→模块索引→文件/符号页，避免Agent全库加载。
- 每个源文件存**文件内容SHA-256**而不是把项目每个文件绑定到全仓Commit SHA；源文件内容未变时其映射不应仅因其他文件提交而过期。
- 变更源码后，根据git diff、模块关联和调用者定位受影响页，修改相关合同和索引；不要求重新读取整个Wiki。
- 同步时只把已实现事实写入Wiki；未来设计留在Doc/contracts和Doc/changes。
- 动态语言/跨语言符号若无可靠解析器，只标`unverified`并附源码定位；文件哈希正确**不等于行为正确**。
