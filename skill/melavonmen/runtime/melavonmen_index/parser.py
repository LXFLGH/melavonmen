"""Extract source ranges and conservative static relationships."""

import ast
from bisect import bisect_right
import re


NAME = r"[A-Za-z_$][\w$]*"
CONTROL = {"if", "for", "while", "switch", "catch", "with", "return", "throw", "sizeof",
           "typeof", "await", "match", "assert", "super", "print", "defined"}
TOKEN = re.compile(r"//[^\n]*|/\*[\s\S]*?\*/|\#[^\n]*|--\[\[[\s\S]*?\]\]|"
                   r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`")
CALL = re.compile(rf"(?<![\w$])({NAME}(?:\s*(?:::|\.)\s*{NAME})*)\s*\(")
CONTAINERS = re.compile(rf"\b(class|interface|enum|struct|trait|object|namespace|module)\s+({NAME})")
DECLARATION = re.compile(
    rf"\b(?:function\s*\*?|fn|func(?:\s*\([^\n)]*\))?|fun|def|sub)\s+({NAME})\s*(?=[(<])"
)
ARROW = re.compile(rf"\b(?:const|let|var)\s+({NAME})(?:\s*:[^=\n]+)?\s*=\s*(?:async\s+)?"
                   rf"(?:\([^\n]*?\)|{NAME})\s*(?::[^=\n]+)?=>")
METHOD = re.compile(rf"(?m)(?:^|[;{{}}])\s*(?:(?:{NAME}(?:[<>,.\[\]:*&?]+)?|~)\s+)*"
                    rf"({NAME})\s*\([^;{{}}]*\)\s*(?:(?:const|throws\s+[\w., ]+|noexcept|override)\s*)*"
                    r"(?::[^\n{}]+)?\s*\{")
TYPESCRIPT_IMPORT = re.compile(
    r"""\bimport\s+([\s\S]*?)\s+from\s*['"]([^'"\n]+)['"]|\b(?:const|let|var)\s+(\w+)\s*=\s*require\(['"]([^'"\n]+)['"]\)"""
)
REEXPORT = re.compile(r"""\bexport\s+(\*|\{[^}]+\})\s+from\s*['"]([^'"\n]+)['"]""")


def item(name, qualified, kind, start, end):
    return {"name": name, "qualifiedName": qualified, "kind": kind, "lineStart": start, "lineEnd": end}


def python_source(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], [], [], ["Python syntax could not be parsed"]
    symbols, calls, imports = [], [], []

    def scope_bindings(node):
        local = set()
        declared = set()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            local.update(arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg) if arg)
        def visit(body):
            if isinstance(body, ast.Name) and isinstance(body.ctx, ast.Store):
                local.add(body.id)
            if isinstance(body, (ast.Global, ast.Nonlocal)):
                declared.update(body.names)
            for child in ast.iter_child_nodes(body):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    continue
                visit(child)
        for statement in node.body:
            visit(statement)
        return local - declared

    def walk(node, scope="", caller=None, bindings=frozenset()):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            scope = f"{scope}.{node.name}" if scope else node.name
            caller = node.lineno
            bindings = bindings | scope_bindings(node)
            symbol = item(node.name, scope, kind, node.lineno, node.end_lineno)
            if kind == "function":
                returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                symbol["signature"] = f"{prefix} {node.name}({ast.unparse(node.args)}){returns}"
            else:
                symbol["signature"] = f"class {node.name}({', '.join(ast.unparse(base) for base in node.bases)})"
            symbols.append(symbol)
            if kind == "class":
                for base in node.bases:
                    calls.append((caller, scope, ast.unparse(base), node.lineno, "Inherits"))
        if isinstance(node, ast.Call) and caller is not None:
            if isinstance(node.func, (ast.Name, ast.Attribute)):
                target = ast.unparse(node.func)
                first = target.split(".", 1)[0]
                if first in bindings and first not in {"self", "cls"}:
                    target = f"<local>.{target}"
                calls.append((caller, scope, target, node.lineno, "Call"))
        if isinstance(node, ast.Import):
            imports.extend((alias.asname or alias.name.split(".")[0], alias.name, "*", scope) for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            imports.extend((alias.asname or alias.name, module, alias.name, scope) for alias in node.names)
        for child in ast.iter_child_nodes(node):
            walk(child, scope, caller, bindings)

    walk(tree)
    return symbols, calls, imports, []


def mask(text):
    return TOKEN.sub(lambda match: re.sub(r"[^\n]", " ", match.group()), text)


def brace_ranges(masked):
    opens, ends = [], {}
    for match in re.finditer(r"[{}]", masked):
        if match.group() == "{":
            opens.append(match.start())
        elif opens:
            ends[opens.pop()] = match.start()
    return ends


def js_imports(text):
    imports = []
    masked = mask(text)
    for match in TYPESCRIPT_IMPORT.finditer(text):
        if not masked[match.start():match.start() + 3].strip():
            continue
        binding, module, common, common_module = match.groups()
        if common:
            imports.append((common, common_module, "*"))
            continue
        if binding.startswith("type "):
            continue
        namespace = re.search(r"\*\s+as\s+(\w+)", binding)
        if namespace:
            imports.append((namespace[1], module, "*"))
        named = re.search(r"\{([^}]+)\}", binding)
        if named:
            for element in named[1].split(","):
                pair = element.strip().split()
                if len(pair) == 1:
                    imports.append((pair[0], module, pair[0]))
                elif len(pair) == 3 and pair[1] == "as":
                    imports.append((pair[2], module, pair[0]))
        default = re.match(rf"^\s*({NAME})(?:\s*,|\s*$)", binding)
        if default:
            imports.append((default[1], module, "default"))
    return imports


def js_reexports(text):
    masked = mask(text)
    for match in REEXPORT.finditer(text):
        if not masked[match.start():match.start() + 6].strip():
            continue
        bindings, module = match.groups()
        if bindings == "*":
            yield "*", module, "*"
            continue
        for value in bindings[1:-1].split(","):
            parts = value.strip().split()
            if len(parts) == 1:
                yield parts[0], module, parts[0]
            elif len(parts) == 3 and parts[1] == "as":
                yield parts[2], module, parts[0]


def statement_symbols(source, language):
    patterns = {
        "ruby": rf"^\s*(def|class|module)\s+({NAME})",
        "shell": rf"^\s*(?:(function)\s+)?({NAME})\s*\(\s*\)\s*\{{",
        "gdscript": rf"^\s*(?:static\s+)?(func|class|class_name|signal)\s+({NAME})",
        "matlab": rf"^\s*(function|classdef)\s+(?:\[[^\]]+\]\s*=\s*|\w+\s*=\s*)?({NAME})",
        "lua": rf"^\s*(?:local\s+)?(function)\s+({NAME}(?:[.:]{NAME})*)",
        "markdown": r"^(#{1,6})\s+(.+?)\s*#*\s*$",
    }
    matches = list(re.finditer(patterns[language], source, re.MULTILINE))
    lines = source.splitlines()
    symbols, calls = [], []
    for i, match in enumerate(matches):
        kind, name = match.groups()
        start = source.count("\n", 0, match.start(2)) + 1
        end = source.count("\n", 0, matches[i + 1].start(2)) if i + 1 < len(matches) else len(lines)
        kind = "heading" if language == "markdown" else "class" if kind in {"class", "classdef", "class_name", "module"} else "function"
        symbols.append(item(name, name, kind, start, max(start, end)))
        if kind == "function":
            for n in range(start + 1, end + 1):
                for call in CALL.finditer(mask(lines[n - 1])):
                    if call[1] not in CONTROL:
                        calls.append((start, name, call[1], n, "Call"))
    return symbols, calls, [], []


def brace_source(source, language):
    masked = mask(source)
    offsets = [-1] + [match.start() for match in re.finditer("\n", source)]
    line = lambda pos: bisect_right(offsets, pos - 1)
    ends = brace_ranges(masked)
    candidates, names = [], set()

    def add(match, name_group, kind, brace=None):
        name, pos = match[name_group], match.start(name_group)
        if name in CONTROL or pos in names:
            return
        if brace is None:
            boundary = re.search(r"[;{}]|\n\s*\n", masked[match.end():match.end() + 2048])
            if boundary and boundary[0] == "{":
                brace = match.end() + boundary.start()
        end = ends.get(brace, pos)
        candidates.append((pos, brace, end, name, kind))
        names.add(pos)

    for match in CONTAINERS.finditer(masked):
        add(match, 2, match[1])
    for match in DECLARATION.finditer(masked):
        add(match, 1, "function")
    for match in ARROW.finditer(masked):
        add(match, 1, "function")
    for match in METHOD.finditer(masked):
        name_pos = match.start(1)
        if any(pos >= match.start() and pos < name_pos for pos in names):
            continue
        add(match, 1, "function", match.end() - 1)

    symbols, scopes, calls, bindings = [], [], [], {}
    for pos, brace, end, name, kind in sorted(candidates):
        parents = [s for begin, stop, s in scopes if begin < pos < stop]
        qualified = f"{parents[-1]['qualifiedName']}.{name}" if parents else name
        symbol = item(name, qualified, kind, line(pos), line(end))
        if brace is not None:
            symbol["signature"] = " ".join(source[pos:brace].split())
        symbols.append(symbol)
        if brace is not None and end > brace:
            scopes.append((brace, end, symbol))
            if kind == "function":
                header = masked[pos:brace]
                parameters = re.search(r"\(([^()]*)\)", header)
                local = set(re.findall(rf"\b(?:const|let|var)\s+({NAME})", masked[brace:end]))
                if parameters:
                    local.update(re.findall(rf"(?:^|,)\s*({NAME})", parameters[1]))
                bindings[(symbol["lineStart"], qualified)] = local
        if kind != "function" and brace is not None:
            header = masked[pos:brace]
            for relation in re.finditer(r"\b(extends|implements)\s+([\w$., ]+?)(?=\bimplements\b|$)", header):
                for base in relation[2].split(","):
                    calls.append((line(pos), qualified, base.strip(), line(pos),
                                  "Inherits" if relation[1] == "extends" else "Implements"))
    for call in CALL.finditer(masked):
        if call.start(1) in names or call[1] in CONTROL:
            continue
        owners = [s for begin, stop, s in scopes if begin < call.start() < stop and s["kind"] == "function"]
        if owners:
            owner = owners[-1]
            target = re.sub(r"\s+", "", call[1]).replace("::", ".")
            first = target.split(".", 1)[0]
            if first in bindings[(owner["lineStart"], owner["qualifiedName"])]:
                target = f"<local>.{target}"
            calls.append((owner["lineStart"], owner["qualifiedName"], target, line(call.start()), "Call"))
    imports = js_imports(source) if language in {"javascript", "typescript"} else []
    return symbols, calls, imports, []


def extract(source, language):
    if language == "python":
        symbols, calls, imports, warnings = python_source(source)
    elif language in {"ruby", "shell", "gdscript", "matlab", "lua", "markdown"}:
        symbols, calls, imports, warnings = statement_symbols(source, language)
    elif language in {"text", "json", "toml", "yaml", "markup", "sql"}:
        symbols, calls, imports, warnings = [], [], [], []
    else:
        symbols, calls, imports, warnings = brace_source(source, language)
    return symbols, calls, imports, warnings


def chunks(source, symbols):
    lines = source.splitlines()
    if not lines:
        return
    starts = sorted({1, len(lines) + 1, *(s["lineStart"] for s in symbols)})
    by_start = {}
    for symbol in symbols:
        by_start.setdefault(symbol["lineStart"], symbol)
    for start, stop in zip(starts, starts[1:]):
        symbol = by_start.get(start)
        for first in range(start, stop, 64):
            last = min(first + 63, stop - 1)
            body = "\n".join(lines[first - 1:last])
            if body.strip():
                yield first, last, symbol["kind"] if symbol else "text", symbol["name"] if symbol else "", body
