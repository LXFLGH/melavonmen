"""Native intelligence regression and acceptance fixtures; standard unittest runner."""
import importlib.util
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
        db.execute("DELETE FROM files WHERE path='src/pricing.py'")
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

    @unittest.skipUnless(importlib.util.find_spec("tree_sitter_language_pack") and
                         importlib.util.find_spec("tree_sitter"),
                         "install optional tree-sitter language pack")
    def test_tree_sitter_languages(self):
        update(self.root)
        db = connect(self.root, readonly=True)
        for lang, path in (("typescript", "src/main.ts"), ("c_sharp", "src/main.cs"),
                           ("cpp", "src/main.cpp"), ("gdscript", "game/Hero.gd")):
            record = db.execute("SELECT depth FROM files WHERE path=?", (path,)).fetchone()
            self.assertIsNotNone(record, lang)
            self.assertEqual(record["depth"], "deep", lang)
        db.close()

if __name__ == "__main__":
    unittest.main()
