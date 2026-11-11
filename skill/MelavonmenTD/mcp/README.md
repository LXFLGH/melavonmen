# 接入 MCP

服务是 stdio JSON-RPC，提供九个标准工具，负责路由脚本能力与闭环判定闸门。

## 自动配置

直接运行配置脚本（支持 Antigravity / Claude / Cursor / Codex / Windsurf / Cline）：

```bash
python scripts/install_harness.py antigravity   # 为反重力配置
python scripts/install_harness.py claude        # 为 Claude 配置
python scripts/install_harness.py all           # 自动为本机所有 harness 配置
```

## 手动配置片段

在 Agent Harness 的 MCP 配置文件中添加 `melavonmen-td` 条目：

```json
{
  "mcpServers": {
    "melavonmen-td": {
      "command": "python",
      "args": ["<path_to_skill>/mcp/maker_server.py"]
    }
  }
}
```

## 先自检

```bash
python mcp/maker_server.py --list
```

能打印九个工具即正常。逐个调用里最常用的是 `maker_frame` 与 `maker_cad`。

## 为什么是九个动词

- `doctor` / `spec` / `cad` / `frame` / `shot` / `compare` / `glbcheck` 是**脚本能力**，MCP 负责标准化调用与参数转发；
- `verify` / `deliver` 是**闸门**，必须在服务端判，不能由调用方自称通过。
- 几何事实（bbox/genus/闭合性）由内置 CAD 引擎与三维分析器保证。
