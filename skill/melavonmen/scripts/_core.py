"""melavonmen AI documentation validators. Python 3.10+, stdlib only.

These tools check machine-verifiable properties; they do not certify behavior.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
ASSET_MANIFESTS = ("assets/manifest.json", "assets/index.json", "doc/assets.json")
ATLAS_WORDS = ("sheet", "atlas", "tileset", "spritesheet", "contact")
SOF_CODES = (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF)


def emit(mode, errors, warnings, stats, details=None):
    result = {"tool": mode, "ok": not errors, "errors": errors,
              "warnings": warnings, "stats": stats, "details": details or {}}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if errors else 0


def load(path, errors):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"unreadable JSON {path}: {exc}")
        return None


def resolve(root, relative, errors, label):
    if not isinstance(relative, str) or not relative.strip():
        errors.append(f"{label}: missing relative path")
        return None
    if Path(relative).is_absolute():
        errors.append(f"{label}: absolute path forbidden: {relative}")
        return None
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        errors.append(f"{label}: outside root: {relative}")
        return None
    if not path.is_file():
        errors.append(f"{label}: missing file: {relative}")
        return None
    return path


def entries(value):
    return value if isinstance(value, list) else []


def manifest_paths(doc):
    manifest = doc.get("manifest", {})
    if not isinstance(manifest, dict):
        return []
    results = []
    for key, group in manifest.items():
        if isinstance(group, str):
            results.append((key, group))
        elif isinstance(group, list):
            for i, item in enumerate(group):
                if isinstance(item, dict) and "path" in item:
                    results.append((f"{key}[{i}]", item["path"]))
    return results


def index(project, errors, warnings, stats):
    present = False
    for kind in ("doc", "wiki"):
        root = project / kind
        if not root.exists():
            continue
        present = True
        main = load(root / "index.json", errors)
        if not isinstance(main, dict):
            continue
        if kind == "doc":
            for label, path in manifest_paths(main):
                resolve(root, path, errors, f"doc.manifest.{label}")
        else:
            modules = {}
            source_paths = set()
            for i, module in enumerate(entries(main.get("modules"))):
                mid = module.get("id") if isinstance(module, dict) else None
                p = resolve(root, module.get("index") if isinstance(module, dict) else None,
                            errors, f"wiki.modules[{i}].index")
                if mid in modules:
                    errors.append(f"duplicate wiki module id: {mid}")
                modules[mid] = p
                if p:
                    sub = load(p, errors)
                    if isinstance(sub, dict):
                        for j, page in enumerate(entries(sub.get("pages"))):
                            if not isinstance(page, dict):
                                errors.append(f"wiki {mid}.pages[{j}] not an object")
                                continue
                            resolve(root, page.get("page"), errors, f"wiki {mid}.pages[{j}]")
                            if isinstance(page.get("source_path"), str):
                                source_paths.add(page["source_path"])
            inventory = entries(main.get("sources"))
            seen = set()
            for i, item in enumerate(inventory):
                if not isinstance(item, dict):
                    errors.append(f"wiki.sources[{i}] not an object")
                    continue
                src = item.get("path")
                if not isinstance(src, str):
                    errors.append(f"wiki.sources[{i}].path must be a string")
                    continue
                if src in seen:
                    errors.append(f"duplicate source in wiki inventory: {src}")
                seen.add(src)
                resolve(project, src, errors, f"wiki.sources[{i}]")
                if item.get("module_id") not in modules:
                    errors.append(f"wiki.sources[{i}] refers to unknown module: {item.get('module_id')}")
                if item.get("coverage") == "deep" and src not in source_paths:
                    errors.append(f"deep source lacks a module page: {src}")
            if main.get("total_sources") != len(inventory):
                errors.append("wiki.total_sources disagrees with inventory length")
            if main.get("indexed_sources") != len(seen):
                errors.append("wiki.indexed_sources disagrees with unique inventory count")
            deep = sum(isinstance(s, dict) and s.get("coverage") == "deep" for s in inventory)
            if main.get("deep_sources") != deep:
                errors.append("wiki.deep_sources disagrees with inventory coverage")
            # Cross-check the declared Wiki inventory against an independently
            # enumerated first-party source set. The existing len(sources) checks
            # cannot prove coverage, even if every declared row is valid.
            try:
                from native_engine import config as native_config, discover as native_discover
                from native_parsers import language_for
                actual_sources, physical = native_discover(project, native_config(project))
                registered_supported = {p for p in seen if language_for(p)}
                missing_in_wiki = sorted(actual_sources - registered_supported)
                extra_in_wiki = sorted(registered_supported - actual_sources)
                errors.extend(f"wiki source not registered in independent scan: {p}"
                              for p in extra_in_wiki)
                errors.extend(f"first-party source missing from wiki inventory: {p}"
                              for p in missing_in_wiki)
                stats["wiki_independent_first_party_sources"] = len(physical)
                stats["wiki_independent_missing_sources"] = len(missing_in_wiki)
                stats["wiki_independent_orphan_sources"] = len(extra_in_wiki)
            except (OSError, ValueError, ImportError) as exc:
                warnings.append("independent source audit unavailable: " + str(exc))
            stats["wiki_total_sources"] = len(inventory)
            stats["wiki_deep_sources"] = deep
        for i, route in enumerate(entries(main.get("task_routes"))):
            if not isinstance(route, dict):
                errors.append(f"{kind}.task_routes[{i}] not an object")
                continue
            for j, path in enumerate(entries(route.get("read"))):
                resolve(root, path, errors, f"{kind}.task_routes[{i}].read[{j}]")
        stats[kind + "_present"] = True
    if not present:
        errors.append("neither doc/index.json nor wiki/index.json exists")


def schema(project, errors, warnings, stats):
    found_any = False
    for kind, prefix in (("doc", "melavonmen.doc/"), ("wiki", "melavonmen.wiki/")):
        root = project / kind
        if not root.exists():
            continue
        found_any = True
        main = load(root / "index.json", errors)
        if not isinstance(main, dict):
            continue
        if not isinstance(main.get("schema_version"), str) or not main["schema_version"].startswith(prefix):
            errors.append(f"{kind}: invalid schema_version")
        if not isinstance(main.get("project"), str) or not main["project"]:
            errors.append(f"{kind}: project required")
        if not isinstance(main.get("task_routes"), list):
            errors.append(f"{kind}: task_routes must be a list")
        if kind == "doc":
            if not isinstance(main.get("manifest"), dict):
                errors.append("doc.manifest must be an object")
            all_ids = set()
            manifest = main.get("manifest", {})
            for key, arr in (manifest if isinstance(manifest, dict) else {}).items():
                if not isinstance(arr, list):
                    continue
                for item in arr:
                    if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("path"), str):
                        errors.append(f"doc manifest {key} must include id and path")
                        continue
                    compound = (key, item["id"])
                    if compound in all_ids:
                        errors.append(f"doc manifest duplicate id: {compound}")
                    all_ids.add(compound)
                    page = load(root / item["path"], errors) if resolve(root, item["path"], errors, key) else None
                    if isinstance(page, dict) and key == "contracts":
                        if page.get("status") not in ("proposed", "approved", "implemented", "verified", "deprecated"):
                            errors.append(f"contract {item['id']} has invalid status")
        else:
            for key in ("sources", "modules"):
                if not isinstance(main.get(key), list):
                    errors.append(f"wiki.{key} must be a list")
            for s in entries(main.get("sources")):
                if not isinstance(s, dict):
                    errors.append("wiki.sources entry must be an object")
                    continue
                if s.get("coverage") not in ("indexed", "deep"):
                    errors.append("wiki.sources entry has invalid coverage")
                elif not isinstance(s.get("sha256"), str) or len(s["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in s["sha256"].lower()):
                    errors.append(f"wiki.sources {s.get('path')}: sha256 must be 64 hex chars")
        stats[kind + "_checked"] = True
    if not found_any:
        errors.append("neither doc nor wiki present")


def python_symbols(source):
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    found = {}
    def walk(nodes, prefix=""):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                key = prefix + node.name
                if isinstance(node, ast.ClassDef):
                    sig = f"class {node.name}"
                else:
                    kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                    sig = f"{kind} {node.name}({ast.unparse(node.args)}){returns}"
                found[key] = (sig, node.lineno)
                walk(node.body, key + ".")
    walk(tree.body)
    return found


def symbols(project, errors, warnings, stats):
    wiki = project / "wiki"
    if not wiki.is_dir():
        errors.append("wiki/index.json required for symbol validation")
        return
    data = load(wiki / "index.json", errors)
    if not isinstance(data, dict):
        return
    validated = 0
    unverified = 0
    cache = {}
    inventory_paths = {s.get("path") for s in entries(data.get("sources")) if isinstance(s, dict) and isinstance(s.get("path"), str)}
    for s in entries(data.get("sources")):
        if not isinstance(s, dict):
            continue
        path = resolve(project, s.get("path"), errors, "source")
        if not path:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if s.get("sha256") != digest:
            errors.append(f"stale source sha256: {s.get('path')}")
    for m in entries(data.get("modules")):
        if not isinstance(m, dict):
            continue
        mod = resolve(wiki, m.get("index"), errors, "module")
        if not mod:
            continue
        mid = load(mod, errors)
        if not isinstance(mid, dict):
            continue
        for page in entries(mid.get("pages")):
            if not isinstance(page, dict):
                continue
            path = resolve(wiki, page.get("page"), errors, "wiki page")
            if not path:
                continue
            item = load(path, errors)
            if not isinstance(item, dict):
                continue
            if item.get("source_path") not in inventory_paths:
                errors.append(f"wiki page not in source inventory: {item.get('source_path')}")
            src = resolve(project, item.get("source_path"), errors, "wiki page source")
            if not src:
                continue
            decls = entries(item.get("declarations"))
            if src.suffix != ".py":
                unverified += len(decls)
                if decls:
                    warnings.append(f"{item.get('source_path')}: non-Python symbols require external language parser; signatures not certified")
                continue
            if src not in cache:
                try:
                    cache[src] = python_symbols(src)
                except (SyntaxError, UnicodeError) as exc:
                    errors.append(f"Python AST parse failed {src}: {exc}")
                    continue
            actual = cache[src]
            for d in decls:
                if not isinstance(d, dict):
                    errors.append(f"malformed declaration in {path}")
                    continue
                key = d.get("qualified_name")
                if key not in actual:
                    errors.append(f"symbol missing: {item.get('source_path')}:{key}")
                    continue
                sig, line = actual[key]
                if d.get("signature") != sig:
                    errors.append(f"signature mismatch: {key}: documented={d.get('signature')!r} actual={sig!r}")
                elif d.get("line_start") is not None and d["line_start"] != line:
                    errors.append(f"line drift: {key}: documented={d['line_start']} actual={line}")
                else:
                    validated += 1
    stats["verified_python_signatures"] = validated
    stats["unverified_non_python_signatures"] = unverified


def git_changed(project, base, errors):
    try:
        result = subprocess.run(["git", "-C", str(project), "diff", "--name-only", "--diff-filter=ACMRTD", base, "--"],
                                capture_output=True, text=True, check=True)
        tracked = {x for x in result.stdout.splitlines() if x}
        result = subprocess.run(["git", "-C", str(project), "ls-files", "--others", "--exclude-standard"],
                                capture_output=True, text=True, check=True)
        return tracked | set(result.stdout.splitlines())
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"git diff failed: {exc}")
        return set()


def drift(project, base, errors, warnings, stats, details):
    changed = git_changed(project, base, errors)
    code = set()
    docs = set()
    wiki = set()
    for f in changed:
        if f.startswith("doc/"):
            docs.add(f)
        elif f.startswith("wiki/"):
            wiki.add(f)
        else:
            code.add(f)
    inventory = {}
    root = project / "wiki" / "index.json"
    if root.is_file():
        data = load(root, errors)
        if isinstance(data, dict):
            inventory = {x.get("path"): x for x in entries(data.get("sources")) if isinstance(x, dict) and isinstance(x.get("path"), str)}
    changed_indexed = sorted(set(code) & set(inventory))
    code_ext = {".py", ".js", ".jsx", ".ts", ".tsx", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".java", ".gd", ".lua", ".swift", ".kt"}
    unindexed_source = sorted(f for f in code if f not in inventory and Path(f).suffix.lower() in code_ext and not f.startswith(("vendor/", "node_modules/", "dist/", "build/")))
    if unindexed_source and root.is_file():
        errors.extend(f"source missing from wiki inventory: {f}" for f in unindexed_source)
    stale = []
    for src in changed_indexed:
        p = project / src
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != inventory[src].get("sha256"):
            stale.append(src)
    if stale:
        errors.extend(f"stale wiki source hash: {s}" for s in stale)
    if changed_indexed and not wiki:
        warnings.append("changed indexed source with no changed wiki files; review wiki sync")
    if code and not docs and (project / "doc").is_dir():
        warnings.append("code changed but no Doc files changed; review whether contracts are affected")
    unknown = sorted(f for f in code if not f.startswith(".") and f not in inventory)
    if unknown:
        warnings.append("non-inventoried changed files require classification; may include new source files")
    stats.update(changed_files=len(changed), changed_code_candidates=len(code), changed_indexed_sources=len(changed_indexed))
    details.update(changed_code_candidates=sorted(code), stale_wiki_sources=stale,
                   changed_doc=sorted(docs), changed_wiki=sorted(wiki), noninventoried=unknown, unindexed_source=unindexed_source)


def _jpeg_size(handle):
    handle.seek(2)
    while True:
        byte = handle.read(1)
        if not byte:
            return None
        if byte != b"\xff":
            continue
        code_byte = handle.read(1)
        while code_byte == b"\xff":
            code_byte = handle.read(1)
        if not code_byte:
            return None
        code = code_byte[0]
        if code in (0xD8, 0xD9, 0x01) or 0xD0 <= code <= 0xD7:
            continue
        raw = handle.read(2)
        if len(raw) < 2:
            return None
        length = struct.unpack(">H", raw)[0]
        if code in SOF_CODES:
            handle.read(1)
            dims = handle.read(4)
            if len(dims) < 4:
                return None
            height, width = struct.unpack(">HH", dims)
            return width, height
        handle.seek(length - 2, 1)


def image_size(path):
    """Read raster dimensions from a file header; None when the format is unsupported."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(32)
            if head.startswith(b"\x89PNG\r\n\x1a\n"):
                return struct.unpack(">II", head[16:24]) if len(head) >= 24 else None
            if head[:6] in (b"GIF87a", b"GIF89a") and len(head) >= 10:
                return struct.unpack("<HH", head[6:10])
            if head[:2] == b"BM" and len(head) >= 26:
                width, height = struct.unpack("<ii", head[18:26])
                return abs(width), abs(height)
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                chunk = head[12:16]
                if chunk == b"VP8X" and len(head) >= 30:
                    return (int.from_bytes(head[24:27], "little") + 1,
                            int.from_bytes(head[27:30], "little") + 1)
                if chunk == b"VP8 ":
                    handle.seek(26)
                    dims = handle.read(4)
                    if len(dims) == 4:
                        width, height = struct.unpack("<HH", dims)
                        return width & 0x3FFF, height & 0x3FFF
                    return None
                if chunk == b"VP8L":
                    handle.seek(20)
                    payload = handle.read(5)
                    if len(payload) == 5 and payload[0] == 0x2F:
                        bits = int.from_bytes(payload[1:5], "little")
                        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
                    return None
                return None
            if head[:2] == b"\xff\xd8":
                return _jpeg_size(handle)
    except OSError:
        return None
    return None


