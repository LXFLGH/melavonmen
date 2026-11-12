"""Tool contracts and workspace operations shared by MCP and the CLI."""

from collections import Counter, defaultdict
from contextlib import closing
import json
from pathlib import Path, PurePosixPath
import re

from .graph import Graph, from_revision
from .history import History, pull_request
from .index import Index, location, token_estimate
from .workspace import IndexErrorWithCode, atomic_json, atomic_write, config_file, git_text, read_config, run_git


def string(description="", *values):
    return {"type": "string", "description": description, **({"enum": list(values)} if values else {})}


def integer(low, high):
    return {"type": "integer", "minimum": low, "maximum": high}


BOOLEAN = {"type": "boolean"}
FILTERS = {key: string() for key in ("fileType", "directory", "chunkType", "blameAuthor", "blameSha", "blameSince", "blameUntil")}
LIMIT = integer(1, 100)
DEPTH = integer(1, 100)
BUDGET = integer(128, 4000)
DIRECTION = string("Call relationship direction", "callers", "callees", "both")
GRAPH_PATH = {"from": string(), "to": string(), "fromFilePath": string(), "toFilePath": string(), "maxDepth": DEPTH}


def tool(description, properties=None, required=()):
    return description, {"type": "object", "properties": properties or {}, "required": list(required), "additionalProperties": False}


TOOLS = {
    "index_codebase": tool("Build or refresh the current branch index.",
                           {key: BOOLEAN for key in ("force", "estimateOnly", "dryRun", "verbose")}),
    "index_status": tool("Report local index readiness and optional source freshness.", {"checkFreshness": BOOLEAN}),
    "index_health_check": tool("Check the local index for database or catalog inconsistencies."),
    "index_metrics": tool("Read operation counts for this session.", {"reset": BOOLEAN}),
    "index_logs": tool("Read recent indexing and retrieval diagnostics.",
                       {"limit": LIMIT, "category": string(), "level": string()}),
    "codebase_search": tool("Find relevant code and return source ranges and snippets.",
                            {**FILTERS, "query": string(), "limit": LIMIT, "contextLines": integer(0, 100)}, ("query",)),
    "codebase_peek": tool("Find relevant files and symbols with metadata only.",
                          {**FILTERS, "query": string(), "limit": LIMIT}, ("query",)),
    "find_similar": tool("Find analogous code by vector similarity in hybrid mode.",
                         {**FILTERS, "code": string(), "excludeFile": string(), "limit": LIMIT}, ("code",)),
    "implementation_lookup": tool("Find a symbol definition and its source.",
                                  {**FILTERS, "query": string(), "limit": LIMIT, "tokenBudget": BUDGET}, ("query",)),
    "call_graph": tool("Find direct callers or callees. Supply filePath for duplicate names.",
                       {"name": string(), "direction": DIRECTION, "filePath": string(), "symbolId": string(),
                        "relationshipType": string()}, ("name",)),
    "call_graph_path": tool("Find a shortest indexed path between two symbols.", GRAPH_PATH, ("from", "to")),
    "codebase_context": tool("Return compact repository evidence within a token budget.",
                             {**GRAPH_PATH, "query": string(), "symbol": string(), "fileType": string(),
                              "directory": string(), "limit": LIMIT, "tokenBudget": BUDGET,
                              "allowUnscopedRecovery": BOOLEAN, "diagnostic": BOOLEAN}, ("query",)),
    "codebase_edit_context": tool("Return bounded source, call sites and optional tests for an edit target.",
                                  {"query": string(), "symbol": string(), "filePath": string(),
                                   "callerLimit": integer(0, 50), "calleeLimit": integer(0, 50),
                                   "tokenBudget": BUDGET, "includeApiImpact": BOOLEAN, "includeTests": BOOLEAN}, ("query",)),
    "architecture_context": tool("Summarize modules, dependencies and optional Git activity.",
                                  {"query": string(), "directory": string(), "depth": integer(1, 3),
                                   "includeRecentActivity": BOOLEAN, "tokenBudget": BUDGET}),
    "code_communities": tool("Find graph communities, hubs and cross-community coupling.",
                              {"branch": string(), "minSize": LIMIT, "limit": LIMIT, "hubThreshold": integer(0, 1000),
                               "minCoupling": LIMIT, "couplingLimit": LIMIT}),
    "pr_impact": tool("Analyze affected symbols in a branch, PR or current working tree.",
                      {"pr": integer(1, 2_147_483_647), "branch": string(), "workingTree": BOOLEAN,
                       "maxDepth": DEPTH, "hubThreshold": integer(1, 1000), "checkConflicts": BOOLEAN,
                       "direction": DIRECTION}),
    "add_knowledge_base": tool("Add and index an explicitly selected directory.", {"path": string()}, ("path",)),
    "list_knowledge_bases": tool("List the workspace's additional indexed directories."),
    "remove_knowledge_base": tool("Remove a directory from search scope and refresh the index.", {"path": string()}, ("path",)),
    "repository_history_sync": tool("Synchronize issue and PR discussion into a local cache using gh.",
                                    {"repository": string(), "since": string()}),
    "repository_history_status": tool("Inspect the local GitHub history cache.", {"repository": string()}),
    "repository_history_search": tool("Search authorized cached GitHub history with source links.",
                                      {"repository": string(), "query": string(), "kind": string(), "state": string(),
                                       "author": string(), "limit": LIMIT}, ("query",)),
    "repository_history_clear": tool("Clear the selected repository's local history cache.", {"repository": string()}),
}


