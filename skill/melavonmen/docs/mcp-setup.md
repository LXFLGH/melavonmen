# Native Codebase Intelligence — Installation, CLI and MCP

## Requirements

Python 3.11+ recommended, SQLite with FTS5. The deterministic file inventory,
Python AST, Godot resource parser, SQLite search and CLI need **no external Python
dependencies**. For full structural parsing of GDScript, JS/TS, C/C++ and C#:

    python -m pip install 'tree-sitter>=0.25,<1' 'tree-sitter-language-pack>=1.19,<2' 'PyYAML>=6,<7'

These grammars may be downloaded into the parser package cache on first use;
install or pre-fetch them ahead of time if offline. Parsing failure is reported,
not silently converted into a verified symbol. For optional MCP server:

    python -m pip install 'mcp>=2,<3'

For optional local semantic search: install sentence-transformers. No semantic
model or API key is required for ordinary codebase indexing or retrieval.

The examples below substitute these two *absolute* paths:

- /ABS/MELAVONMEN/skill/melavonmen/scripts/native_mcp.py — this MCP server file.
- /ABS/YOUR-PROJECT — the target source-code worktree root.

**Never point the server at a broad home directory.** The project root is fixed
at launch, and the MCP tool cannot change it.

## CLI quickstart

    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT build
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT check
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT audit
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT query calculate_price --mode symbol --limit 5 --token-budget 800
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT references calculate_price
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT graph src/pricing.py --reverse --depth 3
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT impact src/pricing.py
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT cycles
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT unresolved
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT sync-status
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT doctor
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT rebuild
    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py --project /ABS/YOUR-PROJECT benchmark --runs 5

Generated cache lives at /ABS/YOUR-PROJECT/.melavonmen/. Add
'.melavonmen/' to the project's .gitignore. It contains rebuildable machine
facts, not hand-maintained Doc or Wiki. The export-routes command writes only
the generated .melavonmen/wiki-routes.json sidecar; existing wiki/index.json
must stay authoritative and be merged by a coordinating Agent.

The optional .melavonmen.json project config can contain:

    {"include": ["**/*"], "exclude": ["tests/fixtures/**"], "max_source_bytes": 2097152}

Worktrees are isolated automatically because each root has its own cache.
Indexes represent the **actual worktree** (including untracked Git-nonignored
files), not just the latest committed HEAD. After a merge or checkout, run update.
For pre-commit gates, use check; it exits nonzero on changed/stale code.

The human-readable output flag is --human before the subcommand. JSON is
default for predictable agent consumption. Natural language mode is a
deterministic lexical router, not a pretend language-understanding model.

## Optional semantic retrieval

    python native_cli.py --project /ABS/YOUR-PROJECT semantic-build --provider local --model all-MiniLM-L6-v2
    python native_cli.py --project /ABS/YOUR-PROJECT semantic-query "item price" --provider local --model all-MiniLM-L6-v2

Only the symbol path/signature metadata is embedded; no entire repository is
automatically uploaded. Local models may download files during installation.
To use a remote OpenAI-compatible embeddings endpoint, both --provider remote
and --allow-upload must be present, plus --endpoint HTTPS_URL. The API token
comes from EMBEDDING_API_KEY; never put it in the command or repository.
If semantic service fails, semantic-query automatically falls back to native
lexical retrieval. Cached vectors are keyed by file hash, provider and model.

## MCP transports

Stdio (default, read-only):

    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_mcp.py --project /ABS/YOUR-PROJECT

Explicit write permission for index refresh only:

    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_mcp.py --project /ABS/YOUR-PROJECT --allow-write

Streamable HTTP bound to loopback (for trusted local clients):

    python /ABS/MELAVONMEN/skill/melavonmen/scripts/native_mcp.py --project /ABS/YOUR-PROJECT --transport streamable-http --port 8765

Endpoint: http://127.0.0.1:8765/mcp . Do not expose this unauthenticated
service on public interfaces.

### CodeWhale

Current CodeWhale supports the interactive MCP client and a CLI:

    codewhale mcp add melavonmen --command "python3" --arg "/ABS/MELAVONMEN/skill/melavonmen/scripts/native_mcp.py" --arg "--project" --arg "/ABS/YOUR-PROJECT"
    codewhale mcp validate

It also supports ~/.codewhale/mcp.json (older versions may use
~/.deepseek/mcp.json):

    {
      "mcpServers": {
        "melavonmen": {
          "command": "python3",
          "args": ["/ABS/MELAVONMEN/skill/melavonmen/scripts/native_mcp.py",
                   "--project", "/ABS/YOUR-PROJECT"]
        }
      }
    }

Source: https://github.com/codewhale-hq/Codewhale/blob/main/docs/MCP.md

### Codex CLI

    codex mcp add melavonmen -- python3 /ABS/MELAVONMEN/skill/melavonmen/scripts/native_mcp.py --project /ABS/YOUR-PROJECT
    codex mcp list

