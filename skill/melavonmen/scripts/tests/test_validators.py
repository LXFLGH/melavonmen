"""Run with: python -m unittest discover -s scripts/tests -v"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

SCRIPTS = Path(__file__).resolve().parents[1]


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def png_header(width, height):
    """Minimal PNG header carrying just IHDR; enough to read dimensions and hash."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    body = b"IHDR" + ihdr
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + body
            + struct.pack(">I", zlib.crc32(body)))


class Validators(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        self.source = self.p / "src" / "math.py"
        self.source.parent.mkdir()
        self.source.write_text("def sum_two(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
        sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        save(self.p / "doc" / "index.json", {
            "schema_version": "melavonmen.doc/1", "project": "test", "manifest": {
                "project": "project.json", "modules": [{"id": "math", "path": "modules/math.json"}],
                "contracts": [{"id": "sum", "path": "contracts/sum.json"}]
            }, "task_routes": [{"task": "sum", "read": ["project.json", "contracts/sum.json"]}]
        })
        save(self.p / "doc" / "project.json", {"id": "test"})
        save(self.p / "doc" / "modules" / "math.json", {"id": "math", "source_paths": ["src/math.py"]})
        save(self.p / "doc" / "contracts" / "sum.json", {"id": "sum", "status": "verified"})
        save(self.p / "wiki" / "index.json", {
            "schema_version": "melavonmen.wiki/1", "project": "test", "source_revision": None,
            "total_sources": 1, "indexed_sources": 1, "deep_sources": 1,
            "sources": [{"path": "src/math.py", "sha256": sha, "module_id": "math", "coverage": "deep"}],
            "modules": [{"id": "math", "index": "math/index.json"}],
            "task_routes": [{"task": "sum", "read": ["math/index.json", "math/math.json"]}]
        })
        save(self.p / "wiki" / "math" / "index.json", {
            "module_id": "math", "pages": [{"source_path": "src/math.py", "page": "math/math.json"}]
        })
        save(self.p / "wiki" / "math" / "math.json", {
            "source_path": "src/math.py", "declarations": [
                {"qualified_name": "sum_two", "signature": "def sum_two(a: int, b: int) -> int", "line_start": 1}
            ]
        })

    def run_cli(self, script, *args):
        p = subprocess.run([sys.executable, str(SCRIPTS / script), "--project", str(self.p), *args],
                           capture_output=True, text=True)
        return p.returncode, json.loads(p.stdout)

    def write_assets(self, entries, files):
        root = self.p / "assets"
        for rel, data in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        save(root / "manifest.json", {"schema_version": "melavonmen.assets/1",
                                      "project": "test", "root": "assets", "assets": entries})

    def asset(self, aid, rel, data, **extra):
        entry = {"id": aid, "path": rel, "kind": "texture", "sprites": 1,
                 "width": 32, "height": 32, "sha256": hashlib.sha256(data).hexdigest()}
        entry.update(extra)
        return entry

    def test_asset_one_file_per_sprite_passes(self):
        grass, dirt = png_header(32, 32), png_header(16, 16)
        entries = [self.asset("tile_grass", "tiles/grass.png", grass),
                   self.asset("tile_dirt", "tiles/dirt.png", dirt, width=16, height=16)]
        self.write_assets(entries, {"tiles/grass.png": grass, "tiles/dirt.png": dirt})
        code, report = self.run_cli("validate_assets.py")
        self.assertEqual(code, 0, report)
        self.assertTrue(report["ok"])
        self.assertEqual(report["stats"]["asset_entries"], 2)

    def test_packed_sheet_fails(self):
        sheet = png_header(512, 512)
        entry = self.asset("icons_all", "ui/icons_all.png", sheet, sprites=16, width=512, height=512)
        self.write_assets([entry], {"ui/icons_all.png": sheet})
        code, report = self.run_cli("validate_assets.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("one-asset-per-file" in e for e in report["errors"]))

    def test_asset_size_and_hash_mismatch_fail(self):
        data = png_header(32, 32)
        entry = self.asset("tile", "tiles/t.png", data, width=64)
        entry["sha256"] = "0" * 64
        self.write_assets([entry], {"tiles/t.png": data})
        code, report = self.run_cli("validate_assets.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("sha256 mismatch" in e for e in report["errors"]))
        self.assertTrue(any("width mismatch" in e for e in report["errors"]))

    def test_unregistered_asset_is_warning(self):
        data = png_header(32, 32)
        self.write_assets([self.asset("tile", "tiles/t.png", data)],
                          {"tiles/t.png": data, "tiles/extra.png": png_header(8, 8)})
        code, report = self.run_cli("validate_assets.py")
        self.assertEqual(code, 0, report)
        self.assertTrue(any("not registered" in w for w in report["warnings"]))

    def test_approved_atlas_keeps_per_sprite_files(self):
        sheet, icon = png_header(512, 512), png_header(32, 32)
        entries = [
            self.asset("atlas_ui", "ui/atlas_ui.png", sheet, kind="atlas", sprites=9,
                       width=512, height=512, user_approved=True, atlas_of=["icon_a"]),
            self.asset("icon_a", "icons/icon_a.png", icon),
        ]
        self.write_assets(entries, {"ui/atlas_ui.png": sheet, "icons/icon_a.png": icon})
        code, report = self.run_cli("validate_assets.py")
        self.assertEqual(code, 0, report)
        self.assertFalse(any("one-asset-per-file" in e for e in report["errors"]))

    def test_missing_asset_manifest_fails(self):
        code, report = self.run_cli("validate_assets.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("asset manifest missing" in e for e in report["errors"]))

    def sheet_project(self, frames, extra_entries=(), extra_files=None, sprites=4):
        sheet = png_header(256, 64)
        files = {"characters/walk.png": sheet}
        for name in ("00", "01", "02", "03"):
            files[f"characters/walk_{name}.png"] = png_header(64, 64)
        files.update(extra_files or {})
        entry = self.asset("char_sheet", "characters/walk.png", sheet, kind="sprite_sheet",
                           sprites=sprites, width=256, height=64,
                           atlas="characters/walk.json",
                           source_files=[f"characters/walk_{n}.png" for n in ("00", "01", "02", "03")])
        files["characters/walk.json"] = json.dumps({"image": "characters/walk.png",
                                                    "frames": frames}).encode()
        self.write_assets([entry, *extra_entries], files)
        return self.run_cli("validate_assets.py")

    def test_sprite_sheet_with_atlas_passes(self):
        frames = [{"name": f"walk_{i}", "x": i * 64, "y": 0, "w": 64, "h": 64} for i in range(4)]
        code, report = self.sheet_project(frames)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["stats"]["asset_sprite_sheets"], 1)
        self.assertFalse(any("not registered" in w for w in report["warnings"]))

    def test_sprite_sheet_without_atlas_fails(self):
        sheet = png_header(256, 64)
        entry = self.asset("char_sheet", "characters/walk.png", sheet, kind="sprite_sheet",
                           sprites=4, width=256, height=64)
        self.write_assets([entry], {"characters/walk.png": sheet})
        code, report = self.run_cli("validate_assets.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("requires atlas metadata" in e for e in report["errors"]))

    def test_sprite_sheet_frame_out_of_bounds_fails(self):
        frames = [{"name": f"walk_{i}", "x": i * 64, "y": 0, "w": 64, "h": 64} for i in range(3)]
        frames.append({"name": "walk_3", "x": 224, "y": 0, "w": 64, "h": 64})
        code, report = self.sheet_project(frames)
        self.assertEqual(code, 1)
        self.assertTrue(any("exceeds sheet bounds" in e for e in report["errors"]))

    def test_sprite_sheet_requires_source_frames(self):
        frames = [{"name": f"walk_{i}", "x": i * 64, "y": 0, "w": 64, "h": 64} for i in range(4)]
        sheet = png_header(256, 64)
        entry = self.asset("char_sheet", "characters/walk.png", sheet, kind="sprite_sheet",
                           sprites=4, width=256, height=64, atlas="characters/walk.json")
        atlas = json.dumps({"image": "characters/walk.png", "frames": frames}).encode()
        self.write_assets([entry], {"characters/walk.png": sheet, "characters/walk.json": atlas})
        code, report = self.run_cli("validate_assets.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("requires source_files" in e for e in report["errors"]))


    def test_clean_indexes_schema_and_symbols(self):
        for script in ("validate_index.py", "validate_schema.py", "validate_symbols.py"):
            with self.subTest(script=script):
                code, report = self.run_cli(script)
                self.assertEqual(code, 0, report)
                self.assertTrue(report["ok"])

    def test_missing_doc_route_fails(self):
        path = self.p / "doc" / "index.json"
        data = json.loads(path.read_text())
        data["task_routes"][0]["read"].append("missing.json")
        save(path, data)
        code, report = self.run_cli("validate_index.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("missing.json" in e for e in report["errors"]))

    def test_conflicting_symbol_fails(self):
        path = self.p / "wiki" / "math" / "math.json"
        data = json.loads(path.read_text())
        data["declarations"][0]["signature"] = "def sum_two(a: str) -> str"
        save(path, data)
        code, report = self.run_cli("validate_symbols.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("signature mismatch" in e for e in report["errors"]))

    def test_outdated_source_fails(self):
        self.source.write_text(self.source.read_text() + "# newer\n")
        code, report = self.run_cli("validate_symbols.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("stale source sha256" in e for e in report["errors"]))

    def test_unsafe_path_fails(self):
        path = self.p / "doc" / "index.json"
        data = json.loads(path.read_text())
        data["task_routes"][0]["read"].append("../../etc/passwd")
        save(path, data)
        code, report = self.run_cli("validate_index.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("outside root" in e for e in report["errors"]))

    def test_contract_status_fails(self):
        path = self.p / "doc" / "contracts" / "sum.json"
        data = json.loads(path.read_text())
        data["status"] = "magic"
        save(path, data)
        code, report = self.run_cli("validate_schema.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("invalid status" in e for e in report["errors"]))

    def test_unindexed_source_reported(self):
        subprocess.run(["git", "init", "-q", str(self.p)], check=True)
        subprocess.run(["git", "-C", str(self.p), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.p), "-c", "user.name=test", "-c", "user.email=test@example.test",
                        "commit", "-qm", "baseline"], check=True)
        (self.p / "src" / "new.py").write_text("print(123)\n")
        code, report = self.run_cli("detect_doc_drift.py")
        self.assertEqual(code, 1)
        self.assertTrue(any("source missing" in e for e in report["errors"]))

    def test_drift_reports_changed_source(self):
        subprocess.run(["git", "init", "-q", str(self.p)], check=True)
        subprocess.run(["git", "-C", str(self.p), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.p), "-c", "user.name=test", "-c", "user.email=test@example.test",
                        "commit", "-qm", "baseline"], check=True)
        self.source.write_text(self.source.read_text() + "# changed\n")
        code, report = self.run_cli("detect_doc_drift.py")
        self.assertEqual(code, 1)
        self.assertIn("src/math.py", report["details"]["stale_wiki_sources"])


if __name__ == "__main__":
    unittest.main()