def validated(name, arguments):
    if name not in TOOLS:
        raise IndexErrorWithCode(f"Unknown tool: {name}")
    if not isinstance(arguments, dict):
        raise IndexErrorWithCode("arguments must be an object")
    values = {key: value for key, value in arguments.items() if value is not None}
    contract = TOOLS[name][1]
    if set(contract["required"]) - values.keys():
        raise IndexErrorWithCode(f"Required: {', '.join(contract['required'])}")
    for key, value in values.items():
        schema = contract["properties"].get(key)
        if schema is None:
            raise IndexErrorWithCode(f"Unknown argument: {key}")
        valid = {"string": str, "integer": int, "boolean": bool}[schema["type"]]
        if type(value) is not valid or (valid is str and (not value.strip() or len(value) > 200_000)):
            raise IndexErrorWithCode(f"Invalid {key}. Expected {schema['type']}.")
        if valid is int and not schema["minimum"] <= value <= schema["maximum"]:
            raise IndexErrorWithCode(f"{key} must be between {schema['minimum']} and {schema['maximum']}")
        if "enum" in schema and value not in schema["enum"]:
            raise IndexErrorWithCode(f"Unknown value for {key}")
    return values


def result(text, **data):
    return {"content": [{"type": "text", "text": text}], "structuredContent": data}


def json_result(data):
    return result(json.dumps(data, indent=2, ensure_ascii=False), **data)


def edge_text(graph, edge):
    return (f"{graph.symbols[edge['from']]['qualifiedName']} → {graph.symbols[edge['to']]['qualifiedName']} "
            f"at {location(edge['path'], edge['line'])} ({edge['type']})")


def bounded_hits(hits, budget, with_source=True):
    output, kept = [], []
    remaining = budget
    for hit in hits:
        label = f"{hit.get('qualifiedName') or hit.get('name') or hit['kind']} · {location(hit['path'], hit['lineStart'], hit['lineEnd'])}"
        metadata = {k: v for k, v in hit.items() if k != "text"}
        if token_estimate(label) > remaining:
            break
        remaining -= token_estimate(label)
        content = []
        if with_source and hit.get("text"):
            for line in hit["text"].splitlines():
                cost = token_estimate(line) + 1
                if cost > remaining - 8:
                    break
                content.append(line)
                remaining -= cost
        if content:
            metadata["text"] = "\n".join(content)
            metadata["lineEnd"] = hit["lineStart"] + len(content) - 1
            label = f"{hit.get('qualifiedName') or hit.get('name') or hit['kind']} · {location(hit['path'], metadata['lineStart'], metadata['lineEnd'])}"
            label += "\n" + metadata["text"]
        output.append(label)
        kept.append(metadata)
    return "\n\n".join(output) or "No matching source found.", kept


def test_path(path):
    return bool(re.search(r"(?:^|/)(?:tests?|__tests__)(?:/|$)|(?:^|/)(?:test_)|(?:[._-](?:test|spec)\.)", path, re.I))


