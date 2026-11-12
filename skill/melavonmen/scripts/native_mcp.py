"""MCP 2.x stdio/Streamable-HTTP server. Install: pip install 'mcp>=2,<3'.

Query tools are read-only and bound to one workspace root at process startup.
Mutating index tools require --allow-write. No tool can choose an arbitrary root.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from native_engine import (
    context, doctor, graph, impact, query, references, sync_status, update,
)

MAX_RESPONSE = 16000
SECRET = re.compile(r'(?i)\b(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*'
                    r'(?:"[^"]*"|\x27[^\x27]*\x27|[^\s,}]+)')

def serve(project, allow_write=False, transport="stdio", port=8765):
    try:
        from mcp.server import MCPServer
    except ImportError as exc:
        raise SystemExit("Install MCP 2.x: pip install 'mcp>=2,<3'") from exc

    root = Path(project).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("workspace root must be a directory")
    server = MCPServer("melavonmen-native-codebase-intelligence")

    def encode(obj):
        data = json.dumps(obj, ensure_ascii=False, default=str)
        data = SECRET.sub(lambda m: m.group(1) + "=<REDACTED>", data)
        data = data.replace(str(root), "<workspace>")
        if len(data) > MAX_RESPONSE:
            data = json.dumps({"truncated": True, "warning": "MCP response size cap",
                               "preview": data[:MAX_RESPONSE - 300]}, ensure_ascii=False)
        return data

    @server.tool()
    def melavonmen_index(full: bool = False) -> str:
        """Refresh the workspace-local index. Requires explicit --allow-write."""
        if not allow_write:
            return encode({"ok": False, "error": "index writes disabled; use --allow-write"})
        return encode(update(root, full=full))

    @server.tool()
    def melavonmen_search(text: str, mode: str = "auto", limit: int = 10,
                         offset: int = 0, token_budget: int = 1200,
                         language: str = "", directory: str = "") -> str:
        """Rank file, symbol, text and Doc/Wiki matches with source evidence."""
        return encode(query(root, text, mode=mode, limit=limit, offset=offset,
                            language=language or None, directory=directory or None,
                            token_budget=token_budget))

    @server.tool()
    def melavonmen_find_symbol(name: str) -> str:
        """Find exact definitions and signatures."""
        return encode(query(root, name, mode="definition", limit=30))

    @server.tool()
    def melavonmen_find_references(name: str, limit: int = 100) -> str:
        """Find known source-location references; possible dynamic uses are not certified."""
        return encode(references(root, name, limit))

    @server.tool()
    def melavonmen_dependency_graph(name: str, depth: int = 2,
                                   reverse: bool = False) -> str:
        """Traverse provenanced import/call/resource/inheritance edges."""
        return encode(graph(root, name, reverse=reverse, depth=depth))

    @server.tool()
    def melavonmen_impact_analysis(paths: list[str], depth: int = 3) -> str:
        """Conservative reverse impact plus relevant Doc/Wiki review candidates."""
        return encode(impact(root, paths, depth=depth))

    @server.tool()
    def melavonmen_read_context(path: str, line: int = 1,
                               before: int = 6, after: int = 12) -> str:
        """Read only hash-verified indexed source lines inside workspace."""
        return encode(context(root, path, line, before, after))

    @server.tool()
    def melavonmen_validate() -> str:
        """Check index integrity and independent source coverage."""
        return encode(doctor(root))

    @server.tool()
    def melavonmen_sync_status(paths: list[str] | None = None) -> str:
        """List candidate Doc/Wiki pages; never auto-approve contracts."""
        return encode(sync_status(root, paths or []))

    if transport == "streamable-http":
        server.run(transport="streamable-http", host="127.0.0.1", port=port)
    else:
        server.run(transport="stdio")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", type=Path, default=Path.cwd())
    p.add_argument("--allow-write", action="store_true")
    p.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    serve(a.project, a.allow_write, a.transport, a.port)

if __name__ == "__main__":
    main()
