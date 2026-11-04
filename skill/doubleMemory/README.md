# Double Memory

一个面向 DeepSeek Harness 的持久记忆插件：把身份、长期记忆、每日笔记、会话原文和图片保存在一个普通文件夹里，并同时提供模型工具与图形化设置页面。

## 目录结构

默认根目录是 `~/.dsh/memory`（Windows 上通常是 `C:\Users\<你>\.dsh\memory`），可以在设置里改成任意绝对路径。

```text
memory/
├── soul.md                  # 价值观、语气、长期原则
├── IDENTITY.md              # 名字、角色、与用户的关系、边界
├── MEMORY.md                # 长期事实索引
├── date/
│   └── 2026-11-04.md        # 每日具体记忆，文件名固定为 yyyy-mm-dd.md
├── session/
│   └── 2026-11-04.json      # 当日会话归档，文件名固定为 yyyy-mm-dd.json
└── pic/
    ├── photo/               # 照片
    ├── meme/                # 表情包
    └── image/               # 会话图片；session 里的 <img src> 指向这里
```

`session/YYYY-MM-DD.json` 保存为可读 JSON：

```json
{
  "schema": 1,
  "date": "2026-11-04",
  "updatedAt": "2026-11-04T15:36:44+08:00",
  "entries": [
    {
      "id": "session-abc:42",
      "seq": 42,
      "sessionId": "session-abc",
      "date": "2026-11-04",
      "time": "2026-11-04T15:36:44+08:00",
      "speaker": "user",
      "label": "用户",
      "text": "看看这张图",
      "images": ["pic/image/2026-11-04-1a2b3c4d5e6f.png"],
      "html": "用户：看看这张图<img src=\"pic/image/2026-11-04-1a2b3c4d5e6f.png\">"
    }
  ]
}
```

同一天有多个会话时，所有会话的条目都写入同一个日期文件，用 `sessionId` 区分。图片相对路径以记忆根目录为基准，统一放在 `pic/image/`。

## 模型工具

插件注册一个 `memory` 工具，通过 `action` 覆盖读、写、改、删：

| action | 作用 |
| --- | --- |
| `read` | 读取 `soul`、`identity`、`memory`、`date`、`session`、图片元数据或 `file` |
| `list` | 列出核心文件、每日笔记、会话归档和相册文件 |
| `search` | 在核心文件、`date/`、`session/` 中做大小写不敏感搜索 |
| `write` | 覆盖写入核心文件、日期笔记、会话 JSON 或相对路径文件 |
| `append` | 追加到核心文件、日期笔记或相对路径文件 |
| `edit` | 精确文本替换，支持 `replace_all`；改 session JSON 后会校验 JSON 合法性 |
| `delete` | 删除日期笔记、会话归档、图片或文件；删除三个核心文件需要 `confirm: true` |
| `capture` | 手动追加一条会话记录，支持文本和图片 |
| `add_image` | 把已有图片复制到 `pic/photo`、`pic/meme` 或 `pic/image` |
| `init` | 创建目录与三个核心文件（已存在则不覆盖） |

`target` 可选：`soul`、`identity`、`memory`、`date`、`session`、`photo`、`meme`、`image`、`file`。

示例：

```text
memory(action="read", target="memory")
memory(action="write", target="date", date="2026-11-04", content="# 今天\n\n- 学会了 ...")
memory(action="edit", target="soul", old_text="语气：直接", new_text="语气：温和而直接")
memory(action="capture", speaker="user", text="记住这个偏好", images=["pic/image/photo.png"])
memory(action="add_image", target="meme", source_path="C:/Users/me/Pictures/smile.png")
memory(action="search", query="偏好")
```

所有路径都相对于记忆根目录；`../`、绝对路径和盘符路径会被拒绝，核心文件删除必须显式确认。

## 图形化设置

打开 Harness 的 **Settings → Memory**（设置 → 记忆）。页面有两个页签：

- **全局**：默认记忆文件夹、自动归档、是否归档助手回复、是否归档子代理会话、是否复制图片、是否把记忆注入系统提示、提示预算。
- **会话覆盖（非全局）**：针对某个 `sessionId` 覆盖启用状态、自动归档、助手回复、提示注入、记忆文件夹和备注；留空字段继承全局值。

保存通过 Harness 的 settings 文档写入当前 profile，全局配置写入插件条目（entry id 为 `memory`），会话覆盖保存在该条目的 `sessions` 字段中。设置页面使用主题 token，自动跟随浅色/深色主题。

## 自动归档

当全局或会话级 `autoCapture` 开启时，插件监听 `session/event`：

- 只归档真实用户消息（`source.kind === 'user'`）和助手消息；
- 默认跳过子代理会话；
- 用户消息和助手消息写入当天 `session/YYYY-MM-DD.json`；
- 图片会被复制到 `pic/image/`，并生成 `<img src="pic/image/...">`；
- 同一条消息按 `sessionId + seq` 去重；
- 遇到损坏的 JSON 会先把原文件改名为 `*.corrupt-<timestamp>`，再重新建立当日文件。

自动归档是后台任务，失败只记录警告，不影响会话提交。

## 系统提示

开启 `injectContext` 后，插件注册一个 `memory` system prompt section，把 `soul.md`、`IDENTITY.md`、`MEMORY.md` 的当前内容按 `maxContextChars` 截断后注入。修改核心文件或调用 `init` 后会刷新缓存。

## 跨平台

- 路径使用 Node `path` / `os` API，Windows、Linux、macOS 均可运行。
- 默认根目录使用 `os.homedir()`，不依赖 shell 语法。
- 设置支持 `~`、`$VAR`、`${VAR}` 和 Windows 的 `%VAR%` 展开。
- 日期使用本地时区，避免 UTC 跨日导致文件名与用户日期不一致。
- 写入采用临时文件 + rename，Windows 上会对 `EEXIST`/`EPERM` 做替换重试。

## 安装

本目录是一个本地 bundle：

```text
doublememory/
├── package.json
├── cordis.patch.yml
├── index.js
├── client.js
├── icon.svg
├── locale/
│   ├── en.json
│   └── zh.json
└── README.md
```

依赖 `@deepseek-ai/schemastery` 用于声明可热更新的 Config。安装后插件条目为 `doublememory`，模型工具名为 `memory`，设置页注册在 `settings.section`。

## 注意

- `soul.md`、`IDENTITY.md`、`MEMORY.md` 初次创建时是模板，不会覆盖已有文件。
- 删除核心文件后，本次进程内不会立刻重建；重启或再次调用 `init` 会补回模板。
- 自动归档只记录文本和图片；工具调用、推理过程和系统提示不写入会话归档。
- 记忆是插件拥有的普通文件，不是 Session 日志的一部分；跨设备同步由用户自行选择同步工具。