class Tools:
    def __init__(self, workspace):
        self.workspace = workspace
        self.index = Index(workspace)
        self.history = History(self.index)

    def invoke(self, name, arguments=None, cancel=None, progress=None):
        values = validated(name, arguments if arguments is not None else {})
        self.index.metrics["toolCalls"] += 1
        try:
            return getattr(self, name)(values, cancel, progress)
        except IndexErrorWithCode as exc:
            self.index.metrics["errors"] += 1
            self.index.log("general", f"{name}: {exc.code}", "error")
            raise

    def index_codebase(self, a, cancel, progress):
        return json_result(self.index.refresh(force=a.get("force", False), estimate=a.get("estimateOnly", False),
                                              dry=a.get("dryRun", False), verbose=a.get("verbose", False),
                                              cancel=cancel, progress=progress))

    def index_status(self, a, cancel, _):
        return json_result(self.index.status(a.get("checkFreshness", False), cancel))

    def index_health_check(self, _a, _cancel, _):
        conn = self.index.connect()
        if conn is None:
            return json_result({"ok": False, "state": "missing", "issues": ["Run index_codebase to build the index."]})
        with closing(conn):
            messages = [row[0] for row in conn.execute("PRAGMA quick_check")]
            missing = conn.execute("SELECT count(*) FROM files LEFT JOIN documents USING(digest) WHERE documents.digest IS NULL").fetchone()[0]
            missing_terms = conn.execute("SELECT count(*) FROM chunks LEFT JOIN terms ON terms.rowid=chunks.id WHERE terms.rowid IS NULL").fetchone()[0]
            issues = [] if messages == ["ok"] else messages
            if missing or missing_terms:
                issues.append(f"Missing catalog records: {missing} documents and {missing_terms} full-text entries")
        return json_result({"ok": not issues, "issues": issues})

    def index_metrics(self, a, _cancel, _):
        if a.get("reset"):
            self.index.metrics.clear()
        return json_result({"metrics": dict(self.index.metrics)})

    def index_logs(self, a, _cancel, _):
        levels = {"debug": 0, "info": 1, "warn": 2, "error": 3}
        if a.get("level") not in (None, *levels):
            raise IndexErrorWithCode("Unknown log level")
        entries = [entry for entry in list(self.index.logs)
                   if (not a.get("category") or a["category"] == entry["category"])
                   and levels[entry["level"]] >= levels.get(a.get("level"), 0)]
        return json_result({"entries": entries[-a.get("limit", 20):]})

    def codebase_search(self, a, cancel, _):
        hits = self.index.search(a["query"], a, cancel)
        text, kept = bounded_hits(hits, 8000)
        return result(text, results=kept)

    def codebase_peek(self, a, cancel, _):
        hits = self.index.search(a["query"], {"limit": 10, **a}, cancel)
        text, kept = bounded_hits(hits, 4000, False)
        return result(text, results=kept)

    def find_similar(self, a, cancel, _):
        hits = self.index.search(a["code"], {"limit": 10, **a}, cancel, similar=True)
        text, kept = bounded_hits(hits, 8000)
        return result(text, results=kept)

    def graph(self, cancel, branch=None):
        if branch and branch != self.workspace.branch:
            return from_revision(self.workspace, self.workspace.commit(branch))
        branch, _ = self.index.ready(cancel)
        return Graph(self.index.documents(branch))

    def definitions(self, graph, a, cancel):
        query = a["query"]
        candidates = graph.candidates(query, a.get("filePath"))
        exact = bool(re.fullmatch(r"[\w$]+(?:[.:][\w$]+)*", query))
        if not candidates and not exact:
            for word in re.findall(r"[\w.$]+", query):
                candidates.extend(graph.candidates(word, a.get("filePath")))
        match = "definition"
        if not candidates and not exact:
            match = "conceptual-candidate"
            for hit in self.index.search(query, {**a, "limit": min(30, a.get("limit", 5) * 4)}, cancel):
                candidates.extend(key for key in graph.by_file[hit["path"]]
                                  if hit["lineStart"] <= graph.symbols[key]["lineStart"] <= hit["lineEnd"])
        def eligible(key):
            path = graph.symbols[key]["path"]
            return ((not a.get("fileType") or Path(path).suffix.lower() == "." + a["fileType"].lstrip(".").lower())
                    and (not a.get("directory") or a["directory"] == "." or path.startswith(a["directory"].rstrip("/") + "/")))
        ordered = [key for key in dict.fromkeys(candidates) if eligible(key)]
        ordered.sort(key=lambda key: test_path(graph.symbols[key]["path"]))
        return [{**graph.snippet(key), "match": match} for key in ordered[:a.get("limit", 5)]]

    def implementation_lookup(self, a, cancel, _):
        hits = self.definitions(self.graph(cancel), a, cancel)
        text, kept = bounded_hits(hits, a.get("tokenBudget", 1500))
        return result(text, results=kept)

    def call_graph(self, a, cancel, _):
        graph = self.graph(cancel)
        key = graph.identify(a.get("symbolId") or a["name"], a.get("filePath"))
        edges = graph.edges(key, a.get("direction", "callers"), a.get("relationshipType"))[:200]
        lines = [edge_text(graph, edge) for edge in edges]
        unknown = [e for e in graph.unresolved if e["caller"] == key][:50]
        return result("\n".join(lines) or "No resolved static relationships.", symbol=graph.symbols[key],
                      edges=edges, unresolved=unknown, evidence="static")

    def call_graph_path(self, a, cancel, _):
        return self.graph_path(self.graph(cancel), a)

    @staticmethod
    def graph_path(graph, a):
        start = graph.identify(a["from"], a.get("fromFilePath"))
        end = graph.identify(a["to"], a.get("toFilePath"))
        path = graph.path(start, end, a.get("maxDepth", 10))
        text = "\n".join(edge_text(graph, edge) for edge in path) if path else (
            "The endpoints are the same symbol." if path == [] else "No resolved path in the selected depth.")
        return result(text, path=path, start=graph.symbols[start], end=graph.symbols[end], evidence="static")

    def codebase_context(self, a, cancel, progress):
        budget = a.get("tokenBudget", 600)
        if a.get("from") or a.get("to"):
            if not (a.get("from") and a.get("to")):
                raise IndexErrorWithCode("Supply both graph endpoints")
            graph = self.graph(cancel)
            data = self.graph_path(graph, a)
            edges, total = [], 0
            for edge in data["structuredContent"]["path"] or []:
                line = edge_text(graph, edge)
                if total + token_estimate(line) > budget:
                    break
                edges.append((edge, line))
                total += token_estimate(line)
            text = "\n".join(line for _, line in edges) or data["content"][0]["text"].splitlines()[0][:budget]
            return result(text, route="path", path=[edge for edge, _ in edges])
        if a.get("symbol"):
            hits = self.definitions(self.graph(cancel), {**a, "query": a["symbol"]}, cancel)
            route = "definition"
        else:
            hits = self.index.search(a["query"], {"limit": 5, **a}, cancel)
            if not hits and a.get("directory") and a.get("allowUnscopedRecovery"):
                hits = self.index.search(a["query"], {k: v for k, v in a.items() if k != "directory"}, cancel)
            route = "search"
        text, kept = bounded_hits(hits, budget)
        details = {"route": route, "results": kept, "omitted": len(hits) - len(kept)}
        if a.get("diagnostic"):
            details["diagnostic"] = {"query": a["query"], "candidateCount": len(hits), "tokenBudget": budget}
        return result(text, **details)

    def codebase_edit_context(self, a, cancel, _):
        graph = self.graph(cancel)
        if a.get("symbol"):
            target = graph.identify(a["symbol"], a.get("filePath"))
            hits = [graph.snippet(target)]
        else:
            hits = self.definitions(graph, {**a, "limit": 1}, cancel)
            target = hits[0]["symbolId"] if hits else None
        budget = a.get("tokenBudget", 1200)
        if not target:
            hits = self.index.search(a["query"], {"limit": 4}, cancel)
        text, kept = bounded_hits(hits, max(64, budget // 2))
        output, used = [text], token_estimate(text)
        evidence = {"results": kept, "target": graph.symbols.get(target), "edges": [], "tests": [],
                    "evidence": "static", "route": "definition" if target else "search"}
        if target:
            edges = (graph.incoming[target][:a.get("callerLimit", 5)] + graph.outgoing[target][:a.get("calleeLimit", 5)])
            for edge in edges:
                line = edge_text(graph, edge)
                if used + token_estimate(line) > budget:
                    break
                output.append(line)
                used += token_estimate(line)
                evidence["edges"].append(edge)
            if a.get("includeTests"):
                name = graph.symbols[target]["name"]
                pattern = re.compile(r"\b" + re.escape(name) + r"\b")
                for path, row in graph.records.items():
                    if not test_path(path):
                        continue
                    for n, source in enumerate(row["text"].splitlines(), 1):
                        if not pattern.search(source):
                            continue
                        line = f"Test reference · {location(path, n)}"
                        if used + token_estimate(line) > budget:
                            break
                        output.append(line)
                        used += token_estimate(line)
                        evidence["tests"].append({"path": path, "line": n, "kind": "text-reference"})
            if a.get("includeApiImpact"):
                source_file = graph.symbols[target]["path"]
                callers = {edge["from"] for edge in graph.incoming[target]}
                evidence["apiImpact"] = {"declaration": graph.symbols[target], "incomingSites": len(graph.incoming[target]),
                                         "externalCallers": sum(graph.symbols[key]["path"] != source_file for key in callers),
                                         "evidence": "indexed call sites"}
        return result("\n".join(output), **evidence)

    def architecture_context(self, a, cancel, _):
        graph = self.graph(cancel)
        focus, depth = a.get("directory", "").rstrip("/"), a.get("depth", 2)
        budget = a.get("tokenBudget", 1200)
        relevant = {hit["path"] for hit in self.index.search(a["query"], {"limit": 15, "directory": focus}, cancel)} if a.get("query") else None
        grouped, links = defaultdict(list), Counter()
        def module(path):
            parts = PurePosixPath(path).parts
            return "/".join(parts[:-1][:depth]) or "."
        for path in graph.records:
            if (not focus or path.startswith(focus + "/")) and (relevant is None or path in relevant):
                grouped[module(path)].append(path)
        for edges in graph.outgoing.values():
            for edge in edges:
                left = module(graph.symbols[edge["from"]]["path"])
                right = module(graph.symbols[edge["to"]]["path"])
                if left != right and left in grouped and right in grouped:
                    links[left, right] += 1
        output, modules, dependencies, activity = [], [], [], []
        used = 0
        for name, paths in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
            count = sum(len(graph.by_file[p]) for p in paths)
            line = f"{name} · {len(paths)} files · {count} definitions · {', '.join(paths[:3])}"
            if used + token_estimate(line) > budget:
                break
            output.append(line)
            used += token_estimate(line)
            modules.append({"name": name, "files": len(paths), "symbols": count, "examples": paths[:3]})
        for (left, right), count in links.most_common():
            line = f"{left} → {right} · {count} indexed relationships"
            if used + token_estimate(line) > budget:
                break
            output.append(line)
            used += token_estimate(line)
            dependencies.append({"from": left, "to": right, "edges": count})
        if a.get("includeRecentActivity"):
            recent = git_text(self.workspace.root, "log", "-5", "--format=%h %s", "--", focus or ".") or ""
            for line in recent.splitlines():
                if used + token_estimate(line) > budget:
                    break
                output.append(line)
                used += token_estimate(line)
                activity.append(line)
        return result("\n".join(output) or "No matching modules.", modules=modules, dependencies=dependencies, activity=activity)

    def code_communities(self, a, cancel, _):
        graph = self.graph(cancel, a.get("branch"))
        groups, hubs, couplings = graph.communities(a.get("minSize", 1), a.get("hubThreshold", 5), a.get("minCoupling", 1))
        limit = a.get("limit", 20)
        for group in groups[:limit]:
            group["members"] = group["members"][:20]
        return json_result({"communities": groups[:limit], "hubs": hubs[:limit],
                            "couplings": couplings[:a.get("couplingLimit", 20)]})

    def pr_impact(self, a, cancel, _):
        number, branch = a.get("pr"), a.get("branch")
        before = None
        if a.get("workingTree"):
            if number or branch or a.get("checkConflicts"):
                raise IndexErrorWithCode("workingTree is exclusive of pr, branch and checkConflicts")
            graph = self.graph(cancel)
            status = self.index.status(True, cancel)
            if not status["freshness"]["current"]:
                raise IndexErrorWithCode("Refresh the index before analyzing working-tree changes", "INDEX_STALE")
            paths = self.workspace.changed()
            scope = {"kind": "workingTree", "head": status["head"], "branch": status["branch"]}
        else:
            if number and branch:
                raise IndexErrorWithCode("Specify either a PR or a branch")
            if number:
                pr = pull_request(self.workspace, number)
                head = pr["head"]["sha"]
                base = pr["base"]["sha"]
                for revision, ref in ((base, pr["base"]["ref"]), (head, f"refs/pull/{number}/head")):
                    if not git_text(self.workspace.root, "rev-parse", "--verify", f"{revision}^{{commit}}"):
                        command = run_git(self.workspace.root, "fetch", "--no-tags", "--no-write-fetch-head", "origin", ref)
                        if command is None or command.returncode:
                            raise IndexErrorWithCode("Unable to retrieve PR commit objects", "GIT_ERROR")
                scope = {"kind": "pr", "pr": number, "url": pr["html_url"], "head": head}
            else:
                head = self.workspace.commit(branch or "HEAD")
                base = self.workspace.base_ref()
                scope = {"kind": "branch", "branch": branch or self.workspace.branch, "head": head}
            merge_base = self.workspace.merge_base(base, head)
            paths = self.workspace.changed(merge_base, head)
            graph = from_revision(self.workspace, head)
            before = from_revision(self.workspace, merge_base)
        evidence = graph.impact(paths[:200], a.get("maxDepth", 5), a.get("direction", "both"), a.get("hubThreshold", 10))
        if before is not None:
            previous = before.impact(paths[:200], a.get("maxDepth", 5), a.get("direction", "both"), a.get("hubThreshold", 10))
            after_symbols = {(s["path"], s["qualifiedName"]): s for s in evidence["changedSymbols"]}
            old_symbols = {(s["path"], s["qualifiedName"]): s for s in previous["changedSymbols"]}
            evidence["removedSymbols"] = [old_symbols[key] for key in sorted(old_symbols.keys() - after_symbols.keys())]
            evidence["addedSymbols"] = [after_symbols[key] for key in sorted(after_symbols.keys() - old_symbols.keys())]
            evidence["signatureChanges"] = [
                {"before": old_symbols[key], "after": after_symbols[key]}
                for key in sorted(old_symbols.keys() & after_symbols.keys())
                if old_symbols[key].get("signature") != after_symbols[key].get("signature")
            ]
            evidence["previouslyAffectedSymbols"] = previous["affectedSymbols"]
            evidence["unassessed"] = sorted(set(previous["unassessed"]) & set(evidence["unassessed"]))
            assessed = bool(previous["affectedSymbols"] or evidence["affectedSymbols"])
            evidence["riskLevel"] = ("UNKNOWN" if evidence["unassessed"] else
                                     "HIGH" if previous["hubs"] or evidence["hubs"] else
                                     "MEDIUM" if assessed else "LOW")
        evidence["scope"] = scope
        evidence["omittedFiles"] = max(0, len(paths) - 200)
        if evidence["omittedFiles"]:
            evidence["riskLevel"] = "UNKNOWN"
        if a.get("checkConflicts"):
            evidence["conflicts"] = self.history.overlapping_pulls(paths, number, cancel)
        return json_result(evidence)

    def knowledge_update(self, path, add, cancel):
        file = self.workspace.override or config_file(self.workspace.root)
        settings = read_config(file)
        original = list(settings.get("knowledgeBases", []))
        resolved = (self.workspace.root / Path(path).expanduser()).resolve()
        if add:
            if not resolved.is_dir():
                raise IndexErrorWithCode(f"Knowledge base is not a directory: {resolved}")
            if resolved not in self.workspace.knowledge_roots(settings):
                settings["knowledgeBases"] = [*original, str(resolved)]
        else:
            settings["knowledgeBases"] = [p for p in original
                                          if (self.workspace.root / Path(p).expanduser()).resolve() != resolved]
        list(self.workspace.knowledge_roots(settings))
        if settings.get("knowledgeBases", []) != original:
            before = file.read_bytes() if file.is_file() else None
            atomic_json(file, settings)
            published = file.read_bytes()
            try:
                self.index.refresh(cancel=cancel)
            except BaseException:
                if file.is_file() and file.read_bytes() == published:
                    if before is None:
                        file.unlink()
                    else:
                        atomic_write(file, before)
                raise
        return json_result({"knowledgeBases": settings.get("knowledgeBases", [])})

    def add_knowledge_base(self, a, cancel, _):
        return self.knowledge_update(a["path"], True, cancel)

    def remove_knowledge_base(self, a, cancel, _):
        return self.knowledge_update(a["path"], False, cancel)

    def list_knowledge_bases(self, _a, _cancel, _):
        return json_result({"knowledgeBases": [str(p) for p in self.workspace.knowledge_roots(self.workspace.settings)]})

    def repository_history_sync(self, a, cancel, _):
        return json_result(self.history.sync(a.get("repository"), a.get("since"), cancel))

    def repository_history_status(self, a, _cancel, _):
        return json_result(self.history.status(a.get("repository")))

    def repository_history_search(self, a, _cancel, _):
        return json_result({"results": self.history.search(a["query"], a)})

    def repository_history_clear(self, a, _cancel, _):
        return json_result(self.history.clear(a.get("repository")))