Equivalent ~/.codex/config.toml:

    [mcp_servers.melavonmen]
    command = "python3"
    args = ["/ABS/MELAVONMEN/skill/melavonmen/scripts/native_mcp.py", "--project", "/ABS/YOUR-PROJECT"]

Source: https://learn.chatgpt.com/docs/cli/reference

### Claude Code

    claude mcp add --transport stdio melavonmen -- python3 /ABS/MELAVONMEN/skill/melavonmen/scripts/native_mcp.py --project /ABS/YOUR-PROJECT
    claude mcp list

For project-scope manual configuration, use the host's supported .mcp.json
format containing "mcpServers" with "command" and "args" as above.
Review scope/trust prompts when loading project-provided MCP definitions.

### DeepSeek Harness

Add to ~/.dsh/profiles/web/cordis.patch.yml (replace the default [] rather
than appending invalid YAML):

    - insert:
        - id: mcp-melavonmen
          name: '@deepseek-ai/dsh-mcp-client'
          config:
            serverName: melavonmen
            transport: stdio
            command: python3
            args:
              - /ABS/MELAVONMEN/skill/melavonmen/scripts/native_mcp.py
              - --project
              - /ABS/YOUR-PROJECT

This is a Host/profile-scoped process with a fixed workspace. For simultaneous
unrelated worktrees, create separate named server entries / isolated scopes.
The Web/Desktop manager may also configure its servers via Settings.

Sources:
https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md
https://github.com/deepseek-ai/deepseek-harness/discussions/8202

## Permissions / diagnostics

Tools: melavonmen_index (requires --allow-write), melavonmen_search,
melavonmen_find_symbol, melavonmen_find_references,
melavonmen_dependency_graph, melavonmen_impact_analysis,
melavonmen_read_context, melavonmen_validate, melavonmen_sync_status.

CLI read-only commands do not require MCP and MCP read-only calls never refresh
the index. A stale source hash causes context reads to fail closed and directs
the caller to update. Responses are bounded and obvious secret assignments
are redacted; **this is defense-in-depth, not a guarantee that every secret in
source code is detectable**. Never expose a workspace to untrusted MCP clients.

## Automatic update lifecycle and optional Git hook integration

Run a foreground workspace file poller for uncommitted changes:

    python native_cli.py --project /ABS/YOUR-PROJECT watch --interval 2

This uses full inventory hashes, so missed OS events cannot silently leave a
stale index. Ctrl-C terminates the watcher. To run exactly twice for tests,
add --iterations 2. It does not edit source files or Doc/Wiki.

The following Git hook *bodies* can be added to a project's existing hook
workflow. **Do not blindly replace any existing hooks.** Substitute the actual
absolute native_cli.py path; use the same path for all three. They must be
executed from the target Git project, not the Skill repository.

Before commit (in .git/hooks/pre-commit or your hook manager):

    #!/bin/sh
    python3 /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py \
      --project "$(git rev-parse --show-toplevel)" check

After commit (in .git/hooks/post-commit):

    #!/bin/sh
    python3 /ABS/MELAVONMEN/skill/melavonmen/scripts/native_cli.py \
      --project "$(git rev-parse --show-toplevel)" update

For branch switches/merges, the corresponding post-checkout/post-merge hook
can run that same update command. A pre-commit failure means the index is
stale; refresh it and review impacted Doc/Wiki before retrying. A Git hook
cannot certify manual business contracts on its own. For multiple Worktrees,
Git may share the hooks folder; the computed working-directory root ensures
each hook updates **only its own index**.

### Schema changes and recovery

    python native_cli.py --project /ABS/YOUR-PROJECT doctor
    python native_cli.py --project /ABS/YOUR-PROJECT migrate

migrate is a non-destructive rebuild from the actual worktree; it writes a
staging SQLite database, validates it, creates a consistent backup of the old
index, checkpoints its WAL and installs the new index by atomic rename. This is
appropriate because auto-generated symbol facts are not an authoritative Doc
record. Keep backups until manual verification, especially after a crash.

## Reproducible performance comparison

    python native_cli.py --project /ABS/YOUR-PROJECT benchmark --runs 10 \
      --phrase "calculate_price" --phrase "load"

The command reports cold build time, incremental unchanged-repo update P50/P95,
query P50/P95, raw ripgrep or Git grep P50/P95, full-source estimated context
tokens and returned-result estimated tokens. Both token counts are **only JSON
character-count or file-byte heuristics divided by 4**, not a precise
tokenizer; Git grep measures tracked files whereas native indexing includes
untracked nonignored sources. A raw grep baseline is reproducible but is
**not** an apples-to-apples proprietary Coding Agent Codebase Index.
Benchmark on the *same revision, same machine and same workloads*, and do not
interpret this proxy as proof of replacement quality on proprietary agents.
