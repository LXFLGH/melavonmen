"""MCP JSON-RPC server over stdio."""

from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import sys
from threading import Event, Lock, Thread

from .tools import TOOLS
from .workspace import IndexErrorWithCode


VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
PROMPTS = {
    "search": ("Search for an implementation and show source", "query", True,
               "Find source matching this request with codebase_search: {value}"),
    "find": ("Find candidate source locations", "query", True,
             "Find likely source locations with codebase_peek, then verify exact matches: {value}"),
    "definition": ("Locate a definition", "query", True,
                   "Use implementation_lookup to locate the definition: {value}"),
    "index": ("Build or refresh the repository index", "options", False,
              "Run index_codebase. Translate requested options to force, estimateOnly or dryRun: {value}"),
    "status": ("Inspect index readiness", None, False, "Use index_status to report index readiness."),
}


def prompt_list():
    return [{"name": name, "description": description,
             "arguments": [{"name": key, "required": required}] if key else []}
            for name, (description, key, required, _) in PROMPTS.items()]


class RpcError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Server:
    def __init__(self, tools):
        self.tools = tools
        self.output = Lock()
        self.pending = {}
        self.pending_lock = Lock()

    def send(self, message):
        with self.output:
            print(json.dumps({"jsonrpc": "2.0", **message}, ensure_ascii=True), flush=True)

    def dispatch(self, method, params, cancel):
        if method == "initialize":
            version = params.get("protocolVersion")
            return {"protocolVersion": version if version in VERSIONS else "2025-06-18",
                    "capabilities": {"tools": {}, "prompts": {}, "resources": {}},
                    "serverInfo": {"name": "melavonmen", "version": "3.1.0"}}
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [{"name": name, "description": description, "inputSchema": schema}
                              for name, (description, schema) in TOOLS.items()]}
        if method == "prompts/list":
            return {"prompts": prompt_list()}
        if method == "resources/list":
            return {"resources": []}
        if method == "resources/templates/list":
            return {"resourceTemplates": []}
        if method == "prompts/get":
            spec = PROMPTS.get(params.get("name"))
            if not spec:
                raise RpcError(-32602, "Unknown prompt")
            description, key, required, template = spec
            arguments = params.get("arguments") or {}
            value = arguments.get(key, "")
            if required and not value:
                raise RpcError(-32602, f"Expected argument {key}")
            return {"description": description,
                    "messages": [{"role": "user", "content": {"type": "text", "text": template.format(value=value)}}]}
        if method == "tools/call":
            token = (params.get("_meta") or {}).get("progressToken")
            progress = None
            if token is not None:
                def progress(done, total, message):
                    self.send({"method": "notifications/progress",
                               "params": {"progressToken": token, "progress": done, "total": total, "message": message}})
            try:
                return self.tools.invoke(params.get("name"), params.get("arguments"), cancel, progress)
            except IndexErrorWithCode as exc:
                return tool_error(exc.code, str(exc))
            except sqlite3.Error:
                return tool_error("INDEX_ERROR", "The local database operation failed. Run index_health_check.")
            except (OSError, TypeError, ValueError, KeyError) as exc:
                self.tools.index.log("general", f"Operation failed: {type(exc).__name__}", "error")
                return tool_error("OPERATION_FAILED", "Check workspace files, configuration and tool arguments.")
        raise RpcError(-32601, "Method not found")

    def answer(self, request_id, method, params, cancel):
        try:
            result = self.dispatch(method, params, cancel)
            self.send({"id": request_id, "result": result})
        except RpcError as exc:
            self.send({"id": request_id, "error": {"code": exc.code, "message": str(exc)}})
        except Exception as exc:
            print(f"Melavonmen MCP operation failed: {type(exc).__name__}", file=sys.stderr, flush=True)
            self.send({"id": request_id, "error": {"code": -32603, "message": "Internal error"}})
        finally:
            with self.pending_lock:
                self.pending.pop(request_id, None)

    def receive(self, workers, request):
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            self.send({"id": None, "error": {"code": -32600, "message": "Invalid request"}})
            return
        method, params = request["method"], request.get("params", {})
        if "id" not in request:
            if method == "notifications/cancelled" and isinstance(params, dict):
                with self.pending_lock:
                    cancel = self.pending.get(params.get("requestId"))
                    if cancel:
                        cancel.set()
            return
        request_id = request["id"]
        if type(request_id) not in (str, int) or not isinstance(params, dict):
            self.send({"id": None, "error": {"code": -32602, "message": "Invalid request parameters"}})
            return
        cancel = Event()
        with self.pending_lock:
            if request_id in self.pending:
                self.send({"id": request_id, "error": {"code": -32600, "message": "Request ID is already in use"}})
                return
            self.pending[request_id] = cancel
        if method == "initialize":
            self.answer(request_id, method, params, cancel)
        else:
            workers.submit(self.answer, request_id, method, params, cancel)

    def run(self):
        stop = Event()
        watcher = Thread(target=self.watch, args=(stop,), name="index-watch", daemon=True)
        watcher.start()
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="mcp") as workers:
            try:
                for line in sys.stdin:
                    if not line.strip():
                        continue
                    try:
                        request = json.loads(line)
                    except ValueError:
                        self.send({"id": None, "error": {"code": -32700, "message": "Invalid JSON"}})
                        continue
                    self.receive(workers, request)
            finally:
                stop.set()
                with self.pending_lock:
                    for cancel in self.pending.values():
                        cancel.set()

    def watch(self, stop):
        index = self.tools.index
        while not stop.wait(4):
            try:
                if not index.database.is_file():
                    continue
                settings = index.workspace.settings.get("indexing", {})
                if settings.get("watchFiles", True) and (index.status()["ready"] or settings.get("autoIndex", False)):
                    index.refresh(cancel=stop, poll=True)
            except (IndexErrorWithCode, OSError, sqlite3.Error, ValueError, TypeError) as exc:
                index.log("cache", f"Watcher could not refresh: {getattr(exc, 'code', type(exc).__name__)}", "warn")


def tool_error(code, message):
    return {"isError": True, "content": [{"type": "text", "text": f"{code}: {message}"}],
            "structuredContent": {"error": {"schemaVersion": 1, "code": code, "message": message}}}
