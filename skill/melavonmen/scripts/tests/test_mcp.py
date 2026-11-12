"""End-to-end MCP stdio integration, not merely a function import smoke test."""
import asyncio
import importlib.util
from pathlib import Path
import sys
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

if __name__ == "__main__":
    unittest.main()
