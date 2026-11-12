"""Workspace-local, rebuildable code intelligence database.

No network calls. The database is separated from Doc/Wiki and deliberately
never mutates the source tree. A worktree gets a different database by default.
"""
from __future__ import annotations

from collections import deque
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time

from native_parsers import PARSER_VERSION, language_for, parse_file

SCHEMA_VERSION = "2"
EXCLUDED = {
    ".git", ".melavonmen", ".godot", "node_modules", "vendor", "third_party",
    "dist", "build", "out", "target", ".venv", "venv", "__pycache__",
    ".cache", ".next", ".idea", ".vscode", "coverage", "wiki", "doc",
}
SKIP_EXT = {".lock", ".map", ".min.js"}
MAX_SOURCE = 2 * 1024 * 1024
MAX_RESULTS = 200
MAX_CONTEXT_LINES = 120
SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS files(
 path TEXT PRIMARY KEY, language TEXT NOT NULL, sha256 TEXT NOT NULL,
 revision TEXT NOT NULL, depth TEXT NOT NULL, parser_version TEXT NOT NULL,
 bytes INTEGER NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS symbols(
 id INTEGER PRIMARY KEY, path TEXT NOT NULL, name TEXT NOT NULL,
 qualified_name TEXT NOT NULL, kind TEXT NOT NULL, signature TEXT NOT NULL,
 line_start INTEGER NOT NULL, line_end INTEGER NOT NULL,
 source_sha256 TEXT NOT NULL, revision TEXT NOT NULL,
 extraction_method TEXT NOT NULL, verification_status TEXT NOT NULL,
 extra TEXT NOT NULL, FOREIGN KEY(path) REFERENCES files(path));
CREATE INDEX IF NOT EXISTS ix_sym_name ON symbols(name);
CREATE INDEX IF NOT EXISTS ix_sym_qual ON symbols(qualified_name);
CREATE INDEX IF NOT EXISTS ix_sym_path ON symbols(path);
CREATE TABLE IF NOT EXISTS edges(
 id INTEGER PRIMARY KEY, path TEXT NOT NULL, line_start INTEGER NOT NULL,
 line_end INTEGER NOT NULL, kind TEXT NOT NULL, target_name TEXT NOT NULL,
 target_file TEXT, target_symbol TEXT, source_sha256 TEXT NOT NULL,
 revision TEXT NOT NULL, extraction_method TEXT NOT NULL,
 verification_status TEXT NOT NULL, extra TEXT NOT NULL,
 FOREIGN KEY(path) REFERENCES files(path));
CREATE INDEX IF NOT EXISTS ix_edge_path ON edges(path);
CREATE INDEX IF NOT EXISTS ix_edge_target ON edges(target_file);
CREATE INDEX IF NOT EXISTS ix_edge_name ON edges(target_name);
CREATE VIRTUAL TABLE IF NOT EXISTS code_fts USING fts5(
 path UNINDEXED, line UNINDEXED, text, tokenize='unicode61');
"""

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def inside(root, relative):
    """Reject absolute paths, parent traversal, symlink escapes and NUL."""
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        raise ValueError("invalid relative path")
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("path outside workspace: " + relative[:100])
    result = (root / rel).resolve()
    if not result.is_relative_to(root):
        raise ValueError("path outside workspace: " + relative[:100])
    return result

def git(root, args, input_bytes=None):
    try:
        proc = subprocess.run(["git", "-C", str(root), *args],
                              input=input_bytes, capture_output=True, check=True,
                              timeout=30)
        return proc.stdout
    except (OSError, subprocess.SubprocessError):
        return b""

def head(root):
    return git(root, ["rev-parse", "HEAD"]).decode("ascii", "replace").strip() or "no-git"

def config(root):
    f = root / ".melavonmen.json"
    if not f.is_file():
        return {"include": ["**/*"], "exclude": [], "max_source_bytes": MAX_SOURCE}
    raw = json.loads(f.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(".melavonmen.json must be an object")
    return {"include": raw.get("include", ["**/*"]),
            "exclude": raw.get("exclude", []),
            "max_source_bytes": int(raw.get("max_source_bytes", MAX_SOURCE))}

def eligible(rel, conf):
    parts = Path(rel).parts
    if any(part in EXCLUDED for part in parts[:-1]):
        return False
    if rel in {".melavonmen.json"} or rel.endswith(".min.js") or Path(rel).suffix.lower() in SKIP_EXT:
        return False
    if "assets" in parts[:-1] and language_for(rel) not in {
            "gdscript", "godot_resource", "godot_project"}:
        return False
    if not language_for(rel):
        return False
    patterns = conf["include"]
    if patterns and not any(fnmatch.fnmatch(rel, p) or p == "**/*" for p in patterns):
        return False
    if any(fnmatch.fnmatch(rel, p) for p in conf["exclude"]):
        return False
    return True

def git_candidates(root, conf):
    raw = git(root, ["ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    paths = {os.fsdecode(x) for x in raw.split(b"\x00") if x}
    return {p for p in paths if eligible(p, conf) and
            (root / p).is_file() and not (root / p).is_symlink()}

def physical_scan(root, conf):
    """Independent filesystem enumeration; not derived from the index manifest."""
    result = set()
    for current, dirs, files in os.walk(root, followlinks=False):
        rel_dir = Path(current).relative_to(root)
        dirs[:] = [d for d in dirs if d not in EXCLUDED and
                   not (Path(current) / d).is_symlink() and
                   not (Path(current) / d / ".git").exists()]
        for name in files:
            path = Path(current) / name
            if path.is_symlink():
                continue
            rel = (rel_dir / name).as_posix()
            if eligible(rel, conf):
                result.add(rel)
    # Exclude Git-ignored paths from the independent scan while preserving
    # tracked files that happen to match a newly added ignore pattern.
    tracked = set(os.fsdecode(x) for x in
                  git(root, ["ls-files", "-z", "--cached"]).split(b"\x00") if x)
    if result and (root / ".git").exists():
        raw = b"\x00".join(os.fsencode(p) for p in sorted(result)) + b"\x00"
        ignored = set(os.fsdecode(x) for x in
                      git(root, ["check-ignore", "--stdin", "-z"], raw).split(b"\x00") if x)
        result -= (ignored - tracked)
    return result

def discover(root, conf):
    candidates = git_candidates(root, conf)
    # In a non-Git folder, or with Git failures, still index eligible physical files.
    physical = physical_scan(root, conf)
    return (candidates | physical), physical

def connect(root, dbpath=None, readonly=False):
    root = Path(root).resolve()
    if dbpath:
        path = inside(root, dbpath)
    else:
        path = inside(root, ".melavonmen/index.sqlite")
    if not readonly:
        path.parent.mkdir(parents=True, exist_ok=True)
    if readonly and not path.is_file():
        raise FileNotFoundError("index absent; run build first")
    db = sqlite3.connect(path.as_uri() + "?mode=ro" if readonly else str(path),
                         uri=readonly, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    if not readonly:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        version = db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
        if version and version["value"] != SCHEMA_VERSION:
            db.close()
            raise ValueError("index schema mismatch: use rebuild/doctor")
        db.execute("INSERT OR REPLACE INTO metadata VALUES('schema',?)", (SCHEMA_VERSION,))
        db.commit()
    else:
        version = db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
        if not version or version["value"] != SCHEMA_VERSION:
            db.close()
            raise ValueError("index schema mismatch: use rebuild/doctor")
    return db

def _rows(db, table, sql="", args=()):
    return [dict(row) for row in db.execute("SELECT * FROM " + table + " " + sql, args)]

def _erase(db, path):
    for table in ("symbols", "edges", "files", "code_fts"):
        db.execute("DELETE FROM " + table + " WHERE path=?", (path,))

def _insert(db, root, relative, revision, maximum):
    file = inside(root, relative)
    raw = file.read_bytes()
    digest = sha256(raw)
    lang = language_for(relative)
    _erase(db, relative)
    data = {"symbols": [], "edges": [], "depth": "indexed", "warnings": []}
    if len(raw) <= maximum:
        data = parse_file(file, relative, lang, digest, revision)
    else:
        data["warnings"].append("over configured parser size limit")
    db.execute("INSERT INTO files VALUES(?,?,?,?,?,?,?,?)",
               (relative, lang, digest, revision, data["depth"],
                PARSER_VERSION, len(raw), time.time()))
    for sym in data["symbols"]:
        extras = {k: v for k, v in sym.items() if k in {"parameters", "return_type", "module"}}
        db.execute("""INSERT INTO symbols
         (path,name,qualified_name,kind,signature,line_start,line_end,
          source_sha256,revision,extraction_method,verification_status,extra)
         VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
         (relative, sym["name"], sym["qualified_name"], sym["kind"], sym["signature"],
          sym["line_start"], sym["line_end"], digest, revision,
          sym["extraction_method"], sym["verification_status"],
          json.dumps(extras, ensure_ascii=False)))
    for edge in data["edges"]:
        extras = {k: v for k, v in edge.items() if k not in {
            "source_path", "line_start", "line_end", "source_sha256",
            "revision", "extraction_method", "verification_status",
            "kind", "target_name", "target_file", "target_symbol"}}
        db.execute("""INSERT INTO edges
         (path,line_start,line_end,kind,target_name,target_file,target_symbol,
          source_sha256,revision,extraction_method,verification_status,extra)
         VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
         (relative, edge["line_start"], edge["line_end"], edge["kind"],
          edge["target_name"], edge.get("target_file"), edge.get("target_symbol"),
          digest, revision, edge["extraction_method"], edge["verification_status"],
          json.dumps(extras, ensure_ascii=False)))
    if len(raw) <= maximum:
        for i, line in enumerate(raw.decode("utf-8", "replace").splitlines(), 1):
            db.execute("INSERT INTO code_fts(path,line,text) VALUES(?,?,?)",
                       (relative, i, line[:2048]))
    return digest, data

def _resolve_edges(db, current_files):
    """Only bind unique candidates; never promote a possible call to verified."""
    known = set(current_files)
    symbol_map = {}
    for row in db.execute("SELECT path,name,qualified_name FROM symbols"):
        for key in (row["name"], row["qualified_name"]):
            symbol_map.setdefault(key, set()).add(row["path"])
    for edge in db.execute("SELECT id,path,kind,target_name,target_file,verification_status FROM edges"):
        target = edge["target_name"]
        file = edge["target_file"]
        if file and file not in known:
            file = None
        if not file and target.startswith("res://"):
            candidate = target[6:]
            if candidate in known:
                file = candidate
        if not file and edge["kind"] in ("calls", "inherits", "reads", "writes", "references"):
            candidates = symbol_map.get(target) or symbol_map.get(target.split(".")[-1], set())
            if len(candidates) == 1:
                file = next(iter(candidates))
        if not file and edge["kind"] == "imports":
            mod = target.replace(".", "/").strip("'\"<>")
            options = [p for p in known if
                       p in (mod + ".py", mod + ".ts", mod + ".js", mod + "/__init__.py")]
            if len(options) == 1:
                file = options[0]
        if file != edge["target_file"]:
            db.execute("UPDATE edges SET target_file=? WHERE id=?", (file, edge["id"]))

def update(root, dbpath=None, full=False, check=False):
    root = Path(root).resolve()
    conf = config(root)
    discovered, physical = discover(root, conf)
    db = connect(root, dbpath, readonly=check)
    old = {r["path"]: r for r in db.execute("SELECT * FROM files")}
    current_sha = {}
    warnings = []
    for rel in sorted(discovered):
        try:
            current_sha[rel] = sha256(inside(root, rel).read_bytes())
        except (OSError, ValueError) as exc:
            warnings.append(rel + ": " + str(exc))
    deleted = sorted(set(old) - set(current_sha))
    changed = sorted(p for p, digest in current_sha.items() if full or
                     p not in old or old[p]["sha256"] != digest or
                     old[p]["parser_version"] != PARSER_VERSION)
    old_hashes = {old[p]["sha256"]: p for p in deleted}
    renames = [{"from": old_hashes[current_sha[p]], "to": p} for p in changed
               if current_sha[p] in old_hashes]
    if not check:
        revision = head(root)
        try:
            db.execute("BEGIN IMMEDIATE")
            for p in deleted:
                _erase(db, p)
            for p in changed:
                try:
                    _, result = _insert(db, root, p, revision, conf["max_source_bytes"])
                    warnings.extend(p + ": " + w for w in result["warnings"])
                except (OSError, UnicodeError, ValueError, sqlite3.Error) as exc:
                    raise RuntimeError("failed indexing " + p + ": " + str(exc)) from exc
            _resolve_edges(db, current_sha)
            db.execute("INSERT OR REPLACE INTO metadata VALUES('head',?)", (revision,))
            db.execute("INSERT OR REPLACE INTO metadata VALUES('root',?)", (str(root),))
            db.execute("INSERT OR REPLACE INTO metadata VALUES('parser',?)", (PARSER_VERSION,))
            db.commit()
        except Exception:
            db.rollback()
            raise
    result = audit(root, db, discovered, physical, current_sha)
    result.update({"mode": "check" if check else ("full" if full else "incremental"),
                   "changed": changed, "deleted": deleted, "renamed": renames,
                   "warnings": sorted(set(result["warnings"] + warnings))})
    if check and (changed or deleted):
        result["ok"] = False
    db.close()
    return result

def audit(root, db=None, discovered=None, physical=None, hashes=None):
    root = Path(root).resolve()
    own = db is None
    if own:
        db = connect(root, readonly=True)
    conf = config(root)
    if discovered is None:
        discovered, physical = discover(root, conf)
    if hashes is None:
        hashes = {}
        for p in discovered:
            try:
                hashes[p] = sha256(inside(root, p).read_bytes())
            except (ValueError, OSError):
                continue
    files = {r["path"]: r for r in db.execute("SELECT * FROM files")}
    missing = sorted(discovered - set(files))
    orphan = sorted(set(files) - discovered)
    stale = sorted(p for p in discovered & set(files)
                   if hashes.get(p) != files[p]["sha256"])
    rows = db.execute("""SELECT COUNT(*) AS count,
       SUM(CASE WHEN verification_status='verified' THEN 1 ELSE 0 END) AS verified
       FROM symbols""").fetchone()
    unknown = db.execute("""SELECT COUNT(*) FROM edges
      WHERE target_file IS NULL AND kind NOT IN ('reads','writes')""").fetchone()[0]
    summary = {"first_party_sources": len(physical),
               "discovered_sources": len(discovered), "indexed_sources": len(files),
               "deep_parsed_sources": sum(r["depth"] == "deep" for r in files.values()),
               "resource_parsed_sources": sum(r["depth"] == "resource" for r in files.values()),
               "verified_symbols": rows["verified"] or 0,
               "unverified_symbols": rows["count"] - (rows["verified"] or 0),
               "stale_sources": len(stale), "missing_sources": len(missing),
               "orphan_sources": len(orphan), "unresolved_edges": unknown}
    if own:
        db.close()
    return {"ok": not (missing or orphan or stale),
            "stats": summary, "missing": missing, "orphan": orphan, "stale": stale,
            "warnings": ["independent physical scan differs from git source set"]
             if physical != discovered else []}

def doctor(root):
    root = Path(root).resolve()
    try:
        db = connect(root, readonly=True)
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        result = audit(root, db)
        result["integrity"] = integrity
        result["ok"] = result["ok"] and integrity == "ok"
        db.close()
        return result
    except (OSError, sqlite3.Error, ValueError) as exc:
        return {"ok": False, "integrity": "unknown", "errors": [str(exc)],
                "recovery": "Back up existing .melavonmen directory; run rebuild with explicit permission"}

def rebuild(root, dbpath=None):
    root = Path(root).resolve()
    rel = dbpath or ".melavonmen/index.sqlite"
    target = inside(root, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Build into a sibling and preserve the old DB until its replacement is valid.
    stage = target.with_name(target.name + ".stage-" + str(os.getpid()))
    stage_rel = stage.relative_to(root).as_posix()
    try:
        report = update(root, stage_rel, full=True)
        if not report["ok"]:
            raise RuntimeError("staging index failed audit")
        staged = sqlite3.connect(str(stage))
        valid = staged.execute("PRAGMA integrity_check").fetchone()[0]
        staged.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        staged.close()
        if valid != "ok":
            raise RuntimeError("staging integrity failed")
        # Readers of the old WAL might be active; preserve a backup, never unlink
        # an existing user DB as a side effect of a failed rebuild.
        if target.exists():
            import shutil
            backup = target.with_name(target.name + ".backup-" + str(int(time.time())))
            shutil.copy2(target, backup)
            report["backup"] = str(backup.relative_to(root))
        os.replace(stage, target)
        report["rebuilt"] = True
        return report
    finally:
        if stage.exists():
            stage.unlink()

def _safe_rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]

def _filter_sql(language=None, directory=None, column="path"):
    where, args = [], []
    if directory:
        if directory.startswith("/") or ".." in Path(directory).parts:
            raise ValueError("invalid directory")
        where.append(column + " LIKE ?")
        args.append(directory.rstrip("/") + "/%")
    if language:
        where.append(column + " IN (SELECT path FROM files WHERE language=?)")
        args.append(language)
    return where, args

def query(root, phrase, mode="auto", limit=20, offset=0, language=None,
          directory=None, token_budget=1500, dbpath=None):
    root = Path(root).resolve()
    db = connect(root, dbpath, readonly=True)
    limit = max(1, min(int(limit), MAX_RESULTS))
    offset = max(0, int(offset))
    budget = max(100, min(int(token_budget), 20000))
    phrase = phrase.strip()[:400]
    if not phrase:
        raise ValueError("query cannot be empty")
    filters, params = _filter_sql(language, directory)
    results = []
    def append(rows, category, score, labels):
        for r in rows:
            if "line_start" not in r:
                r["line_start"] = 1
            if "line_end" not in r:
                r["line_end"] = r["line_start"]
            path = r["path"]
            if (directory and not path.startswith(directory.rstrip("/") + "/")) or (
                language and db.execute("SELECT language FROM files WHERE path=?", (path,)).fetchone()["language"] != language):
                continue
            try:
                actual = sha256(inside(root, path).read_bytes())
            except (ValueError, OSError):
                continue
            stored = db.execute("SELECT sha256 FROM files WHERE path=?", (path,)).fetchone()
            if not stored or stored["sha256"] != actual:
                continue
            results.append({"path": path, "line_start": r["line_start"],
                            "line_end": r["line_end"],
                            "symbol": r.get("qualified_name"),
                            "kind": r.get("kind", category),
                            "score": score,
                            "evidence": labels, "verification_status":
                            r.get("verification_status", "verified"),
                            "extraction_method": r.get("extraction_method", "file_index"),
                            "source_sha256": actual,
                            "revision": r.get("revision")})
    if mode in ("auto", "symbol", "definition"):
        rows = _safe_rows(db, """SELECT path,line_start,line_end,qualified_name,
                 kind,verification_status,extraction_method,revision FROM symbols
                 WHERE name=? OR qualified_name=? ORDER BY path,line_start LIMIT 400""",
                 (phrase, phrase))
        append(rows, "symbol", 1.0, ["symbol_exact"])
        if mode != "definition":
            rows = _safe_rows(db, """SELECT path,line_start,line_end,qualified_name,
                  kind,verification_status,extraction_method,revision FROM symbols
                  WHERE name LIKE ? OR qualified_name LIKE ?
                  ORDER BY path,line_start LIMIT 400""",
                  ("%" + phrase + "%", "%" + phrase + "%"))
            append(rows, "symbol", .85, ["symbol_partial"])
    if mode in ("auto", "path", "file"):
        rows = _safe_rows(db, "SELECT path,revision FROM files WHERE path LIKE ? ORDER BY path LIMIT 400",
                          ("%" + phrase + "%",))
        append(rows, "file", .75, ["path_match"])
    if mode in ("auto", "text", "natural"):
        terms = re.findall(r"\w+", phrase, re.UNICODE)[:8]
        if terms:
            match = " OR ".join('"' + x.replace('"', "") + '"' for x in terms)
            try:
                rows = _safe_rows(db, """SELECT path,CAST(line AS INTEGER) line_start,
                     CAST(line AS INTEGER) line_end,text FROM code_fts
                     WHERE code_fts MATCH ? ORDER BY bm25(code_fts) LIMIT 500""", (match,))
                append(rows, "text", .55, ["fts_match"])
            except sqlite3.OperationalError:
                pass
        if not results:
            rows = _safe_rows(db, """SELECT path,CAST(line AS INTEGER) line_start,
                 CAST(line AS INTEGER) line_end FROM code_fts
                 WHERE text LIKE ? LIMIT 300""", ("%" + phrase + "%",))
            append(rows, "text", .50, ["substring_match"])
    if mode in ("auto", "contract", "natural"):
        for section in ("doc", "wiki"):
            directory_path = root / section
            if not directory_path.is_dir():
                continue
            terms = re.findall(r"\w+", phrase.lower())[:6]
            for p in directory_path.rglob("*.json"):
                if len(results) > 800:
                    break
                if p.is_symlink() or not p.resolve().is_relative_to(root):
                    continue
                rel = p.relative_to(root).as_posix()
                try:
                    lines = p.read_text("utf-8").splitlines()
                except (OSError, UnicodeError):
                    continue
                for i, line in enumerate(lines, 1):
                    if terms and any(t in line.lower() for t in terms):
                        results.append({"path": rel, "line_start": i, "line_end": i,
                                        "symbol": None, "kind": "contract",
                                        "score": .65, "evidence": ["doc_wiki_match"],
                                        "verification_status": "unverified"})
                        break
    unique = {}
    for row in results:
        key = (row["path"], row["line_start"], row.get("symbol"))
        if key not in unique or unique[key]["score"] < row["score"]:
            unique[key] = row
    ranked = sorted(unique.values(), key=lambda r: (-r["score"], r["path"], r["line_start"]))
    chosen, tokens = [], 0
    for r in ranked[offset:offset + limit]:
        estimate = max(20, len(json.dumps(r, ensure_ascii=False)) // 3)
        if tokens + estimate > budget:
            break
        chosen.append(r)
        tokens += estimate
    db.close()
    return {"query": phrase, "mode": mode, "results": chosen,
            "next_offset": offset + len(chosen) if offset + len(chosen) < len(ranked) else None,
            "truncated": offset + len(chosen) < len(ranked),
            "total_matches": len(ranked), "token_budget": budget, "warnings": []}

def references(root, symbol, limit=100, dbpath=None):
    db = connect(Path(root).resolve(), dbpath, readonly=True)
    sql = """SELECT * FROM edges WHERE target_name=? OR target_name LIKE ?
             OR target_symbol=? ORDER BY path,line_start LIMIT ?"""
    rows = _safe_rows(db, sql, (symbol, "%." + symbol, symbol, min(int(limit), 200)))
    db.close()
    return {"symbol": symbol, "results": rows,
            "warnings": ["These are statically known edges; dynamic uses may be missing"]}

def graph(root, name, reverse=False, depth=2, limit=200, kinds=None, dbpath=None):
    db = connect(Path(root).resolve(), dbpath, readonly=True)
    depth = max(0, min(int(depth), 8))
    limit = min(max(1, int(limit)), 1000)
    allfiles = {r["path"] for r in db.execute("SELECT path FROM files")}
    start = {name} if name in allfiles else {
        r["path"] for r in db.execute(
            "SELECT path FROM symbols WHERE name=? OR qualified_name=?", (name, name))}
    edges, seen, pending = [], set(start), deque((x, 0) for x in start)
    while pending and len(edges) < limit:
        current, layer = pending.popleft()
        if layer >= depth:
            continue
        col = "target_file" if reverse else "path"
        for edge in db.execute("SELECT * FROM edges WHERE " + col + "=?", (current,)):
            if kinds and edge["kind"] not in kinds:
                continue
            e = dict(edge)
            nxt = e["path"] if reverse else e["target_file"]
            edges.append(e)
            if nxt and nxt not in seen:
                seen.add(nxt)
                pending.append((nxt, layer + 1))
            if len(edges) >= limit:
                break
    db.close()
    return {"root": name, "reverse": reverse, "depth": depth,
            "visited_files": sorted(seen), "edges": edges,
            "truncated": bool(pending) or len(edges) >= limit,
            "warnings": [] if start else ["symbol or file was not indexed"]}

def impact(root, changed, depth=3, dbpath=None):
    db = connect(Path(root).resolve(), dbpath, readonly=True)
    known = {r["path"] for r in db.execute("SELECT path FROM files")}
    direct = []
    for name in changed:
        if name in known:
            direct.append(name)
        else:
            direct += [r["path"] for r in db.execute(
                "SELECT DISTINCT path FROM symbols WHERE name=? OR qualified_name=?",
                (name, name))]
    db.close()
    affected = set(direct)
    for p in direct:
        affected.update(graph(root, p, reverse=True, depth=depth,
                              dbpath=dbpath)["visited_files"])
    docs = sync_status(root, sorted(affected), dbpath=dbpath)
    return {"changed": changed, "affected_files": sorted(affected),
            "doc_wiki_candidates": docs["candidates"],
            "warnings": ["Impact is conservative; runtime/reflection edges are not exhaustive"]}

def context(root, path, line=1, before=6, after=12, dbpath=None):
    root = Path(root).resolve()
    target = inside(root, path)
    db = connect(root, dbpath, readonly=True)
    record = db.execute("SELECT sha256 FROM files WHERE path=?", (path,)).fetchone()
    db.close()
    if not record or not target.is_file() or sha256(target.read_bytes()) != record["sha256"]:
        return {"ok": False, "error": "unindexed or stale source: run update"}
    lines = target.read_text("utf-8", errors="replace").splitlines()
    line = max(1, min(int(line), max(1, len(lines))))
    before, after = max(0, int(before)), max(0, int(after))
    start = max(1, line - before)
    end = min(len(lines), line + after, start + MAX_CONTEXT_LINES - 1)
    return {"ok": True, "path": path, "source_sha256": record["sha256"],
            "line_start": start, "line_end": end,
            "lines": [{"line": i, "text": lines[i-1][:2048]}
                      for i in range(start, end+1)]}

def cycles(root, kinds=None, dbpath=None, max_cycles=100):
    """Tarjan SCC: only indexed, statically linked file edges."""
    db = connect(Path(root).resolve(), dbpath, readonly=True)
    accepted = set(kinds or ["imports", "depends_on", "resource_reference"])
    adjacency = {r["path"]: set() for r in db.execute("SELECT path FROM files")}
    for e in db.execute("SELECT path,target_file,kind FROM edges WHERE target_file IS NOT NULL"):
        if e["kind"] in accepted and e["target_file"] in adjacency:
            adjacency[e["path"]].add(e["target_file"])
    index = 0
    stack, active, numbers, low, found = [], set(), {}, {}, []
    def visit(v):
        nonlocal index
        numbers[v] = low[v] = index
        index += 1
        stack.append(v)
        active.add(v)
        for w in sorted(adjacency[v]):
            if w not in numbers:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in active:
                low[v] = min(low[v], numbers[w])
        if low[v] == numbers[v]:
            component = []
            while True:
                w = stack.pop()
                active.remove(w)
                component.append(w)
                if w == v:
                    break
            if len(component) > 1 or (component and component[0] in adjacency[component[0]]):
                found.append(sorted(component))
    try:
        for v in sorted(adjacency):
            if v not in numbers:
                visit(v)
    except RecursionError:
        db.close()
        return {"cycles": found, "warnings": ["graph recursion limit; partial cycle report"]}
    db.close()
    return {"cycles": found[:max_cycles], "truncated": len(found) > max_cycles,
            "kinds": sorted(accepted), "warnings": []}

def unresolved(root, limit=100, dbpath=None):
    """Known unresolved edges; a dynamic call is never silently 'resolved'."""
    db = connect(Path(root).resolve(), dbpath, readonly=True)
    rows = _safe_rows(db, """SELECT * FROM edges WHERE target_file IS NULL
               AND kind NOT IN ('reads','writes') ORDER BY path,line_start LIMIT ?""",
               (max(1, min(int(limit), 500)),))
    db.close()
    return {"count": len(rows), "edges": rows,
            "warning": "Unresolved may include built-ins/external libraries and dynamic dispatch"}

def sync_status(root, changed=None, dbpath=None):
    """Source-provenance checks plus a minimal plan; never promotes Doc states."""
    root = Path(root).resolve()
    changed = changed or []
    candidates, missing_refs, stale_wiki, unverified = [], [], [], []
    symbol_db = None
    try:
        symbol_db = connect(root, dbpath, readonly=True)
    except (OSError, sqlite3.Error, ValueError):
        pass
    for section in ("doc", "wiki"):
        folder = root / section
        if not folder.is_dir():
            continue
        for p in folder.rglob("*.json"):
            if p.is_symlink() or not p.resolve().is_relative_to(root):
                continue
            try:
                content = p.read_text("utf-8")
                obj = json.loads(content)
            except (OSError, UnicodeError, ValueError):
                unverified.append({"page": p.relative_to(root).as_posix(),
                                   "reason": "unreadable or invalid JSON"})
                continue
            rel = p.relative_to(root).as_posix()
            if any(name in content for name in changed):
                candidates.append(rel)
            if not isinstance(obj, dict):
                continue
            entries = list(obj.get("sources", [])) if isinstance(obj.get("sources"), list) else []
            if isinstance(obj.get("source_path"), str):
                entries.append({"path": obj["source_path"],
                                "sha256": obj.get("source_sha256")})
            if section == "doc":
                # Only cross-check known first-party source paths, not doc-relative routes.
                for key in ("source_paths", "affected_source_paths"):
                    value = obj.get(key, [])
                    if isinstance(value, list):
                        entries.extend({"path": x} for x in value if isinstance(x, str))
            for source in entries:
                if not isinstance(source, dict):
                    continue
                source_path = source.get("path")
                if not isinstance(source_path, str):
                    continue
                try:
                    code = inside(root, source_path)
                except ValueError:
                    missing_refs.append({"page": rel, "source": source_path, "reason": "unsafe_path"})
                    continue
                if not code.is_file():
                    missing_refs.append({"page": rel, "source": source_path, "reason": "deleted"})
                    continue
                declared_hash = source.get("sha256")
                if declared_hash and declared_hash != hashlib.sha256(code.read_bytes()).hexdigest():
                    stale_wiki.append({"page": rel, "source": source_path,
                                       "kind": "source_sha256"})
            if section == "wiki" and symbol_db and obj.get("source_path"):
                source_path = obj["source_path"]
                for decl in obj.get("declarations", []):
                    if not isinstance(decl, dict) or not isinstance(decl.get("qualified_name"), str):
                        continue
                    row = symbol_db.execute(
                        "SELECT signature,line_start,verification_status FROM symbols "
                        "WHERE path=? AND qualified_name=? LIMIT 1",
                        (source_path, decl["qualified_name"])).fetchone()
                    if not row:
                        unverified.append({"page": rel, "symbol": decl["qualified_name"],
                                           "reason": "missing_from_native_index"})
                    elif row["verification_status"] == "verified":
                        if (decl.get("signature") != row["signature"] or
                                (decl.get("line_start") is not None and
                                 decl["line_start"] != row["line_start"])):
                            stale_wiki.append({"page": rel,
                                               "symbol": decl["qualified_name"],
                                               "kind": "signature_or_location"})
                    else:
                        unverified.append({"page": rel, "symbol": decl["qualified_name"],
                                           "reason": "parser_cannot_certify_semantics"})
    if symbol_db:
        symbol_db.close()
    tasks = [{"page": path, "action": "review_contract_if_affected"
              if path.startswith("doc/") else "review_current_wiki_facts"}
             for path in sorted(set(candidates))]
    tasks += [{"page": x["page"], "action": "repair_missing_source_reference",
               "source": x["source"]} for x in missing_refs]
    tasks += [{"page": x["page"], "action": "verify_and_update_source_evidence",
               "source_or_symbol": x.get("source", x.get("symbol"))} for x in stale_wiki]
    return {"changed_sources": changed, "candidates": sorted(set(candidates)),
            "missing_source_references": missing_refs, "stale_wiki": stale_wiki,
            "unverified": unverified, "tasks": tasks,
            "state": "review_required" if tasks else "no_known_change",
            "note": "Business semantics and Doc contract state require human/agent review"}
