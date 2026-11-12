"""Optional semantic retrieval cache; never needed by deterministic search.

Local provider: sentence-transformers, model downloaded per its own configuration.
Remote provider: OpenAI-compatible HTTPS /embeddings endpoint, opt-in only.
No remote source upload occurs without allow_upload=True.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sqlite3
import urllib.request
from urllib.parse import urlparse
import os

from native_engine import connect, inside, query

CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS vectors(
 path TEXT NOT NULL, qualified_name TEXT NOT NULL, line_start INTEGER NOT NULL,
 source_sha256 TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 provider TEXT NOT NULL, model TEXT NOT NULL, embedding TEXT NOT NULL,
 PRIMARY KEY(path,qualified_name,provider,model));
CREATE INDEX IF NOT EXISTS ix_vector_source ON vectors(path,source_sha256);
"""

def client(provider="local", model="all-MiniLM-L6-v2", endpoint=None,
           allow_upload=False, token_env="EMBEDDING_API_KEY"):
    if provider == "local":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("local vectors require pip install sentence-transformers") from exc
        encoder = SentenceTransformer(model)
        def embed(texts):
            return [vector.tolist() for vector in encoder.encode(texts)]
        return embed
    if provider != "remote":
        raise ValueError("provider must be local or remote")
    if not allow_upload:
        raise PermissionError("remote code embedding requires explicit --allow-upload")
    if not endpoint:
        raise ValueError("remote embedding endpoint is required")
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise ValueError("remote endpoint must use HTTPS (or local loopback HTTP)")
    token = os.environ.get(token_env)
    def embed(texts):
        data = json.dumps({"input": texts, "model": model}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(endpoint, data, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
        vectors = sorted(body["data"], key=lambda x: x["index"])
        if len(vectors) != len(texts):
            raise ValueError("embedding response length mismatch")
        return [x["embedding"] for x in vectors]
    return embed

def cache_path(root):
    return inside(Path(root).resolve(), ".melavonmen/semantic.sqlite")

def open_cache(root):
    path = cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")
    db.executescript(CACHE_SCHEMA)
    return db

def index_vectors(root, provider="local", model="all-MiniLM-L6-v2",
                  endpoint=None, allow_upload=False, max_items=10000):
    root = Path(root).resolve()
    source = connect(root, readonly=True)
    cache = open_cache(root)
    embed = client(provider, model, endpoint, allow_upload)
    max_items = max(1, min(int(max_items), 100000))
    records = source.execute(
        "SELECT path,qualified_name,line_start,signature,source_sha256 "
        "FROM symbols ORDER BY path,line_start LIMIT ?", (max_items,)).fetchall()
    count = 0
    try:
        cache.execute("BEGIN IMMEDIATE")
        # Purge changed/removed items, not the entire vector store.
        valid = {(r["path"], r["qualified_name"], r["source_sha256"]) for r in records}
        for old in list(cache.execute(
                "SELECT path,qualified_name,source_sha256 FROM vectors WHERE provider=? AND model=?",
                (provider, model))):
            if tuple(old) not in valid:
                cache.execute("DELETE FROM vectors WHERE path=? AND qualified_name=? AND provider=? AND model=?",
                              (old["path"], old["qualified_name"], provider, model))
        for rec in records:
            # Exact signature and path are the indexed document; no whole repo upload.
            content = rec["path"] + ":" + rec["qualified_name"] + "\n" + rec["signature"]
            digest = hashlib.sha256(content.encode()).hexdigest()
            cached = cache.execute(
                "SELECT content_sha256,source_sha256 FROM vectors WHERE path=? AND "
                "qualified_name=? AND provider=? AND model=?",
                (rec["path"], rec["qualified_name"], provider, model)).fetchone()
            if cached and cached["content_sha256"] == digest and (
                    cached["source_sha256"] == rec["source_sha256"]):
                continue
            vector = embed([content])[0]
            if not vector or not all(math.isfinite(float(x)) for x in vector):
                raise ValueError("embedding provider returned invalid vector")
            cache.execute("""INSERT OR REPLACE INTO vectors
                 (path,qualified_name,line_start,source_sha256,content_sha256,
                  provider,model,embedding) VALUES(?,?,?,?,?,?,?,?)""",
                 (rec["path"], rec["qualified_name"], rec["line_start"],
                  rec["source_sha256"], digest, provider, model, json.dumps(vector)))
            count += 1
        cache.commit()
    except Exception:
        cache.rollback()
        raise
    finally:
        cache.close()
        source.close()
    return {"ok": True, "embedded_new_or_changed": count,
            "provider": provider, "model": model,
            "remote_code_upload": provider == "remote"}

def _cosine(a, b):
    if len(a) != len(b) or not a:
        return 0.
    dot = sum(float(x)*float(y) for x, y in zip(a,b))
    den = math.sqrt(sum(float(x)**2 for x in a)*sum(float(y)**2 for y in b))
    return dot/den if den else 0.

def semantic_query(root, phrase, provider="local", model="all-MiniLM-L6-v2",
                   endpoint=None, allow_upload=False, limit=10):
    # Failure always degrades to deterministic code search, not a server crash.
    fallback = query(root, phrase, mode="natural", limit=limit)
    try:
        embed = client(provider, model, endpoint, allow_upload)
        needle = embed([phrase])[0]
        cache = open_cache(root)
        source = connect(Path(root).resolve(), readonly=True)
        records = []
        for row in cache.execute("SELECT * FROM vectors WHERE provider=? AND model=?",
                                 (provider, model)):
            f = source.execute("SELECT sha256 FROM files WHERE path=?", (row["path"],)).fetchone()
            if not f or f["sha256"] != row["source_sha256"]:
                continue
            score = _cosine(needle, json.loads(row["embedding"]))
            records.append({"path": row["path"], "symbol": row["qualified_name"],
                            "line_start": row["line_start"],
                            "line_end": row["line_start"], "kind": "symbol",
                            "score": round(score, 6),
                            "evidence": ["embedding_similarity"],
                            "verification_status": "unverified"})
        cache.close()
        source.close()
        ranked = sorted(records, key=lambda x: -x["score"])[:max(1, min(limit, 100))]
        return {"query": phrase, "results": ranked,
                "fallback_results": fallback["results"], "warnings": []}
    except (OSError, ImportError, ValueError, RuntimeError, sqlite3.Error) as exc:
        return {"query": phrase, "results": fallback["results"],
                "warnings": ["semantic unavailable; deterministic fallback: " +
                             type(exc).__name__]}
