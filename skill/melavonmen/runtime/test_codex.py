"""Smoke-test the installed Melavonmen plugin through Codex's app server."""

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from queue import Queue
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
import unittest


class AppServer:
    def __init__(self):
        self.process = subprocess.Popen(
            ["codex", "app-server", "--listen", "stdio://"], text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        self.messages = Queue()
        self.request_id = 0
        self.reader = Thread(target=self.read, daemon=True)
        self.reader.start()

    def read(self):
        for line in self.process.stdout:
            self.messages.put(json.loads(line))
        self.messages.put(None)

    def call(self, method, params, *, notification=False):
        self.request_id += 1
        request = {"method": method, "params": params}
        if not notification:
            request["id"] = self.request_id
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        if notification:
            return None
        while True:
            response = self.messages.get(timeout=120)
            if response is None:
                raise RuntimeError(f"Codex app server closed while handling {method}")
            if response.get("id") == self.request_id:
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response["result"]

    def close(self):
        self.process.terminate()
        self.process.wait(timeout=10)
        self.reader.join(timeout=10)
        self.process.stdin.close()
        self.process.stdout.close()


class InstalledPlugin(unittest.TestCase):
    def connect(self, repo):
        server = AppServer()
        self.addCleanup(server.close)
        server.call("initialize", {"clientInfo": {"name": "melavonmen-smoke", "version": "1"}})
        server.call("initialized", {}, notification=True)
        skills = server.call("skills/list", {"cwds": [str(repo)]})
        names = {skill["name"] for entry in skills["data"] for skill in entry["skills"]}
        self.assertIn("melavonmen:melavonmen", names)
        thread = server.call("thread/start", {"cwd": str(repo), "ephemeral": True})["thread"]["id"]
        status = server.call("mcpServerStatus/list", {"threadId": thread, "serverName": "codebase-index"})
        self.assertEqual(len(status["data"]), 1, status)
        tools = status["data"][0]["tools"]
        self.assertEqual(len(tools), 23, tools)

        def call(tool, **arguments):
            result = server.call("mcpServer/tool/call", {
                "threadId": thread, "server": "codebase-index", "tool": tool,
                "arguments": arguments,
            })
            self.assertFalse(result.get("isError"), result)
            return json.dumps(result, ensure_ascii=False)

        return call

    def test_tool_discovery_and_checkout_scope(self):
        with TemporaryDirectory(prefix="检索 测试 ") as temporary:
            repo = Path(temporary)
            (repo / ".codebase-index").mkdir()
            (repo / ".codebase-index" / "config.json").write_text(
                '{"indexing":{"mode":"structural","watchFiles":false}}', encoding="utf-8",
            )
            def git(*args):
                subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)

            git("init", "-q", "-b", "main")
            definition = repo / "recovery.ts"
            definition.write_text(
                "export function resumePendingBatch() { return 'recovery'; }\n",
                encoding="utf-8",
            )
            (repo / "caller.ts").write_text(
                "import {resumePendingBatch} from './recovery';\n"
                "export function retryJob() { return resumePendingBatch(); }\n",
                encoding="utf-8",
            )
            git("add", "caller.ts", "recovery.ts")
            git("-c", "user.name=test", "-c", "user.email=test@example.test", "commit", "-qm", "baseline")
            call = self.connect(repo)

            self.assertIn(str(repo), call("index_status"))
            call("index_codebase")
            self.assertIn("recovery.ts", call("codebase_search", query="resumePendingBatch"))
            self.assertIn("recovery.ts", call("implementation_lookup", query="resumePendingBatch"))
            self.assertIn("retryJob", call("call_graph", name="resumePendingBatch", direction="callers"))
            self.assertIn("retryJob", call("call_graph_path", **{"from": "retryJob", "to": "resumePendingBatch"}))
            self.assertIn("recovery.ts", call("codebase_context", query="resumePendingBatch", tokenBudget=600, limit=5))

            git("switch", "-qc", "rename")
            git("mv", "recovery.ts", "renewal.ts")
            git("-c", "user.name=test", "-c", "user.email=test@example.test", "commit", "-qm", "rename")
            call("index_codebase")
            lookup = call("implementation_lookup", query="resumePendingBatch")
            self.assertIn("renewal.ts", lookup)
            self.assertNotIn("recovery.ts", lookup)
            git("switch", "-q", "main")
            call("index_codebase")
            lookup = call("implementation_lookup", query="resumePendingBatch")
            self.assertIn("recovery.ts", lookup)
            self.assertNotIn("renewal.ts", lookup)

    def test_hybrid_retrieval_with_local_embedding_endpoint(self):
        requests = []

        class Embeddings(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_POST(self):
                if self.path != "/v1/embeddings":
                    self.send_error(404)
                    return
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                inputs = request["input"]
                if isinstance(inputs, str):
                    inputs = [inputs]
                requests.extend(inputs)
                data = [
                    {"object": "embedding", "index": index,
                     "embedding": [(byte + 1) / 256 for byte in hashlib.sha256(value.encode()).digest()[:8]]}
                    for index, value in enumerate(inputs)
                ]
                result = json.dumps({"object": "list", "model": request["model"], "data": data}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(result)))
                self.end_headers()
                self.wfile.write(result)

        with ThreadingHTTPServer(("127.0.0.1", 0), Embeddings) as endpoint, TemporaryDirectory() as temporary:
            worker = Thread(target=endpoint.serve_forever, daemon=True)
            worker.start()
            try:
                repo = Path(temporary)
                (repo / ".codebase-index").mkdir()
                config = {
                    "indexing": {"mode": "hybrid", "watchFiles": False},
                    "embeddingProvider": "custom",
                    "customProvider": {
                        "baseUrl": f"http://127.0.0.1:{endpoint.server_port}/v1",
                        "model": "test-embedding", "dimensions": 8, "requestIntervalMs": 0,
                    },
                }
                (repo / ".codebase-index" / "config.json").write_text(json.dumps(config), encoding="utf-8")
                code = "export function resumePendingBatch() { return 'recovery'; }\n"
                (repo / "recovery.ts").write_text(code, encoding="utf-8")
                call = self.connect(repo)
                call("index_codebase")
                self.assertIn("recovery.ts", call("codebase_search", query="continue after interrupted processing"))
                self.assertIn("recovery.ts", call("find_similar", code=code))
                self.assertGreaterEqual(len(requests), 3)
            finally:
                endpoint.shutdown()
                worker.join(timeout=10)


if __name__ == "__main__":
    unittest.main()