def sprite_sheet(item, aid, root, actual, registered, errors):
    """A sprite sheet is legal only if atlas metadata covers every frame and per-frame files exist."""
    rel = item.get("atlas")
    if not isinstance(rel, str) or not rel.strip():
        errors.append(f"asset {aid}: sprite_sheet requires atlas metadata (field: atlas)")
        return
    atlas_path = (root / rel).resolve()
    if not atlas_path.is_relative_to(root) or not atlas_path.is_file():
        errors.append(f"asset {aid}: atlas metadata missing or outside asset root: {rel}")
        return
    try:
        meta = json.loads(atlas_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"asset {aid}: unreadable atlas {rel}: {exc}")
        return
    frames = meta.get("frames") if isinstance(meta, dict) else None
    if not isinstance(frames, list) or not frames:
        errors.append(f"asset {aid}: atlas frames must be a non-empty list")
        return
    names = set()
    for j, frame in enumerate(frames):
        if not isinstance(frame, dict):
            errors.append(f"asset {aid}: atlas frame[{j}] not an object")
            continue
        label = frame.get("name")
        if not isinstance(label, str) or not label.strip():
            errors.append(f"asset {aid}: atlas frame[{j}] missing name")
            label = f"#{j}"
        elif label in names:
            errors.append(f"asset {aid}: duplicate frame name: {label}")
        else:
            names.add(label)
        rect = [frame.get(k) for k in ("x", "y", "w", "h")]
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in rect):
            errors.append(f"asset {aid}: frame {label} needs integer x/y/w/h")
            continue
        x, y, width, height = rect
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            errors.append(f"asset {aid}: frame {label} has an invalid rect")
            continue
        if actual and (x + width > actual[0] or y + height > actual[1]):
            errors.append(f"asset {aid}: frame {label} exceeds sheet bounds {actual[0]}x{actual[1]}")
    if len(frames) != item.get("sprites"):
        errors.append(f"asset {aid}: sprites={item.get('sprites')} but atlas describes {len(frames)} frames")
    sources = item.get("source_files")
    if not isinstance(sources, list) or not sources:
        errors.append(f"asset {aid}: sprite_sheet requires source_files (per-frame decoupled assets)")
        return
    for rel_src in sources:
        if not isinstance(rel_src, str) or not rel_src.strip():
            errors.append(f"asset {aid}: source_files entry must be a path string")
            continue
        src = (root / rel_src).resolve()
        if not src.is_relative_to(root) or not src.is_file():
            errors.append(f"asset {aid}: source frame missing: {rel_src}")
            continue
        registered.add(src)


