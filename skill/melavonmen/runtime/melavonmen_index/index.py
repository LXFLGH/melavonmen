"""Persistent source inventory, incremental publication, and hybrid retrieval."""

from collections import Counter, defaultdict, deque
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import sqlite3
from threading import Lock
from time import monotonic

from . import parser
from .embeddings import Embeddings, pack, rerank, similarity
from .workspace import IndexErrorWithCode, git_text, operation_connection, project_stat


SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots(branch TEXT PRIMARY KEY, head TEXT, signature TEXT NOT NULL,
    indexed_at TEXT NOT NULL, mode TEXT NOT NULL, provider TEXT);
CREATE TABLE IF NOT EXISTS files(branch TEXT NOT NULL, path TEXT NOT NULL, digest TEXT NOT NULL,
    mtime INTEGER NOT NULL, size INTEGER NOT NULL, PRIMARY KEY(branch,path));
CREATE INDEX IF NOT EXISTS files_digest ON files(digest);
CREATE TABLE IF NOT EXISTS documents(digest TEXT PRIMARY KEY, text TEXT NOT NULL, language TEXT NOT NULL,
    symbols TEXT NOT NULL, calls TEXT NOT NULL, imports TEXT NOT NULL, warnings TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, digest TEXT NOT NULL, start INTEGER NOT NULL,
    end INTEGER NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL, body TEXT NOT NULL, vector_key TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS chunks_digest ON chunks(digest);
CREATE VIRTUAL TABLE IF NOT EXISTS terms USING fts5(body, name, tokenize='unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS vectors(provider TEXT NOT NULL, key TEXT NOT NULL, value BLOB NOT NULL,
    PRIMARY KEY(provider,key));
CREATE TABLE IF NOT EXISTS history_sources(repository TEXT PRIMARY KEY, principal TEXT NOT NULL,
    since_date TEXT, synced_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS history_generation(repository TEXT PRIMARY KEY, generation INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS history_entries(repository TEXT NOT NULL, number INTEGER NOT NULL, kind TEXT NOT NULL,
    state TEXT NOT NULL, author TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL, updated TEXT,
    passages TEXT NOT NULL, files TEXT NOT NULL, PRIMARY KEY(repository,number));
"""
FORMAT = 2
EXTRACTION_VERSION = "2026-11-12.5"
QUERY_WORD = re.compile(r"[^\W_]+", re.UNICODE)
CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
STOP = set("a an and at be by for from how in is it of on or the to was what when where which with".split())
CJK = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]+")


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def lexical(text):
    expanded = CAMEL.sub(" ", text)
    extra = " ".join(" ".join(word[i:i + 2] for i in range(len(word) - 1))
                     for word in CJK.findall(text))
    return f"{text}\n{expanded}\n{extra}"


def fts_query(query):
    terms = dict.fromkeys(word.casefold() for word in QUERY_WORD.findall(lexical(query)) if word.casefold() not in STOP)
    return " OR ".join(f'"{word}"' for word in list(terms)[:40])


def token_estimate(text):
    return len(re.findall(r"[A-Za-z0-9_]{1,4}|[^\sA-Za-z0-9_]", text))


def location(path, first, last=None):
    return f"{path}:{first}" if last is None or first == last else f"{path}:{first}-{last}"


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise IndexErrorWithCode("Operation cancelled", "CANCELLED")


class Index:
    def __init__(self, workspace):
        self.workspace = workspace
        self.root = workspace.root
        self.database = self.root / ".melavonmen" / "index.sqlite3"
        self.metrics = Counter()
        self.logs = deque(maxlen=250)
        self.refresh_lock = Lock()

    def log(self, category, message, level="info"):
        self.logs.append({"time": iso_now(), "category": category, "level": level, "message": message})

    def connect(self, write=False):
        if not write and not self.database.is_file():
            return None
        if self.database.is_symlink() or self.database.parent.is_symlink():
            raise IndexErrorWithCode("Index storage must be local to the workspace", "INDEX_INCOMPATIBLE")
        self.database.parent.mkdir(mode=0o700, exist_ok=True)
        if write and not self.database.exists():
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            try:
                os.close(os.open(self.database, flags, 0o600))
            except FileExistsError:
                pass
        conn = sqlite3.connect(self.database, timeout=30)
        try:
            conn.row_factory = sqlite3.Row
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, FORMAT):
                raise IndexErrorWithCode("Index storage format is not supported", "INDEX_INCOMPATIBLE")
            if write and version < FORMAT:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(SCHEMA)
                conn.execute(f"PRAGMA user_version={FORMAT}")
            return conn
        except BaseException:
            conn.close()
            raise

    def _load(self, settings, previous, cancel, thorough=False):
        inventory, decoded, observed = {}, {}, {}
        for name, path, lang in self.workspace.source_files(settings):
            check_cancel(cancel)
            try:
                stat = path.stat()
                observed[name] = (stat.st_mtime_ns, stat.st_size)
                if not thorough and name in previous and previous[name][1:] == (stat.st_mtime_ns, stat.st_size):
                    inventory[name] = previous[name]
                    continue
                raw = path.read_bytes()
                final = path.stat()
            except OSError:
                continue
            if (stat.st_mtime_ns, stat.st_size, stat.st_ino) != (final.st_mtime_ns, final.st_size, final.st_ino):
                raise IndexErrorWithCode(f"Source changed while reading {name}. Retry indexing.", "SOURCE_CHANGED")
            if b"\x00" in raw:
                continue
            try:
                source = raw.decode("utf-8-sig")
            except UnicodeError:
                continue
            digest = sha(f"{EXTRACTION_VERSION}\0{lang}\0".encode() + raw)
            inventory[name] = (digest, stat.st_mtime_ns, stat.st_size)
            decoded[digest] = (source, lang)
        return inventory, decoded, observed

    def verify_scan(self, settings, before, cancel):
        observed = {}
        for name, path, _ in self.workspace.source_files(settings):
            check_cancel(cancel)
            if metadata := project_stat(path):
                observed[name] = metadata
        if observed != before:
            raise IndexErrorWithCode("Source files changed while indexing. Retry.", "SOURCE_CHANGED")

    @staticmethod
    def mode(settings):
        mode = settings.get("indexing", {}).get("mode", "structural")
        if mode not in {"structural", "hybrid"}:
            raise IndexErrorWithCode("indexing.mode must be structural or hybrid")
        return mode

    @staticmethod
    def signature(settings, provider):
        scope = {key: settings.get(key) for key in ("include", "exclude", "additionalInclude", "includeIgnored", "knowledgeBases")}
        indexing = settings.get("indexing", {})
        scope["indexing"] = {key: indexing.get(key) for key in ("include", "exclude", "additionalInclude", "maxFileSize", "mode")}
        return sha(json.dumps([EXTRACTION_VERSION, scope, provider.identity if provider else None], sort_keys=True).encode())

    def status(self, check_freshness=False, cancel=None):
        settings = self.workspace.settings
        mode = self.mode(settings)
        provider = Embeddings(settings) if mode == "hybrid" else None
        branch, head = self.workspace.branch, self.workspace.head
        snapshot, files, blocks = None, {}, 0
        if conn := self.connect():
            with closing(conn):
                snapshot = conn.execute("SELECT * FROM snapshots WHERE branch=?", (branch,)).fetchone()
                files = self.inventory(conn, branch)
                blocks = conn.execute(
                    "SELECT count(*) FROM files JOIN chunks USING(digest) WHERE branch=?", (branch,)
                ).fetchone()[0]
        compatibility = bool(snapshot and snapshot["signature"] == self.signature(settings, provider))
        freshness = None
        if check_freshness:
            observed, _, _ = self._load(settings, {}, cancel, thorough=True)
            changed = sorted(p for p in observed.keys() | files.keys()
                             if observed.get(p, ("",))[0] != files.get(p, ("",))[0])
            freshness = {"current": compatibility and snapshot["head"] == head and not changed,
                         "changedFiles": changed, "headMatches": bool(snapshot and snapshot["head"] == head)}
        return {"projectRoot": str(self.root), "storage": str(self.database), "branch": branch, "head": head,
                "mode": mode, "provider": provider.kind if provider else None, "model": provider.model if provider else None,
                "ready": compatibility, "files": len(files), "chunks": blocks, "freshness": freshness,
                "indexedAt": snapshot["indexed_at"] if snapshot else None}

    @staticmethod
    def inventory(conn, branch):
        return {r["path"]: (r["digest"], r["mtime"], r["size"])
                for r in conn.execute("SELECT path,digest,mtime,size FROM files WHERE branch=?", (branch,))}

    def refresh(self, *, force=False, estimate=False, dry=False, verbose=False, progress=None, cancel=None, poll=False):
        with self.refresh_lock:
            return self._refresh(force, estimate, dry, verbose, progress, cancel, poll)

    def _refresh(self, force, estimate, dry, verbose, progress, cancel, poll):
        before = monotonic()
        settings = self.workspace.settings
        branch, head = self.workspace.branch, self.workspace.head
        mode = self.mode(settings)
        provider = Embeddings(settings) if mode == "hybrid" else None
        signature = self.signature(settings, provider)
        readonly = estimate or dry
        conn = self.connect(write=not readonly)
        previous = {}
        if progress:
            progress(0, 3, "Scanning source files")
        try:
            if conn is not None:
                with conn:
                    conn.execute("BEGIN")
                    current = conn.execute("SELECT * FROM snapshots WHERE branch=?", (branch,)).fetchone()
                    previous = self.inventory(conn, branch)
            else:
                current = None
            thorough = force or readonly or not poll or current is None or current["signature"] != signature
            inventory, decoded, observed_files = self._load(settings, previous, cancel, thorough=thorough)
            if poll and current and inventory == previous and current["head"] == head and current["signature"] == signature:
                return {"files": len(inventory), "unchanged": len(inventory), "mode": mode}
            if readonly:
                total = sum(token_estimate(decoded[digest][0]) for digest, _, _ in inventory.values())
                return {"files": len(inventory), "estimatedTokens": total, "mode": mode, "readOnly": True}
            if progress:
                progress(1, 3, "Extracting source and refreshing index")
            with operation_connection(conn):
                observed = conn.execute("SELECT * FROM snapshots WHERE branch=?", (branch,)).fetchone()
                if observed != current:
                    raise IndexErrorWithCode("Another process published a newer index. Retry indexing.", "INDEX_CHANGED")
                for digest, (source, language) in decoded.items():
                    check_cancel(cancel)
                    if conn.execute("SELECT 1 FROM documents WHERE digest=?", (digest,)).fetchone():
                        continue
                    symbols, calls, imports, warnings = parser.extract(source, language)
                    conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
                                 (digest, source, language, *(json.dumps(x, ensure_ascii=False) for x in (symbols, calls, imports, warnings))))
                    for start, end, kind, name, body in parser.chunks(source, symbols):
                        key = sha(body.encode())
                        rowid = conn.execute("INSERT INTO chunks(digest,start,end,kind,name,body,vector_key) VALUES (?,?,?,?,?,?,?)",
                                             (digest, start, end, kind, name, body, key)).lastrowid
                        conn.execute("INSERT INTO terms(rowid,body,name) VALUES (?,?,?)", (rowid, lexical(body), lexical(name)))
                conn.execute("DELETE FROM files WHERE branch=?", (branch,))
                conn.executemany("INSERT INTO files VALUES (?,?,?,?,?)",
                                 ((branch, path, *meta) for path, meta in inventory.items()))
                if provider:
                    self.build_vectors(conn, branch, provider, force, progress, cancel)
                self.verify_scan(settings, observed_files, cancel)
                check_cancel(cancel)
                if (self.workspace.branch, self.workspace.head) != (branch, head):
                    raise IndexErrorWithCode("Branch changed while indexing. Retry in the current checkout.", "SOURCE_CHANGED")
                conn.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?,?)",
                             (branch, head, signature, iso_now(), mode, provider.identity if provider else None))
            counts = conn.execute("SELECT count(*) FROM files JOIN chunks USING(digest) WHERE branch=?", (branch,)).fetchone()[0]
            skipped = sum(path in previous and previous[path][0] == meta[0] for path, meta in inventory.items())
            result = {"branch": branch, "mode": mode, "files": len(inventory), "chunks": counts,
                      "unchanged": skipped, "removed": len(previous.keys() - inventory.keys())}
            if verbose:
                result["warnings"] = [{"path": row["path"], "warnings": json.loads(row["warnings"])}
                                      for row in conn.execute("SELECT path,warnings FROM files JOIN documents USING(digest) WHERE branch=? AND warnings!='[]'", (branch,))]
            self.metrics["indexRuns"] += 1
            self.log("general", f"Indexed {len(inventory)} files on {branch} in {monotonic() - before:.3f}s")
            if progress:
                progress(3, 3, "Index published")
            return result
        finally:
            if conn is not None:
                conn.close()

    def build_vectors(self, conn, branch, provider, force, progress, cancel):
        rows = conn.execute("""
            SELECT DISTINCT vector_key, body FROM chunks JOIN files USING(digest)
            WHERE branch=? AND (? OR NOT EXISTS (SELECT 1 FROM vectors v WHERE v.provider=? AND v.key=chunks.vector_key))
        """, (branch, force, provider.identity)).fetchall()
        for i in range(0, len(rows), provider.batch_size):
            check_cancel(cancel)
            batch = rows[i:i + provider.batch_size]
            vectors = provider.embed([r["body"] for r in batch])
            conn.executemany("INSERT OR REPLACE INTO vectors VALUES (?,?,?)",
                             ((provider.identity, row["vector_key"], pack(vector)) for row, vector in zip(batch, vectors)))
            self.metrics["embeddedChunks"] += len(batch)
            if progress:
                progress(2 + min(0.9, (i + len(batch)) / max(len(rows), 1) * 0.9), 3, "Building vectors")

    def ready(self, cancel=None):
        settings = self.workspace.settings
        status = self.status()
        indexing = settings.get("indexing", {})
        if (status["ready"] and indexing.get("watchFiles", True)) or (
                not status["ready"] and indexing.get("autoIndex", False)):
            self.refresh(cancel=cancel, poll=True)
            status = self.status()
        if not status["ready"]:
            raise IndexErrorWithCode("Run index_codebase for this branch and configuration.", "INDEX_NOT_READY")
        return status["branch"], settings

    def search(self, query, options, cancel=None, similar=False):
        branch, settings = self.ready(cancel)
        provider = Embeddings(settings) if self.mode(settings) == "hybrid" else None
        if similar and not provider:
            raise IndexErrorWithCode("find_similar requires a configured hybrid index", "UNSUPPORTED_OPERATION")
        search_settings = settings.get("search", {})
        limit = min(options.get("limit", 5), search_settings.get("maxResults", 100))
        fetch_limit = max(limit, settings.get("reranker", {}).get("topN", 15)) if settings.get("reranker", {}).get("enabled") else limit
        with closing(self.connect()) as conn:
            conn.execute("BEGIN")
            rows = self._retrieve(conn, branch, provider, query, {**options, "limit": fetch_limit},
                                  search_settings, cancel, similar)
        check_cancel(cancel)
        if not similar:
            rows = rerank(query, rows, settings)
        rows = rows[:limit]
        self.metrics["queries"] += 1
        self.metrics["returnedChunks"] += len(rows)
        return rows

    def _retrieve(self, conn, branch, provider, query, options, search, cancel, similar):
        where, params = search_filters(branch, options)
        fields = """f.path, c.id, c.start AS lineStart, c.end AS lineEnd, c.kind, c.name, c.body AS text,
                    d.text AS source, d.language"""
        catalog = """chunks c JOIN files f ON c.digest=f.digest JOIN documents d ON f.digest=d.digest"""
        candidate_limit = min(1000, max(100, options.get("limit", 5) * 12))
        candidates = {}
        scores = defaultdict(float)
        weighted = search.get("fusionStrategy") == "weighted"
        semantic_weight = search.get("hybridWeight", 0.5) if weighted and provider else 1
        keyword_weight = 1 - semantic_weight if weighted and provider else 1
        rrf_k = max(1, search.get("rrfK", 30))
        terms = fts_query(query)
        if terms and not similar:
            ranked = conn.execute(f"""
                SELECT {fields} FROM {catalog} JOIN terms ON terms.rowid=c.id
                WHERE terms MATCH ? AND {where} ORDER BY bm25(terms, 1.0, 4.0), f.path, c.start LIMIT ?
            """, (terms, *params, candidate_limit))
            for rank, row in enumerate(ranked, 1):
                key = (row["path"], row["id"])
                candidates[key] = row
                scores[key] += keyword_weight * (rrf_k + 1) / (rrf_k + rank)
        if provider:
            qvector = provider.embed([query], purpose="query")[0]
            vector_scores = {}
            for row in conn.execute(f"""
                SELECT f.path, c.id, v.value FROM {catalog} JOIN vectors v ON c.vector_key=v.key
                WHERE v.provider=? AND {where}
            """, (provider.identity, *params)):
                check_cancel(cancel)
                vector_scores[(row["path"], row["id"])] = similarity(qvector, row["value"])
            ranked_keys = sorted(vector_scores, key=lambda key: (-vector_scores[key], key))[:candidate_limit]
            for rank, key in enumerate(ranked_keys, 1):
                if key not in candidates:
                    candidates[key] = conn.execute(f"SELECT {fields} FROM {catalog} WHERE f.branch=? AND f.path=? AND c.id=?",
                                                   (branch, *key)).fetchone()
                scores[key] += (max(0, vector_scores[key]) if similar else
                                semantic_weight * (rrf_k + 1) / (rrf_k + rank))
        hits = []
        for key in sorted(scores, key=lambda k: (-scores[k], k)):
            check_cancel(cancel)
            score = scores[key] / (2 if provider and not similar and not weighted else 1)
            if score < search.get("minScore", 0):
                continue
            hit = dict(candidates[key])
            source = hit.pop("source")
            hit.pop("id")
            if not self.blame_matches(hit, options):
                continue
            context = options.get("contextLines", 0)
            if context:
                lines = source.splitlines()
                hit["lineStart"] = max(1, hit["lineStart"] - context)
                hit["lineEnd"] = min(len(lines), hit["lineEnd"] + context)
                hit["text"] = "\n".join(lines[hit["lineStart"] - 1:hit["lineEnd"]])
            hit["score"] = round(score, 6)
            hits.append(hit)
            if len(hits) == options.get("limit", 5):
                break
        return hits

    def blame_matches(self, hit, options):
        names = ("blameAuthor", "blameSha", "blameSince", "blameUntil")
        if not any(options.get(name) for name in names):
            return True
        if hit["path"].startswith("/"):
            return False
        output = git_text(self.root, "blame", "--line-porcelain", "-L", f"{hit['lineStart']},{hit['lineEnd']}", "--", hit["path"])
        if output is None:
            return False
        commit, authors, date = "", [], ""
        for line in output.splitlines():
            if re.match(r"^[a-f0-9]{40,64} \d+ \d+", line):
                commit, authors, date = line.split()[0], [], ""
            elif line.startswith(("author ", "author-mail ")):
                authors.append(line.split(" ", 1)[1].casefold())
            elif line.startswith("author-time "):
                date = datetime.fromtimestamp(int(line.split()[1]), timezone.utc).date().isoformat()
            elif line.startswith("\t") and commit.strip("0"):
                if all((not options.get("blameAuthor") or any(options["blameAuthor"].casefold() in a for a in authors),
                        not options.get("blameSha") or commit.startswith(options["blameSha"]),
                        not options.get("blameSince") or date >= options["blameSince"][:10],
                        not options.get("blameUntil") or date <= options["blameUntil"][:10])):
                    return True
        return False

    def documents(self, branch):
        with closing(self.connect()) as conn:
            return [dict(row) for row in conn.execute("""
                SELECT path,text,language,symbols,calls,imports,warnings FROM files JOIN documents USING(digest)
                WHERE branch=? ORDER BY path
            """, (branch,))]


def search_filters(branch, options):
    where, params = ["f.branch=?"], [branch]
    directory = options.get("directory")
    if directory and directory != ".":
        prefix = directory.replace("\\", "/").rstrip("/") + "/"
        where.append("substr(f.path,1,?)=?")
        params.extend((len(prefix), prefix))
    if options.get("fileType"):
        suffix = "." + options["fileType"].lstrip(".").lower()
        where.append("lower(substr(f.path,-?))=?")
        params.extend((len(suffix), suffix))
    if options.get("chunkType"):
        kind = options["chunkType"].removesuffix("_definition")
        where.append("c.kind=?")
        params.append(kind)
    if options.get("excludeFile"):
        where.append("f.path!=?")
        params.append(options["excludeFile"])
    return " AND ".join(where), params
