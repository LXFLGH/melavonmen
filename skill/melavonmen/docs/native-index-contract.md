# Native Codebase Intelligence — approved implementation contract

Status: approved by task authorization; baseline main 77b21ca39e5f01645a9f2e198746153f5f6745b5. This is a **target contract**, not a statement that code is complete.

## Scope and authority

Preserve Melavonmen Doc (design intent), Wiki (verified existing facts), and source-code evidence. The new generated SQLite database is **neither Doc nor Wiki** and can be discarded and rebuilt. No generated symbol or edge may be reported as verified merely because a file SHA matches.

Canonical generated index: workspace-local .melavonmen/index.sqlite, gitignored. A process may request a different database path **only inside its workspace**. Never overwrite an existing human-maintained wiki/index.json. Export machine-derived file routes to a dedicated generated sidecar; merge into the managed Wiki only through a deliberate sync operation.

## Storage and lifecycle

- Inventory: Git tracked files, plus Git-untracked nonignored first-party source. Independent filesystem walk validates actual coverage.
- File records: normalized relative path, language, SHA-256, Git HEAD, actual worktree content hash, extraction depth, parser/version.
- Symbol records: name, qualified name, kind, signature, range, source_sha256, revision, extraction_method, verification_status.
- Edge records: kind, source file + line, optional resolved target file/symbol, original target name, source_sha256, revision, extraction_method, verification_status.
- A parser failure lowers confidence and appears in audit output, never silently becomes verified.
- All mutations transact together; generated SQLite files must be separate per worktree. Retry SQLITE_BUSY; do not delete user data on lock contention.
- Deletion removes obsolete file, symbol, edge and search cache rows; database schema version mismatch fails safe and instructs doctor/rebuild.
- Failed rebuild is non-destructive where possible. Doctor reports stale, unknown parser, missing, orphan, unresolved and failed integrity status.

## Search and token budget

Deterministic symbol/path/filename/exact text search and SQLite FTS. No API key required. Score matches, deduplicate by path+line+symbol, page using offset/limit, return source line ranges and evidence, clamp output size and never read arbitrary paths. Semantic embeddings are optional and must require explicit opt-in before sending remote data. Dynamic calls/reflection, ambiguous name binding and scene/node lookups are *possible*, not verified.

## Godot 4

Discover GDScript, scene/resource INI-like sections, ext_resource, UID, Autoload, script binds, node instances, signal connections and literal preload/load paths. Track path-based and UID-based dependencies separately. Do not edit project resources. Dynamic path expressions emit unknown/possible edges and retain text-search fallback.

## CLI and MCP

build/update/check/audit/doctor/rebuild/query/find/references/graph/impact/context/sync-status/benchmark. All paths are relative to and constrained within --project. Stdio MCP query tools are read-only by default. Index mutation is available only when explicit --allow-write is passed. Streamable HTTP binds loopback by default; external binds require deliberate operator choice.

## Delivery gates

- Multi-language fixtures for Python, GDScript, JS/TS, C/C++, C#, JSON, YAML/TOML and Godot scenes.
- Cold/warm build, increment, query P50/P95, change impact and token-budget test.
- Provenance and confidence tests; traversal and symlink confinement tests; rename/deletion/untracked/worktree tests.
- Preserve existing validator test results.
- Record missing dependencies and unsupported precise analysis honestly. A component is marked verified only on passing runnable tests.
