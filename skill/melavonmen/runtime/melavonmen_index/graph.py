"""Definitions and source-backed call graph traversal."""

from collections import defaultdict, deque
import io
import json
from pathlib import PurePosixPath
import posixpath
import re
from zipfile import ZipFile

from . import parser
from .index import location
from .workspace import LANGUAGES, MAX_FILE_BYTES, IndexErrorWithCode, git_output, permitted


def from_revision(workspace, sha):
    raw = git_output(workspace.root, "archive", "--format=zip", sha)
    if raw is None:
        raise IndexErrorWithCode("The selected Git commit could not be read", "GIT_ERROR")
    records = []
    with ZipFile(io.BytesIO(raw)) as archive:
        for file in archive.infolist():
            path = file.filename
            lang = LANGUAGES.get(PurePosixPath(path).suffix.lower())
            if (file.is_dir() or not lang or not permitted(path) or file.file_size > MAX_FILE_BYTES
                    or file.external_attr >> 28 == 0xA):
                continue
            try:
                source = archive.read(file).decode("utf-8-sig")
            except UnicodeError:
                continue
            symbols, calls, imports, warnings = parser.extract(source, lang)
            records.append({"path": path, "text": source, "language": lang,
                            "symbols": symbols, "calls": calls, "imports": imports, "warnings": warnings})
    return Graph(records)


