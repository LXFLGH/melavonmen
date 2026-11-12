"""Independent index regression tests with temporary workspaces."""

from contextlib import closing
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from melavonmen_index.history import GitHubFailure
from melavonmen_index.protocol import Server
from melavonmen_index.tools import Tools
from melavonmen_index.workspace import IndexErrorWithCode, Workspace, atomic_json


class IndexTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.project = self.root / "项目"
        self.project.mkdir()
        self.tools = Tools(Workspace(self.project))
        self.settings = self.project / ".melavonmen" / "config.json"

    def save(self, name, data):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def call(self, tool, **arguments):
        return self.tools.invoke(tool, arguments)["structuredContent"]

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.project), *args],
                              capture_output=True, check=True).stdout

    def commit(self):
        self.git("add", "-A")
        self.git("-c", "user.name=Tester", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")

    def test_dry_run_filters_and_refresh(self):
        self.save(".gitignore", "ignored.py\n.melavonmen/\n")
        self.git("init", "-qb", "main")
        old = self.save("lib/读取.py", "def resumePendingTask():\n    return '重试恢复'\n")
        self.save("ignored.py", "def secretIgnored(): pass\n")
        self.save(".env", "LOCAL_SECRET=never-index\n")
        self.save("lib/extra.txt", "pending task notes\n")
        self.commit()
        self.save("ignored.py", "def secretIgnored(): pass\n")
        self.assertEqual(self.call("index_codebase", dryRun=True)["files"], 2)
        self.assertFalse(self.tools.index.database.exists())
        self.assertFalse(self.call("index_status", checkFreshness=True)["ready"])
        self.assertEqual(self.call("index_codebase")["files"], 2)
        self.assertEqual(self.call("index_codebase")["unchanged"], 2)
        self.assertTrue(self.call("index_health_check")["ok"])
        self.assertTrue(self.call("index_status", checkFreshness=True)["freshness"]["current"])
        self.assertEqual(self.call("codebase_search", query="重试", fileType="py", directory="lib")["results"][0]["path"], "lib/读取.py")
        rows = self.call("codebase_peek", query="pending", blameAuthor="Tester")["results"]
        self.assertTrue(rows)
        self.assertTrue(all("text" not in hit for hit in rows))
        old.rename(old.with_name("继续.py"))
        self.assertEqual(self.call("index_status", checkFreshness=True)["freshness"]["changedFiles"], ["lib/继续.py", "lib/读取.py"])
        rows = self.call("implementation_lookup", query="resumePendingTask")["results"]
        self.assertEqual({hit["path"] for hit in rows}, {"lib/继续.py"})
        self.assertFalse(self.call("codebase_search", query="secretIgnored")["results"])
        self.assertTrue(self.call("index_logs")["entries"])
        self.assertTrue(self.call("index_metrics")["metrics"]["queries"])

    def test_graph_disambiguation_reexports_and_tests(self):
        self.save("src/math.ts", "export function total() { return 3; }\n")
        self.save("src/other.ts", "export function total() { return 9; }\n")
        self.save("src/index.ts", "export { total as calculate } from './math';\n")
        self.save("app/main.ts", "import { calculate } from '../src';\n"
                  "export function checkout() { return calculate(); }\n"
                  "export function shadow(calculate: Function) { return calculate(); }\n")
        self.save("tests/main.test.ts", "import {checkout} from '../app/main';\ncheckout();\n")
        self.call("index_codebase")
        with self.assertRaisesRegex(IndexErrorWithCode, "Ambiguous"):
            self.call("call_graph", name="total")
        edges = self.call("call_graph", name="total", filePath="src/math.ts")["edges"]
        self.assertEqual([edge["from"].split(":")[-1] for edge in edges], ["checkout"])
        path = self.call("call_graph_path", **{"from": "checkout", "to": "total", "toFilePath": "src/math.ts"})
        self.assertEqual(len(path["path"]), 1)
        context = self.call("codebase_context", query="find calculate", symbol="total", tokenBudget=128)
        self.assertEqual(context["route"], "definition")
        edit = self.call("codebase_edit_context", query="edit checkout", symbol="checkout",
                         includeTests=True, includeApiImpact=True)
        self.assertEqual(edit["tests"][0]["path"], "tests/main.test.ts")
        self.assertTrue(edit["apiImpact"]["declaration"])
        self.assertTrue(self.call("architecture_context")["dependencies"])
        self.assertTrue(self.call("code_communities")["communities"])

    def test_branch_and_working_tree_impact(self):
        self.git("init", "-qb", "main")
        self.save(".gitignore", ".melavonmen/\n")
        self.save("lib.py", "def source():\n    return 1\n\ndef caller():\n    return source()\n")
        self.commit()
        self.git("switch", "-qc", "change")
        self.save("lib.py", "def source():\n    return 2\n\ndef caller():\n    return source()\n")
        self.commit()
        branch = self.call("pr_impact", branch="change")
        self.assertEqual(branch["scope"]["kind"], "branch")
        self.assertIn("lib.py", branch["changedFiles"])
        self.assertFalse(branch["signatureChanges"])
        self.call("index_codebase")
        self.save("lib.py", "def source():\n    return 3\n\ndef caller():\n    return source()\n")
        impact = self.call("pr_impact", workingTree=True)
        self.assertEqual({s["name"] for s in impact["affectedSymbols"]}, {"source", "caller"})

    def test_knowledge_base_scope_and_cancellation(self):
        self.save("local.py", "def local(): pass\n")
        external = self.root / "knowledge"
        external.mkdir()
        (external / "extra.md").write_text("independent knowledge evidence", encoding="utf-8")
        self.call("index_codebase")
        self.assertEqual(self.call("add_knowledge_base", path=str(external))["knowledgeBases"], [str(external)])
        self.assertEqual(self.call("list_knowledge_bases")["knowledgeBases"], [str(external)])
        self.assertTrue(self.call("codebase_search", query="independent evidence")["results"])
        self.call("remove_knowledge_base", path=str(external))
        self.assertFalse(self.call("codebase_search", query="independent evidence")["results"])
        self.save("local.py", "def replacement(): pass\n")
        cancel = Event()
        cancel.set()
        with self.assertRaisesRegex(IndexErrorWithCode, "cancelled"):
            self.tools.invoke("index_codebase", {}, cancel=cancel)
        with closing(self.tools.index.connect()) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM snapshots").fetchone()[0], 1)
        self.assertEqual(self.call("index_status", checkFreshness=True)["freshness"]["changedFiles"], ["local.py"])

    def test_failed_vector_refresh_preserves_published_snapshot(self):
        atomic_json(self.settings, {"indexing": {"mode": "hybrid", "watchFiles": False},
                                    "embeddingProvider": "custom",
                                    "customProvider": {"baseUrl": "http://127.0.0.1:9/v1", "model": "fixture", "dimensions": 2}})
        self.save("local.py", "def previous(): return 1\n")
        with patch("melavonmen_index.index.Embeddings.embed", side_effect=lambda texts: [[1, 0] for _ in texts]):
            self.call("index_codebase")
        published = self.call("index_status")
        self.save("local.py", "def replacement(): return 2\n")
        with patch("melavonmen_index.index.Embeddings.embed",
                   side_effect=IndexErrorWithCode("provider unavailable", "EMBEDDING_ERROR")):
            with self.assertRaisesRegex(IndexErrorWithCode, "provider unavailable"):
                self.call("index_codebase")
        self.assertEqual(self.call("index_status")["indexedAt"], published["indexedAt"])
        self.assertTrue(self.call("implementation_lookup", query="previous")["results"])
        self.assertFalse(self.call("implementation_lookup", query="replacement")["results"])

    def test_history_opt_in_and_permission_reconciliation(self):
        repository = "owner/repo"
        atomic_json(self.settings, {"repositoryHistory": {"repositories": [{"repository": repository, "enabled": True}]}})
        issue = {"number": 7, "title": "Batch recovery", "state": "open", "created_at": "2026-01-01",
                 "html_url": "https://github.com/owner/repo/issues/7", "user": {"login": "dev"},
                 "body": "Drain pending jobs after restart."}
        comment = {"html_url": issue["html_url"] + "#issuecomment-2", "body": "Retry queued work after a timeout."}
        answers = {"user": {"id": 4}, "repos/owner/repo": {"id": 19},
                   "repos/owner/repo/issues?state=all&per_page=100": [issue],
                   "repos/owner/repo/issues/7/comments?per_page=100": [comment]}
        with patch("melavonmen_index.history.gh_api", side_effect=lambda _host, route, **_kw: answers[route]):
            self.assertEqual(self.call("repository_history_sync")["entries"], 1)
        hit = self.call("repository_history_search", query="timeout retry")["results"][0]
        self.assertEqual(hit["url"], comment["html_url"])
        with patch("melavonmen_index.history.gh_api", side_effect=GitHubFailure(403, rate_limited=True)):
            with self.assertRaises(GitHubFailure):
                self.call("repository_history_sync")
        self.assertEqual(self.call("repository_history_status")["entries"], 1)
        with patch("melavonmen_index.history.gh_api", side_effect=GitHubFailure(403)):
            with self.assertRaises(GitHubFailure):
                self.call("repository_history_sync")
        self.assertEqual(self.call("repository_history_status")["entries"], 0)
        self.assertTrue(self.call("repository_history_clear", repository=repository)["cleared"])

    def test_protocol_manifest_and_error_schema(self):
        server = Server(self.tools)
        self.assertEqual(len(server.dispatch("tools/list", {}, None)["tools"]), 23)
        prompts = server.dispatch("prompts/list", {}, None)["prompts"]
        self.assertEqual({p["name"] for p in prompts}, {"search", "find", "definition", "index", "status"})
        self.assertEqual(server.dispatch("initialize", {"protocolVersion": "2025-06-18"}, None)["serverInfo"]["name"], "melavonmen")
        bad = server.dispatch("tools/call", {"name": "codebase_search", "arguments": {"limit": True}}, None)
        self.assertTrue(bad["isError"])
        self.assertEqual(bad["structuredContent"]["error"]["code"], "INVALID_ARGUMENT")


if __name__ == "__main__":
    unittest.main()
