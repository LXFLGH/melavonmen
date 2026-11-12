"""End-to-end MCP stdio integration, not merely a function import smoke test."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import subprocess
import socket
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from native_engine import update

@unittest.skipUnless(importlib.util.find_spec("mcp"), "install optional mcp>=2,<3")
class MCPIntegrationTests(unittest.TestCase):
    def test_stdio_capabilities_and_write_gate(self):
        from mcp import Client, StdioServerParameters
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "test.py").write_text(
                "def query_example(amount: int) -> int:\n    return amount * 2\n",
                encoding="utf-8",
            )
            self.assertTrue(update(root)["ok"])

            async def check():
                params = StdioServerParameters(
                    command=sys.executable,
                    args=[str(SCRIPTS / "native_mcp.py"), "--project", str(root)],
                )
                async with Client(params) as client:
                    advertised = await client.list_tools()
                    names = {item.name for item in advertised.tools}
                    expected = {
                        "melavonmen_index", "melavonmen_search",
                        "melavonmen_find_symbol", "melavonmen_find_references",
                        "melavonmen_dependency_graph", "melavonmen_impact_analysis",
                        "melavonmen_read_context", "melavonmen_validate",
                        "melavonmen_sync_status",
                    }
                    self.assertTrue(expected <= names, names)
                    found = await client.call_tool(
                        "melavonmen_find_symbol", {"name": "query_example"})
                    self.assertFalse(found.is_error, found)
                    self.assertIn("query_example", str(found.content))
                    status = await client.call_tool("melavonmen_validate", {})
                    self.assertFalse(status.is_error, status)
                    denied = await client.call_tool("melavonmen_index", {})
                    self.assertFalse(denied.is_error, denied)
                    self.assertIn("index writes disabled", str(denied.content))
            asyncio.run(check())

    def test_streamable_http_loopback(self):
        from mcp import Client
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "hello.py").write_text("def hello(): return 1\n", "utf-8")
            update(root)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            server = subprocess.Popen(
                [sys.executable, str(SCRIPTS / "native_mcp.py"),
                 "--project", str(root), "--transport", "streamable-http",
                 "--port", str(port)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            try:
                async def run():
                    last = None
                    for _ in range(15):
                        if server.poll() is not None:
                            break
                        try:
                            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                                tools = await client.list_tools()
                                names = {entry.name for entry in tools.tools}
                                self.assertIn("melavonmen_find_symbol", names)
                                response = await client.call_tool(
                                    "melavonmen_find_symbol", {"name": "hello"})
                                self.assertFalse(response.is_error)
                                self.assertIn("hello", str(response.content))
                                return
                        except Exception as exc:
                            last = exc
                            await asyncio.sleep(.3)
                    stderr = server.stderr.read() if server.poll() is not None else ""
                    raise AssertionError(f"HTTP handshake failed: {last}; server stderr: {stderr}")
                asyncio.run(run())
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
                if server.stderr:
                    server.stderr.close()

if __name__ == "__main__":
    unittest.main()
