"""Vector providers and cosine similarity. No provider is used in structural mode."""

import hashlib
import json
import math
import os
import struct
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .workspace import IndexErrorWithCode


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Embeddings:
    def __init__(self, settings):
        self.kind = settings.get("embeddingProvider", "auto")
        if self.kind == "auto":
            self.kind = "openai" if os.environ.get("OPENAI_API_KEY") else (
                "google" if os.environ.get("GEMINI_API_KEY") else "ollama"
            )
        defaults = {
            "openai": ("https://api.openai.com/v1", "text-embedding-3-small", "OPENAI_API_KEY"),
            "google": ("https://generativelanguage.googleapis.com/v1beta", "gemini-embedding-001", "GEMINI_API_KEY"),
            "ollama": ("http://127.0.0.1:11434", "nomic-embed-text", ""),
            "custom": ("", "", ""),
        }
        if self.kind not in defaults:
            raise IndexErrorWithCode(f"Unsupported embedding provider: {self.kind}")
        url, model, env = defaults[self.kind]
        provider = settings.get("customProvider" if self.kind == "custom" else self.kind, {})
        self.url = provider.get("baseUrl", url).rstrip("/")
        self.model = provider.get("model", settings.get("embeddingModel", model))
        self.dimensions = provider.get("dimensions")
        self.api_key = provider.get("apiKey") or os.environ.get(env) if env else provider.get("apiKey")
        self.timeout = min(30, provider.get("timeoutMs", 15000) / 1000)
        self.batch_size = max(1, min(64, provider.get("maxBatchSize", 24)))
        target = urlsplit(self.url)
        if not self.model or target.scheme not in {"http", "https"} or not target.hostname or target.username or target.password:
            raise IndexErrorWithCode("An embedding model and a valid HTTP(S) endpoint are required")
        self.identity = hashlib.sha256(json.dumps([self.kind, self.url, self.model, self.dimensions]).encode()).hexdigest()

    def embed(self, texts, purpose="document"):
        if self.kind == "ollama":
            url, payload = self.url + "/api/embed", {"model": self.model, "input": texts}
        elif self.kind == "google":
            model = "models/" + self.model.removeprefix("models/")
            url = self.url + "/" + quote(model, safe="/") + ":batchEmbedContents"
            task = "RETRIEVAL_QUERY" if purpose == "query" else "RETRIEVAL_DOCUMENT"
            payload = {"requests": [
                {"model": model, "content": {"parts": [{"text": text}]}, "taskType": task,
                 **({"outputDimensionality": self.dimensions} if self.dimensions else {})}
                for text in texts
            ]}
        else:
            url, payload = self.url + "/embeddings", {"model": self.model, "input": texts}
            if self.dimensions and self.kind == "openai" and self.model.startswith("text-embedding-3"):
                payload["dimensions"] = self.dimensions
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            if self.kind == "google":
                headers["x-goog-api-key"] = self.api_key
            else:
                headers["Authorization"] = "Bearer " + self.api_key
        try:
            req = Request(url, json.dumps(payload).encode(), headers)
            with build_opener(NoRedirect).open(req, timeout=self.timeout) as response:
                data = json.loads(response.read(32 * 1024 * 1024))
            if self.kind == "ollama":
                vectors = data["embeddings"]
            elif self.kind == "google":
                vectors = [value["values"] for value in data["embeddings"]]
            else:
                rows = sorted(data["data"], key=lambda row: row["index"])
                if [row["index"] for row in rows] != list(range(len(texts))):
                    raise ValueError("unexpected embedding indices")
                vectors = [row["embedding"] for row in rows]
            if len(vectors) != len(texts) or len({len(v) for v in vectors}) != 1:
                raise ValueError("inconsistent embedding count or dimensions")
            if self.dimensions and len(vectors[0]) != self.dimensions:
                raise ValueError("endpoint returned a different vector dimension")
            return [normalize(vector) for vector in vectors]
        except HTTPError as exc:
            raise IndexErrorWithCode(f"Embedding endpoint returned HTTP {exc.code}", "EMBEDDING_ERROR") from exc
        except (URLError, TimeoutError, ValueError, KeyError, TypeError, OSError) as exc:
            raise IndexErrorWithCode("Embedding request failed or returned invalid vectors", "EMBEDDING_ERROR") from exc


def normalize(vector):
    length = math.sqrt(sum(x * x for x in vector))
    if not math.isfinite(length) or not length:
        raise ValueError("invalid vector magnitude")
    return [value / length for value in vector]


def pack(vector):
    return struct.pack(f"<{len(vector)}f", *vector)


def similarity(query, vector):
    if len(vector) != len(query) * 4:
        raise IndexErrorWithCode("Embedding dimensions changed. Use a new model configuration and rebuild.", "INDEX_INCOMPATIBLE")
    return sum(a * b for a, b in zip(query, struct.unpack(f"<{len(query)}f", vector)))


def rerank(query, hits, settings):
    options = settings.get("reranker", {})
    if not options.get("enabled") or not hits:
        return hits
    kind = options.get("provider", "custom")
    defaults = {
        "cohere": ("https://api.cohere.com/v2", "COHERE_API_KEY"),
        "jina": ("https://api.jina.ai/v1", "JINA_API_KEY"),
        "custom": ("", ""),
    }
    if kind not in defaults:
        raise IndexErrorWithCode("Unknown reranking provider")
    base, key_name = defaults[kind]
    base = options.get("baseUrl", base).rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or not options.get("model"):
        raise IndexErrorWithCode("Reranking requires an HTTP(S) endpoint and model")
    top = max(1, min(100, options.get("topN", 15), len(hits)))
    payload = {"model": options["model"], "query": query, "documents": [hit["text"] for hit in hits[:top]],
               "top_n": top}
    headers = {"Content-Type": "application/json"}
    if key := options.get("apiKey") or (os.environ.get(key_name) if key_name else None):
        headers["Authorization"] = "Bearer " + key
    try:
        req = Request(base + "/rerank", json.dumps(payload).encode(), headers)
        with build_opener(NoRedirect).open(req, timeout=min(30, options.get("timeoutMs", 10000) / 1000)) as response:
            result = json.loads(response.read(2 * 1024 * 1024))["results"]
        indices = [item["index"] for item in result]
        if any(type(i) is not int or not 0 <= i < top for i in indices) or len(set(indices)) != len(indices):
            raise ValueError("invalid candidate positions")
        seen = set(indices)
        return [hits[i] for i in indices] + [hit for i, hit in enumerate(hits) if i not in seen]
    except (URLError, OSError, ValueError, KeyError, TypeError) as exc:
        raise IndexErrorWithCode("The configured reranking endpoint did not return a valid result", "RERANK_ERROR") from exc
