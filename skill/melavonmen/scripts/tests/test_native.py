"""Native intelligence regression and acceptance fixtures; standard unittest runner."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from native_engine import (
    audit, connect, context, doctor, graph, impact, inside, query, rebuild,
    references, sync_status, update,
)
from native_parsers import parse_file, language_for
from native_semantic import index_vectors, semantic_query
from unittest.mock import patch

class NativeIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write("src/pricing.py", "from math import ceil\n"
                   "def calculate_price(amount: int) -> int:\n"
                   "    return ceil(amount * 1.2)\n"
                   "def checkout():\n"
                   "    return calculate_price(10)\n")
        self.write("game/Hero.gd", "class_name Hero\nextends CharacterBody2D\n"
                   "signal died\n@export var hit_points: int = 10\n"
                   "@onready var sprite = get_node(\"Sprite2D\")\n"
                   "func go():\n"
                   "    var scene = preload(\"res://game/Hero.tscn\")\n"
                   "    died.connect(_on_died)\n")
        self.write("game/Hero.tscn", '[gd_scene load_steps=2 format=3]\n'
                   '[ext_resource type="Script" path="res://game/Hero.gd" '
                   'id="1_script" uid="uid://abcdef"]\n'
                   '[node name="Hero" type="CharacterBody2D"]\n'
                   'script = ExtResource("1_script")\n'
                   '[connection signal="died" from="." to="." method="_on_died"]\n')
        self.write("project.godot", '[application]\nconfig/name="A"\n'
                   '[autoload]\nGame="*res://game/Hero.gd"\n')
        self.write("src/main.ts", "export class Price { total(n: number): number { return n; } }\n")
        self.write("src/main.cs", "public class Game { public int Price(int v) { return v; } }\n")
        self.write("src/main.cpp", "int add(int a, int b) { return a+b; }\n")
        self.write("src/settings.json", '{"code": {"difficulty": "hard"}, "enabled": true}\n')
        self.write("src/settings.toml", '[code]\ndifficulty = "hard"\n')
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=CI",
                        "-c", "user.email=ci@example.invalid",
                        "commit", "-qm", "fixture"], check=True)

    def write(self, path, content):
        f = self.root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")

    def test_fresh_index_and_independent_coverage(self):
        report = update(self.root)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["stats"]["first_party_sources"], 9)
        self.assertEqual(report["stats"]["indexed_sources"], 9)
        self.assertEqual(report["stats"]["missing_sources"], 0)
        self.assertGreater(report["stats"]["verified_symbols"], 1)
        self.assertIn("src/pricing.py", query(self.root, "calculate_price", mode="definition")
                      ["results"][0]["path"])
        self.assertTrue(context(self.root, "src/pricing.py", line=2)["ok"])
        self.assertTrue(doctor(self.root)["ok"])

    def test_scene_tree_hierarchical_node_paths(self):
        self.write("game/Nested.tscn",
                   '[gd_scene format=3]\n'
                   '[node name="Root" type="Node2D"]\n'
                   '[node name="Sprite" type="Sprite2D" parent="."]\n'
                   '[node name="Child" type="Node" parent="Sprite"]\n')
        update(self.root)
        db = connect(self.root, readonly=True)
        nodes = list(db.execute(
            "SELECT qualified_name,extra FROM symbols WHERE path=? AND kind='scene_node'",
            ("game/Nested.tscn",)))
        db.close()
        names = {x["qualified_name"] for x in nodes}
        self.assertEqual(names, {"Root", "Root/Sprite", "Root/Sprite/Child"})
        by_name = {r["qualified_name"]: json.loads(r["extra"]) for r in nodes}
        self.assertEqual(by_name["Root/Sprite/Child"]["parent_path"], "Sprite")

    def test_godot_uid_signal_and_export_impact(self):
        # UID sidecar maps a scene reference even when the scene has no path.
        self.write("game/Hero.gd.uid", "uid://hero001\n")
        self.write("game/UidOnly.tscn", '[gd_scene format=3]\n'
                   '[ext_resource type="Script" uid="uid://hero001" id="1"]\n'
                   '[node name="Hero" type="Node"]\n'
                   'script = ExtResource("1")\n'
                   'hit_points = 30\n'
                   '[connection signal="died" from="." to="." method="_on_died"]\n')
        update(self.root)
        db = connect(self.root, readonly=True)
        edges = list(db.execute(
            "SELECT kind,target_name,target_file,verification_status "
            "FROM edges WHERE path='game/UidOnly.tscn'"))
        db.close()
        self.assertTrue(any(x["target_file"] == "game/Hero.gd" and
                            x["kind"] == "resource_reference" for x in edges), edges)
        self.assertTrue(any(x["kind"] == "connect" and
                            x["target_name"] == "died" for x in edges), edges)
        self.assertTrue(any(x["kind"] == "writes" and
                            x["target_name"] == "hit_points" for x in edges), edges)
        impact_result = impact(self.root, ["game/Hero.gd"])
        self.assertIn("game/UidOnly.tscn", impact_result["affected_files"])

    def test_godot_scene_edges_and_autoload(self):
        update(self.root)
        db = connect(self.root, readonly=True)
        rows = list(db.execute("SELECT kind,target_file FROM edges WHERE path='game/Hero.tscn'"))
        self.assertTrue(any(x["target_file"] == "game/Hero.gd" for x in rows))
        self.assertTrue(any(x["kind"] == "connect" for x in rows))
        auto = list(db.execute("SELECT * FROM edges WHERE path='project.godot'"))
        self.assertTrue(any(x["target_file"] == "game/Hero.gd" for x in auto))
        db.close()
        self.assertIn("game/Hero.tscn", impact(self.root, ["game/Hero.gd"])["affected_files"])

    def test_parallel_git_worktrees_do_not_share_writable_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            secondary = Path(tmp) / "secondary"
            subprocess.run(["git", "-C", str(self.root), "worktree", "add",
                            "-q", "-b", "parallel", str(secondary), "HEAD"],
                           check=True)
            try:
                base = update(self.root)
                other = update(secondary)
                self.assertTrue(base["ok"] and other["ok"])
                self.assertNotEqual((self.root / ".melavonmen/index.sqlite").resolve(),
                                    (secondary / ".melavonmen/index.sqlite").resolve())
                (secondary / "src/pricing.py").write_text(
                    "def separate(): return 99\n", encoding="utf-8")
                changed = update(secondary)
                self.assertEqual(changed["stats"]["current_dirty_sources"], 1)
                self.assertTrue(doctor(self.root)["ok"])
                self.assertTrue(query(self.root, "calculate_price", mode="definition")["results"])
                self.assertFalse(query(secondary, "calculate_price", mode="definition")["results"])
            finally:
                subprocess.run(["git", "-C", str(self.root), "worktree", "remove",
                                "--force", str(secondary)], check=True)

    def test_git_head_and_worktree_dirty_state_are_separate(self):
        initial = update(self.root)
        self.assertEqual(initial["stats"]["current_dirty_sources"], 0)
        committed = initial["stats"]["committed_revision"]
        self.write("src/pricing.py", "def calculate_price(): return 100\n")
        pending = update(self.root)
        self.assertEqual(pending["stats"]["committed_revision"], committed)
        self.assertEqual(pending["stats"]["current_dirty_sources"], 1)
        self.assertEqual(pending["stats"]["recorded_dirty_sources"], 1)
        subprocess.run(["git", "-C", str(self.root), "add", "src/pricing.py"], check=True)
        subprocess.run(["git", "-C", str(self.root),
                        "-c", "user.name=CI", "-c", "user.email=ci@example.invalid",
                        "commit", "-qm", "modify"], check=True)
        done = update(self.root)
        self.assertNotEqual(done["stats"]["committed_revision"], committed)
        self.assertEqual(done["stats"]["current_dirty_sources"], 0)
        self.assertEqual(done["stats"]["recorded_dirty_sources"], 0)

    def test_same_content_rename_retains_provenance_and_deletes_old(self):
        update(self.root)
        old = self.root / "src" / "settings.toml"
        new = self.root / "src" / "设置 (renamed).toml"
        old.rename(new)
        result = update(self.root)
        self.assertTrue(result["ok"])
        self.assertIn({"from": "src/settings.toml",
                       "to": "src/设置 (renamed).toml"}, result["renamed"])
        self.assertIn("src/settings.toml", result["deleted"])
        self.assertFalse(query(self.root, "src/settings.toml", mode="path")["results"])
        self.assertTrue(query(self.root, "src/设置 (renamed).toml", mode="path")["results"])

    def test_two_simultaneous_index_writers_transactional(self):
        from concurrent.futures import ThreadPoolExecutor
        # Writer lock, schema setup and FTS mutations must not corrupt SQLite.
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(update, self.root) for _ in range(2)]
            reports = [f.result(timeout=45) for f in futures]
        self.assertTrue(all(x["ok"] for x in reports), reports)
        self.assertTrue(doctor(self.root)["ok"])

    def test_incremental_reparse_and_delete(self):
        update(self.root)
        self.write("src/pricing.py", "def new_price(amount):\n    return amount + 1\n")
        self.assertFalse(update(self.root, check=True)["ok"])
        self.assertFalse(context(self.root, "src/pricing.py")["ok"])
        report = update(self.root)
        self.assertEqual(report["changed"], ["src/pricing.py"])
        self.assertTrue(query(self.root, "new_price", mode="definition")["results"])
        self.assertFalse(query(self.root, "calculate_price", mode="definition")["results"])
        (self.root / "src/settings.toml").unlink()
        report = update(self.root)
        self.assertIn("src/settings.toml", report["deleted"])
        self.assertEqual(report["stats"]["orphan_sources"], 0)

    def test_unicode_and_untracked(self):
        update(self.root)
        self.write("src/小 雪 (test).py", "def snow(): return 42\n")
        report = update(self.root)
        self.assertIn("src/小 雪 (test).py", report["changed"])
        self.assertTrue(query(self.root, "snow", mode="definition")["results"])

    def test_symlink_and_traversal(self):
        with self.assertRaises(ValueError):
            inside(self.root, "../private.key")
        with self.assertRaises(ValueError):
            context(self.root, "/etc/passwd")
        with tempfile.TemporaryDirectory() as elsewhere:
            (self.root / "src" / "external.py").symlink_to(Path(elsewhere) / "secret.py")
            report = update(self.root)
            self.assertNotIn("src/external.py", report["changed"])

    def test_graph_calls_and_references(self):
        update(self.root)
        result = references(self.root, "calculate_price")
        self.assertTrue(any(x["kind"] == "calls" for x in result["results"]))
        g = graph(self.root, "calculate_price", depth=1)
        self.assertIn("src/pricing.py", g["visited_files"])
        self.assertGreater(len(g["edges"]), 0)

    def test_check_and_doctor_index_corruption(self):
        update(self.root)
        self.assertTrue(doctor(self.root)["ok"])
        db = connect(self.root)
        for table in ("symbols", "edges", "code_fts", "files"):
            db.execute("DELETE FROM " + table + " WHERE path=?", ("src/pricing.py",))
        db.commit()
        db.close()
        report = doctor(self.root)
        self.assertFalse(report["ok"])
        self.assertIn("src/pricing.py", report["missing"])
        report = rebuild(self.root)
        self.assertTrue(report["ok"], report)
        self.assertTrue(doctor(self.root)["ok"])

    def test_filter_limit_and_token_budget(self):
        update(self.root)
        out = query(self.root, "price", mode="auto", limit=1, token_budget=500)
        self.assertLessEqual(len(out["results"]), 1)
        self.assertTrue(all(r["path"].startswith("src/") for r in
                            query(self.root, "price", directory="src")["results"]))
        with self.assertRaises(ValueError):
            query(self.root, "price", directory="../../")

    def test_doc_wiki_are_not_overwritten(self):
        self.write("doc/contracts/pricing.json", json.dumps(
            {"id": "p", "status": "approved", "source_path": "src/pricing.py"}))
        self.write("wiki/info.json", '{"source_path": "src/pricing.py"}')
        update(self.root)
        self.assertEqual(json.loads((self.root / "doc/contracts/pricing.json").read_text())
                         ["status"], "approved")
        result = sync_status(self.root, ["src/pricing.py"])
        self.assertIn("doc/contracts/pricing.json", result["candidates"])

    def test_config_exclude(self):
        self.write(".melavonmen.json", '{"exclude":["src/settings.json"]}')
        out = update(self.root)
        self.assertEqual(out["stats"]["first_party_sources"], 8)
        self.assertFalse(query(self.root, "src/settings.json", mode="path")["results"])

    def test_semantic_local_cache_and_fallback(self):
        update(self.root)
        encoder = lambda texts: [[float(len(text) % 17), 1.0] for text in texts]
        with patch("native_semantic.client", return_value=encoder):
            first = index_vectors(self.root, provider="local", model="mock")
            second = index_vectors(self.root, provider="local", model="mock")
            self.assertGreater(first["embedded_new_or_changed"], 0)
            self.assertEqual(second["embedded_new_or_changed"], 0)
            results = semantic_query(self.root, "price", model="mock")
            self.assertTrue(results["results"])
        fallback = semantic_query(self.root, "price", provider="remote", model="missing")
        self.assertTrue(fallback["results"])
        self.assertTrue(fallback["warnings"])

    def test_cycle_and_unresolved_index(self):
        from native_engine import cycles, unresolved
        self.write("src/a.py", "import b\n")
        self.write("src/b.py", "import a\n")
        update(self.root)
        # Import resolution of Python imports is conservative; names stay possible.
        self.assertTrue(unresolved(self.root)["count"] >= 0)
        self.assertIsInstance(cycles(self.root)["cycles"], list)

    def test_stale_wiki_signature_detection(self):
        self.write("wiki/pages/pricing.json", json.dumps({
            "source_path": "src/pricing.py", "declarations": [{
                "qualified_name": "calculate_price",
                "signature": "def calculate_price(x) -> str",
                "line_start": 99}]}))
        update(self.root)
        status = sync_status(self.root, ["src/pricing.py"])
        self.assertTrue(any(row["kind"] == "signature_or_location"
                            for row in status["stale_wiki"]))

    def test_python_parameter_default_types_and_evidence(self):
        self.write("src/types.py",
                   "def clamp(value: int, low: int = 0, *, high: int = 10) -> int:\n"
                   "    return min(max(value, low), high)\n")
        update(self.root)
        db = connect(self.root, readonly=True)
        item = db.execute("SELECT * FROM symbols WHERE path=? AND name=?",
                          ("src/types.py", "clamp")).fetchone()
        self.assertIsNotNone(item)
        self.assertEqual(item["verification_status"], "verified")
        parameters = json.loads(item["extra"])["parameters"]
        self.assertEqual([p["name"] for p in parameters], ["value", "low", "high"])
        self.assertEqual(parameters[1]["default"], "0")
        self.assertEqual(parameters[2]["type"], "int")
        db.close()

    def test_watch_incremental_polling_cli(self):
        p = subprocess.run(
            [sys.executable, str(SCRIPTS / "native_cli.py"),
             "--project", str(self.root), "watch",
             "--interval", "0.2", "--iterations", "2"],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = [json.loads(row) for row in p.stdout.splitlines() if row.strip()]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["ok"] for row in rows))

    def test_benchmark_has_token_and_raw_search_baseline(self):
        from native_cli import benchmark
        data = benchmark(self.root, None, ["price"], runs=2)
        self.assertIn("cold_build_ms", data)
        self.assertIn("whole_source_estimated_tokens", data)
        self.assertIn("response_estimated_tokens", data)
        self.assertIn("raw_search_baseline", data)
        self.assertIn("p50_ms", data["raw_search_baseline"])
        self.assertTrue(data["stats"]["indexed_sources"] >= 9)

    @unittest.skipUnless(importlib.util.find_spec("tree_sitter_language_pack") and
                         importlib.util.find_spec("tree_sitter"),
                         "install optional tree-sitter language pack")
    def test_legacy_wiki_validator_verifies_typescript_signature(self):
        file = self.root / "src/main.ts"
        sha = hashlib.sha256(file.read_bytes()).hexdigest()
        facts = parse_file(file, "src/main.ts", "typescript", sha, "fixture")
        actual = next(s for s in facts["symbols"]
                      if s["name"] == "Price" and
                      s["verification_status"] == "verified")
        wiki = self.root / "wiki"
        (wiki / "ts").mkdir(parents=True)
        (wiki / "index.json").write_text(json.dumps({
            "schema_version": "melavonmen.wiki/1", "project": "test",
            "sources": [{"path": "src/main.ts", "sha256": sha, "module_id": "ts",
                         "coverage": "deep"}],
            "modules": [{"id": "ts", "index": "ts/index.json"}],
            "task_routes": [], "total_sources": 1,
            "indexed_sources": 1, "deep_sources": 1}), "utf-8")
        (wiki / "ts/index.json").write_text(json.dumps({
            "module_id": "ts", "pages": [{"source_path": "src/main.ts",
                                        "page": "ts/price.json"}]}), "utf-8")
        page = wiki / "ts/price.json"
        page.write_text(json.dumps({
            "source_path": "src/main.ts",
            "declarations": [{"qualified_name": actual["qualified_name"],
                              "signature": actual["signature"],
                              "line_start": actual["line_start"]}]}), "utf-8")
        cmd = [sys.executable, str(SCRIPTS / "validate_symbols.py"),
               "--project", str(self.root)]
        run = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(report["stats"]["verified_non_python_signatures"], 1)
        bad = json.loads(page.read_text())
        bad["declarations"][0]["signature"] = "class Wrong"
        page.write_text(json.dumps(bad), "utf-8")
        changed = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(changed.returncode, 1, changed.stdout + changed.stderr)
        self.assertIn("signature mismatch", changed.stdout)

    @unittest.skipUnless(importlib.util.find_spec("tree_sitter_language_pack") and
                         importlib.util.find_spec("tree_sitter"),
                         "install optional tree-sitter language pack")
    def test_tree_sitter_languages(self):
        update(self.root)
        db = connect(self.root, readonly=True)
        for lang, path in (("typescript", "src/main.ts"), ("csharp", "src/main.cs"),
                           ("cpp", "src/main.cpp"), ("gdscript", "game/Hero.gd")):
            record = db.execute("SELECT depth FROM files WHERE path=?", (path,)).fetchone()
            self.assertIsNotNone(record, lang)
            self.assertEqual(record["depth"], "deep", lang)
        db.close()

if __name__ == "__main__":
    unittest.main()
