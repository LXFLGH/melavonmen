# Melavonmen

Melavonmen 将本地源码检索、定义定位、调用图和改动影响分析接入 Doc/Wiki 工作流。Codex 插件使用锁定的 `open-codebase-index@0.38.2` 后端，保留该版本的 23 个 MCP 工具和 5 个 prompts。

## 安装到 Codex

解压发布包后进入 `melavonmen-3.0.0/`。从本仓库安装时进入 `skill/melavonmen/`。在该目录运行以下命令，然后打开一个新的 Codex 聊天。

```bash
python3 runtime/package_plugin.py
codex plugin marketplace add "$(pwd)"
codex plugin add melavonmen@melavonmen-local
```

需要 Python 3.10+、Node.js 22.13+，首次启动还需要 npm 或 Corepack 以及 npm registry 访问。Linux Codex Desktop 可使用随应用安装的 Node.js，也可通过 `MELAVONMEN_NODE` 指定 Node.js 可执行文件。首次启动按锁文件安装后端到 `$XDG_CACHE_HOME/melavonmen` 或 `~/.cache/melavonmen`。可以提前运行 `python3 runtime/launch.py --cli --help` 准备缓存。后续启动复用缓存。保留同名服务 `codebase-index` 的单个活动来源，以免旧插件和 Melavonmen 重复注册。

## 使用

在 Codex 中用 `$melavonmen:melavonmen` 或直接要求“找出源码中负责增量刷新的逻辑”“列出这个函数的调用者”。默认以当前聊天的工作区为检索范围。插件依赖本地市场构建目录，移动项目后请从新路径重新构建和注册。终端可以使用同一后端，在命令中把 `.` 换成目标仓库。

```bash
python3 runtime/launch.py --cli status --project .
python3 runtime/launch.py --cli index --project .
python3 runtime/launch.py --cli search '索引刷新' --project .
python3 runtime/launch.py --cli definition discover_sources --project .
python3 runtime/launch.py --cli graph callers discover_sources --project .
```

本项目的 `.codebase-index/config.json` 使用 `indexing.mode: structural`，无需嵌入模型即可使用关键词、定义和调用图。在其他仓库中可沿用原有 Codebase Index 配置；需要无模型模式时，把该设置合并到目标仓库的配置。需要语义检索和相似实现时，设为 `hybrid`，选择 Ollama、OpenAI、Google 或兼容端点，重新启动会话并为该模式建索引。使用外部嵌入或重排服务会按所选服务配置处理源码片段。GitHub 历史仍按仓库显式启用，并使用既有 `gh` 登录。

检索模式、嵌入模型和忽略规则见[上游配置](https://github.com/Helweg/open-codebase-index/blob/v0.38.2/docs/configuration.md)，工具及响应见[上游工具清单](https://github.com/Helweg/open-codebase-index/blob/v0.38.2/docs/tools.md)。Doc/Wiki 校验命令见 [校验器说明](references/90-tooling.md)。

## 验证

安装插件后可用下列命令复跑校验器和 Codex 端到端测试。混合检索测试在本机启动模拟嵌入端点。

```bash
python3 -m unittest discover -s scripts/tests -v
python3 runtime/test_codex.py -v
```
