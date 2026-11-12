# Melavonmen

Melavonmen 将本地源码索引、定义定位、调用图和改动影响分析接入 Codex 的 Doc/Wiki 工作流。3.1.0 使用仓库自带的 Python 索引和 MCP 服务。基础安装只需要 Python 3.10+ 和带 FTS5 的 SQLite，支持完全离线的结构索引。

## 安装到 Codex

解压发布包后进入 `melavonmen-3.1.0/`。从本仓库安装时进入 `skill/melavonmen/`。在该目录运行以下命令，然后在目标仓库打开一个新的 Codex 聊天。

```bash
python3 runtime/package_plugin.py
codex plugin marketplace add "$(pwd)"
codex plugin add melavonmen@melavonmen-local
```

用 `$melavonmen:melavonmen` 或直接要求查源码、找调用者、分析变更。Codex 通过 `melavonmen-index` MCP 加载 23 个工具和 5 个 prompts。插件从聊天的工作目录确定检索范围。移动源码目录后需要重新构建和注册本地市场。

## 终端和项目配置

```bash
python3 runtime/launch.py --cli index --project .
python3 runtime/launch.py --cli status --check-freshness --project .
python3 runtime/launch.py --cli search '索引刷新' --project .
python3 runtime/launch.py --cli definition discover_sources --project .
python3 runtime/launch.py --cli graph callers discover_sources --project .
python3 runtime/launch.py --cli impact --working-tree --project .
python3 runtime/launch.py --cli visualize --project . --output graph.html
```

默认结构模式使用 SQLite FTS5 BM25、符号匹配和静态调用关系。Git 仓库按分支记录内容快照，并遵守 Git 忽略规则。修改、新增、删除或重命名文件后可增量刷新，未变内容复用解析结果和向量。索引保存在项目的 `.melavonmen/index.sqlite3`。Git 用于分支、变更影响和提交过滤。普通目录也能进行索引和检索。

项目配置使用 `.melavonmen/config.json`。旧版 `.codebase-index/config.json` 中的常用检索设置可以作为配置回退。切换到新后端后运行一次 `index_codebase`，新后端会建立自己的索引。 `indexing.watchFiles` 默认开启，会检查已索引项目的变化。使用 `indexing.autoIndex: true` 可在首次查询时自动建库。

需要按语义检索或找相似代码时，选择混合模式并指定嵌入服务。以下示例连接本机运行的 Ollama。

```json
{
  "indexing": { "mode": "hybrid" },
  "embeddingProvider": "ollama",
  "ollama": {
    "baseUrl": "http://127.0.0.1:11434",
    "model": "nomic-embed-text"
  }
}
```

也可选 `openai`、`google` 或 `custom`。兼容端点在 `customProvider` 中填写 `baseUrl`、`model` 和可选的 `dimensions`。OpenAI 和 Google 可分别通过 `OPENAI_API_KEY`、`GEMINI_API_KEY` 读取凭据。配置外部服务时，选定的服务会收到用于生成向量或重排的源码片段。搜索支持目录、文件类型、块类型和 Git blame 过滤，也可通过 `search.fusionStrategy` 选择 `rrf` 或 `weighted`。调用 `add_knowledge_base` 可以把选定目录加入当前项目的检索范围。

GitHub 历史可在项目配置的 `repositoryHistory.repositories` 中按仓库启用，格式为 `{"repository":"OWNER/REPO","enabled":true}`。同步和远程 PR 查询使用本机已登录的 `gh`。缓存历史可离线搜索，并带原始链接。

调用图提供静态证据。Python 用 AST 提取，其他语言按源码结构和模块导入解析，无法确定的边会标记为未解析。动态分派、复杂宏、跨语言运行时调用，以及不同语言的解析深度需要结合源码与编译器核实。

## 验证

```bash
python3 -m unittest discover -s scripts/tests -v
python3 runtime/test_index.py -v
python3 runtime/test_codex.py -v
```

Codex 测试使用临时工作区及本机模拟嵌入端点。Doc/Wiki 校验命令见 [校验器说明](references/90-tooling.md)。
