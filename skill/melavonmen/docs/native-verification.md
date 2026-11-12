# Native Codebase Intelligence — reproducible engineering verification

## Environment and commands

Reference successful CI run:
https://github.com/LXFLGH/melavonmen/actions/runs/43189212881

Commit: 3242144818520b4c63a30f584446c5da640995f9
Environment: Ubuntu GitHub Actions, Python 3.11 and 3.13.
44 regression tests (Python 3.11), 0 failed; both CI jobs succeeded.

    python -m pip install 'tree-sitter>=0.25,<1' 'tree-sitter-language-pack>=1.19,<2' 'PyYAML>=6,<7' 'mcp>=2,<3'
    python -m unittest discover -s skill/melavonmen/scripts/tests -v
    python skill/melavonmen/scripts/native_cli.py --project . build
    python skill/melavonmen/scripts/native_cli.py --project . check
    python skill/melavonmen/scripts/native_cli.py --project . audit
    python skill/melavonmen/scripts/native_cli.py --project . doctor
    python skill/melavonmen/scripts/native_cli.py --project . query native --limit 5
    python skill/melavonmen/scripts/native_cli.py --project . benchmark --runs 3 --phrase native

## Example metrics from the successful run

| Metric | Measured |
|---|---:|
| Independently scanned first-party files | 46 |
| Index file coverage | 46/46 |
| Deep parsed files | 46 |
| Syntax-verified symbols | 903 |
| Unverified symbols | 73 |
| Stale/missing/orphan files | 0/0/0 |
| Unresolved static edges | 20,777 |
| Cold build | 693.69 ms |
| Unchanged-repo incremental update P50 | 87.04 ms |
| Native query P50 | 9.32 ms |
| Raw git grep P50 | 3.64 ms |
| Approximate query result tokens (P50) | 1,104 |
| Approximate full source tokens | 114k |

Three benchmark repetitions are not statistically sufficient for robust P95
inference. Results change by hardware and cache warmth. Token numbers are JSON
character-count or file-byte divided by four, not a tokenizer. Git grep
is a reproducible raw text baseline, not a proprietary Coding Agent Codebase
Index. Therefore this does not prove superiority over any proprietary indexer.

## Evidence gates

- Legacy validator and asset contract regression tests unchanged and passing.
- Independent scanned source coverage, stale source rejection, missing/orphan
  indexes, Unicode/space filename, deletion, rename, dirty worktree vs HEAD.
- Source-provenanced Python AST and Tree-sitter multilanguage signatures,
  call/import/reference edges, C++/C#/TS/GDScript fixtures, config keys.
- Godot 4 scene/resource script references, UID sidecars, signal connections,
  exported property overrides, Autoloads, SceneTree paths, conservative impact.
- Git Worktree separation, concurrent SQLite writers, atomic rebuild and
  live changes, symlink/path traversal checks.
- Source-hash gated read-context, output budget, semantic cache/fallback,
  Doc/Wiki contract candidates and stale signature audit.
- Actual MCP stdio and HTTP loopback handshakes, read-only permission check.
- Cold/warm/query/raw baseline repeatable performance commands.

## Non-claims / further acceptance work

Syntax-verified symbols are not verified runtime behavior. Static/dynamic
cross-module reference resolution can remain possible/unverified. 20k+
unresolved edges mostly include possible identifier references; they are not
20k demonstrated defects. Real repository CI exercises 46 source/config
files; Godot 4 cases are from fixtures rather than a real large Godot game.
No industrial-scale ground-truth semantic recall benchmark or apples-to-apples
comparison with a proprietary Codebase Index has been executed.

Doc architectural intent remains governed by agent/human audit. Generated
machine facts do not promote Doc statuses or overwrite verified Wiki pages.
Remote embeddings require explicit upload consent; MCP defaults read-only.