def assets(project, errors, warnings, stats, details, manifest=None):
    """Enforce one-asset-per-file delivery: sprites == 1, declared size/hash match the file."""
    target = None
    if manifest:
        candidate = Path(manifest)
        target = candidate if candidate.is_absolute() else project / candidate
        if not target.is_file():
            errors.append(f"asset manifest not found: {manifest}")
            return
    else:
        target = next((project / p for p in ASSET_MANIFESTS if (project / p).is_file()), None)
        if target is None:
            errors.append("asset manifest missing (expected assets/manifest.json)")
            return
    data = load(target, errors)
    if not isinstance(data, dict):
        return
    if not str(data.get("schema_version", "")).startswith("melavonmen.assets/"):
        errors.append("assets: invalid schema_version")
    root_rel = data.get("root", "assets")
    if not isinstance(root_rel, str) or not root_rel.strip():
        errors.append("assets.root must be a non-empty string")
        return
    root = (project / root_rel).resolve()
    if not root.is_relative_to(project.resolve()):
        errors.append(f"assets.root outside project: {root_rel}")
        return
    entries_list = data.get("assets")
    if not isinstance(entries_list, list):
        errors.append("assets.assets must be a list")
        return
    ids = set()
    owners = {}
    registered = set()
    approved_atlases = 0
    sprite_sheets = 0
    for i, item in enumerate(entries_list):
        if not isinstance(item, dict):
            errors.append(f"assets[{i}] not an object")
            continue
        aid = item.get("id")
        if not isinstance(aid, str) or not aid.strip():
            errors.append(f"assets[{i}].id required")
            aid = f"#{i}"
        elif aid in ids:
            errors.append(f"duplicate asset id: {aid}")
        ids.add(aid)
        rel = item.get("path")
        if not isinstance(rel, str) or not rel.strip():
            errors.append(f"asset {aid}: path required")
            continue
        path = (root / rel).resolve()
        if not path.is_relative_to(root):
            errors.append(f"asset {aid}: path outside asset root: {rel}")
            continue
        if rel in owners:
            errors.append(f"asset file registered twice: {rel} (ids: {owners[rel]}, {aid})")
        owners.setdefault(rel, aid)
        registered.add(path)
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            warnings.append(f"asset {aid}: not a known raster format: {rel}")
        if not path.is_file():
            errors.append(f"asset {aid}: missing file: {rel}")
            continue
        kind = item.get("kind")
        approved = item.get("user_approved") is True and kind == "atlas"
        approved_atlases += 1 if approved else 0
        sprites = item.get("sprites")
        if sprites is None:
            errors.append(f"asset {aid}: sprites field required (1, or frame count for sprite_sheet)")
        elif not isinstance(sprites, int) or isinstance(sprites, bool) or sprites < 1:
            errors.append(f"asset {aid}: sprites must be a positive integer")
        elif sprites != 1 and kind != "sprite_sheet":
            if approved:
                warnings.append(f"asset {aid}: approved atlas with sprites={sprites}; keep per-sprite files too")
            else:
                errors.append(f"asset {aid}: sprites={sprites} violates one-asset-per-file "
                              "(must be 1; use kind=sprite_sheet with atlas metadata for animation sheets)")
        atlas_of = item.get("atlas_of")
        if isinstance(atlas_of, list) and atlas_of and not approved:
            errors.append(f"asset {aid}: atlas_of present without user_approved atlas declaration")
        if kind == "sprite_sheet" and isinstance(atlas_of, list) and atlas_of:
            warnings.append(f"asset {aid}: sprite_sheet describes frames via atlas/source_files; atlas_of is for approved icon packing")
        if (any(word in path.stem.lower().replace("-", "_") for word in ATLAS_WORDS)
                and not approved and kind != "sprite_sheet"):
            warnings.append(f"asset {aid}: filename suggests a packed sheet: {path.name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        declared = item.get("sha256")
        if isinstance(declared, str) and declared.strip():
            if len(declared) != 64 or any(c not in "0123456789abcdef" for c in declared.lower()):
                errors.append(f"asset {aid}: sha256 must be 64 hex chars")
            elif declared.lower() != digest:
                errors.append(f"asset {aid}: sha256 mismatch")
        else:
            warnings.append(f"asset {aid}: sha256 not recorded")
        actual = image_size(path)
        if actual is None and (item.get("width") is not None or item.get("height") is not None):
            warnings.append(f"asset {aid}: dimensions declared but image header unreadable")
        elif actual:
            if item.get("width") is not None and item["width"] != actual[0]:
                errors.append(f"asset {aid}: width mismatch: declared={item['width']} actual={actual[0]}")
            if item.get("height") is not None and item["height"] != actual[1]:
                errors.append(f"asset {aid}: height mismatch: declared={item['height']} actual={actual[1]}")
        if kind == "sprite_sheet" and isinstance(sprites, int) and not isinstance(sprites, bool) and sprites > 1:
            sprite_sheets += 1
            sprite_sheet(item, aid, root, actual, registered, errors)
    for item in entries_list:
        if not isinstance(item, dict) or item.get("kind") != "atlas":
            continue
        for ref in entries(item.get("atlas_of")):
            if ref not in ids:
                errors.append(f"asset {item.get('id')}: atlas_of refers to unknown asset: {ref}")
    unclassified = []
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            if path.resolve() in registered:
                continue
            if "_raw" in path.relative_to(root).parts:
                continue
            unclassified.append(path.relative_to(project).as_posix())
    if unclassified:
        warnings.append(f"{len(unclassified)} image file(s) under asset root not registered in manifest")
    stats.update(asset_entries=len(entries_list), asset_files_registered=len(registered),
                 asset_files_unclassified=len(unclassified), asset_approved_atlases=approved_atlases,
                 asset_sprite_sheets=sprite_sheets)
    details.update(unclassified_assets=unclassified,
                   asset_manifest=target.relative_to(project).as_posix() if target.is_relative_to(project) else str(target))


def main(mode):
    p = argparse.ArgumentParser(description=f"melavonmen {mode} validator")
    p.add_argument("--project", type=Path, default=Path("."), help="project root")
    if mode == "drift":
        p.add_argument("--base", default="HEAD", help="Git baseline revision")
    if mode == "assets":
        p.add_argument("--manifest", default=None, help="asset manifest path relative to --project")
    args = p.parse_args()
    project = args.project.resolve()
    errors, warnings, stats, details = [], [], {}, {}
    if mode == "index":
        index(project, errors, warnings, stats)
    elif mode == "schema":
        schema(project, errors, warnings, stats)
    elif mode == "symbols":
        symbols(project, errors, warnings, stats)
    elif mode == "assets":
        assets(project, errors, warnings, stats, details, args.manifest)
    elif mode == "drift":
        drift(project, args.base, errors, warnings, stats, details)
    sys.exit(emit(mode, errors, warnings, stats, details))