class Graph:
    def __init__(self, records):
        self.records = {row["path"]: row for row in records}
        self.symbols = {}
        self.names = defaultdict(set)
        self.by_file = defaultdict(set)
        self.outgoing = defaultdict(list)
        self.incoming = defaultdict(list)
        self.unresolved = []
        self.module_paths = self._module_paths()
        self.reexports = {path: list(parser.js_reexports(row["text"])) for path, row in self.records.items()
                          if row["language"] in {"javascript", "typescript"}}
        for row in records:
            path = row["path"]
            for symbol in self.unpack(row, "symbols"):
                key = f"{path}:{symbol['lineStart']}:{symbol['qualifiedName']}"
                self.symbols[key] = {**symbol, "symbolId": key, "path": path, "language": row["language"]}
                self.by_file[path].add(key)
                for name in {symbol["name"], symbol["qualifiedName"]}:
                    self.names[name].add(key)
        for row in records:
            self._resolve_calls(row)

    @staticmethod
    def unpack(row, name):
        data = row[name]
        return json.loads(data) if isinstance(data, str) else data

    def _module_paths(self):
        modules = defaultdict(set)
        for path, row in self.records.items():
            stem = str(PurePosixPath(path).with_suffix(""))
            modules[stem].add(path)
            if stem.endswith(("/index", "/__init__")):
                modules[posixpath.dirname(stem)].add(path)
            if row["language"] == "python":
                modules[stem.replace("/", ".")].add(path)
        return modules

    def _module(self, source, spec, language):
        folder = posixpath.dirname(source)
        if language == "python":
            if spec.startswith("."):
                level = len(spec) - len(spec.lstrip("."))
                path = posixpath.normpath(posixpath.join(folder, "../" * (level - 1), spec[level:].replace(".", "/")))
                return self.module_paths.get(path, set())
            return self.module_paths.get(spec, set())
        if spec.startswith("."):
            path = posixpath.normpath(posixpath.join(folder, spec))
            ext = PurePosixPath(path).suffix
            if ext in LANGUAGES:
                path = str(PurePosixPath(path).with_suffix(""))
            return self.module_paths.get(path, set())
        return self.module_paths.get(spec, set())

    def _exported(self, file, name, seen):
        key = (file, name)
        if key in seen or len(seen) >= 32:
            return set()
        seen = seen | {key}
        candidates = set(self.names.get(name, set()) & self.by_file[file])
        if name == "default":
            for declared in re.findall(
                    r"\bexport\s+default\s+(?:(?:async\s+)?function\s+|class\s+)?(\w+)",
                    parser.mask(self.records[file]["text"])):
                candidates.update(self.names[declared] & self.by_file[file])
        explicit = [(module, imported) for exported, module, imported in self.reexports.get(file, ()) if exported == name]
        wildcard = [(module, name) for exported, module, _ in self.reexports.get(file, ()) if exported == "*"]
        for module, imported in explicit or ([] if candidates or name == "default" else wildcard):
            for other in self._module(file, module, self.records[file]["language"]):
                candidates.update(self._exported(other, imported, seen))
        return candidates

    def _imported_target(self, path, target, imports, language):
        first, _, rest = target.partition(".")
        if first not in imports:
            return set()
        module, imported = imports[first]
        choices = self._module(path, module, language)
        resolved_name = rest if imported == "*" else imported + ("." + rest if rest else "")
        return {key for file in choices for key in self._exported(file, resolved_name, set())}

    def _resolve_calls(self, row):
        path, language = row["path"], row["language"]
        scopes = defaultdict(dict)
        for name, module, symbol, *scope in self.unpack(row, "imports"):
            scopes[scope[0] if scope else ""][name] = (module, symbol)
        owners = {(self.symbols[k]["lineStart"], self.symbols[k]["qualifiedName"]): k for k in self.by_file[path]}
        for start, owner, target, callsite, relation in self.unpack(row, "calls"):
            source = owners.get((start, owner))
            if source is None:
                continue
            parts = owner.split(".")
            imports = dict(scopes[""])
            for level in range(1, len(parts) + 1):
                imports.update(scopes[".".join(parts[:level])])
            first, _, rest = target.partition(".")
            targets = self._imported_target(path, target, imports, language)
            if first not in imports:
                if first in {"self", "cls", "this"} and "." in owner:
                    targets = self.names.get(owner.rsplit(".", 1)[0] + "." + rest, set()) & self.by_file[path]
                else:
                    targets = self.names.get(target, set()) & self.by_file[path]
                    if len(targets) > 1 and "." in owner and "." not in target:
                        local = self.names.get(owner.rsplit(".", 1)[0] + "." + target, set()) & self.by_file[path]
                        targets = local or targets
                    if not targets and language in {"c-family", "go", "rust", "swift", "kotlin", "java", "csharp", "gdscript"}:
                        targets = {key for key in self.names.get(target, set())
                                   if PurePosixPath(self.symbols[key]["path"]).parent == PurePosixPath(path).parent
                                   and self.symbols[key]["language"] == language}
            if len(targets) != 1:
                self.unresolved.append({"caller": source, "target": target, "path": path, "line": callsite,
                                        "reason": "ambiguous" if targets else "unresolved"})
                continue
            dest = next(iter(targets))
            if relation == "Call":
                kind = self.symbols[dest]["kind"]
                relation = ("Constructor" if kind in {"class", "struct"} else
                            "MethodCall" if "." in self.symbols[dest]["qualifiedName"] else "Call")
            edge = {"from": source, "to": dest, "path": path, "line": callsite, "type": relation}
            self.outgoing[source].append(edge)
            self.incoming[dest].append(edge)

    def candidates(self, name, file=None):
        if name in self.symbols:
            keys = {name}
        else:
            keys = self.names.get(name, set())
        return sorted((key for key in keys if not file or self.symbols[key]["path"] == file),
                      key=lambda key: (self.symbols[key]["path"], self.symbols[key]["lineStart"], key))

    def identify(self, name, file=None):
        keys = self.candidates(name, file)
        if len(keys) != 1:
            details = ", ".join(location(self.symbols[k]["path"], self.symbols[k]["lineStart"]) for k in keys[:12])
            if keys:
                raise IndexErrorWithCode(f"Ambiguous symbol {name}. Supply a file or symbol ID: {details}", "AMBIGUOUS_SYMBOL")
            raise IndexErrorWithCode(f"Symbol not found: {name}", "SYMBOL_NOT_FOUND")
        return keys[0]

    def snippet(self, key):
        symbol = dict(self.symbols[key])
        lines = self.records[symbol["path"]]["text"].splitlines()
        symbol["text"] = "\n".join(lines[symbol["lineStart"] - 1:symbol["lineEnd"]])
        return symbol

    def edges(self, key, direction, relation=None):
        found = []
        if direction in {"callers", "both"}:
            found.extend(self.incoming[key])
        if direction in {"callees", "both"}:
            found.extend(self.outgoing[key])
        unique = {(e["from"], e["to"], e["line"], e["type"]): e for e in found
                  if not relation or e["type"].casefold() == relation.casefold()}
        return list(unique.values())

    def path(self, start, goal, limit):
        pending = deque([(start, 0)])
        parents = {start: None}
        while pending:
            node, depth = pending.popleft()
            if node == goal:
                steps = []
                while edge := parents[node]:
                    steps.append(edge)
                    node = edge["from"]
                return list(reversed(steps))
            if depth == limit:
                continue
            for edge in self.outgoing[node]:
                if edge["to"] not in parents:
                    parents[edge["to"]] = edge
                    pending.append((edge["to"], depth + 1))
        return None

    def impact(self, paths, depth, direction, hub_threshold):
        changed = set(paths)
        targets = set().union(*(self.by_file[path] for path in changed))
        affected = set(targets)
        frontier = targets
        for _ in range(depth):
            adjacent = set()
            for key in frontier:
                for edge in self.edges(key, direction):
                    adjacent.add(edge["to"] if edge["from"] == key else edge["from"])
            frontier = adjacent - affected
            if not frontier:
                break
            affected.update(frontier)
        hubs = [self.symbols[key] for key in sorted(affected)
                if len({edge["from"] for edge in self.incoming[key]}) >= hub_threshold]
        unassessed = sorted(path for path in changed if not self.by_file[path])
        return {"changedFiles": sorted(changed), "changedSymbols": [self.symbols[key] for key in sorted(targets)],
                "affectedSymbols": [self.symbols[key] for key in sorted(affected)], "hubs": hubs,
                "unassessed": unassessed, "riskLevel": "UNKNOWN" if unassessed else "HIGH" if hubs else "MEDIUM" if affected - targets else "LOW"}

    def communities(self, min_size=1, hub_threshold=5, min_coupling=1):
        neighbors = defaultdict(set)
        for key in self.symbols:
            for edge in self.edges(key, "both"):
                other = edge["to"] if key == edge["from"] else edge["from"]
                if key != other:
                    neighbors[key].add(other)
        groups = {key: key for key in self.symbols}
        for _ in range(8):
            moved = False
            for key in sorted(groups):
                counts = defaultdict(int)
                for other in neighbors[key]:
                    counts[groups[other]] += 1
                if counts:
                    best = min(counts, key=lambda group: (-counts[group], group))
                    if best != groups[key] and counts[best] > counts.get(groups[key], 0):
                        groups[key] = best
                        moved = True
            if not moved:
                break
        members, coupling = defaultdict(list), defaultdict(set)
        hubs = []
        for key, group in groups.items():
            members[group].append(self.symbols[key])
            external = {other for other in neighbors[key] if groups[other] != group}
            if len(external) >= hub_threshold and external:
                hubs.append({**self.symbols[key], "externalNeighbors": len(external)})
            for other in external:
                coupling[tuple(sorted((group, groups[other])))].add(tuple(sorted((key, other))))
        communities = [{"id": key, "size": len(values), "members": values}
                       for key, values in members.items() if len(values) >= min_size]
        communities.sort(key=lambda item: (-item["size"], item["id"]))
        hubs.sort(key=lambda item: (-item["externalNeighbors"], item["symbolId"]))
        visible = {item["id"] for item in communities}
        couplings = [{"from": left, "to": right, "edges": len(pairs), "examples": sorted(pairs)[:3]}
                     for (left, right), pairs in coupling.items()
                     if left in visible and right in visible and len(pairs) >= min_coupling]
        couplings.sort(key=lambda item: (-item["edges"], item["from"], item["to"]))
        return communities, hubs, couplings
