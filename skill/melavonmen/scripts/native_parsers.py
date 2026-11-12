"""Language adapters for generated code facts.

Python declarations use the stdlib AST. Other programming languages require a
real Tree-sitter grammar (optional dependency). Godot resource files are parsed
as their documented line-oriented resource format, never as executable code.
"""
from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path

PARSER_VERSION = "native-4"
LANGUAGES = {
    ".py": "python", ".gd": "gdscript", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript",
    ".tsx": "tsx", ".cs": "csharp", ".c": "c", ".h": "cpp",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".hh": "cpp", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".tscn": "godot_resource", ".tres": "godot_resource",
}
DECL_NODES = {
    "function_definition": "function", "function_declaration": "function",
    "function": "function", "method_definition": "method",
    "method_declaration": "method", "constructor_declaration": "constructor",
    "class_definition": "class", "class_declaration": "class",
    "interface_declaration": "interface", "struct_specifier": "struct",
    "struct_declaration": "struct", "enum_declaration": "enum",
    "enum_specifier": "enum", "function_item": "function",
    "property_declaration": "property", "field_declaration": "field",
    "signal_statement": "signal", "signal_declaration": "signal",
}
IMPORT_NODES = {
    "import_statement", "import_declaration", "using_directive",
    "preproc_include", "import_from_statement", "import_directive",
}
CALL_NODES = {"call", "call_expression", "invocation_expression"}

def language_for(path: str) -> str | None:
    return "godot_project" if Path(path).name == "project.godot" else LANGUAGES.get(Path(path).suffix.lower())

def evidence(path, sha, revision, method, status, start, end=None):
    return {"source_path": path, "line_start": start, "line_end": end or start,
            "source_sha256": sha, "revision": revision,
            "extraction_method": method, "verification_status": status}

def declaration(output, path, sha, revision, method, status,
                name, qualified, kind, signature, start, end, parameters=None,
                return_type=None, **extra):
    if not name:
        return
    output["symbols"].append({
        **evidence(path, sha, revision, method, status, start, end),
        "name": name, "qualified_name": qualified, "kind": kind,
        "signature": signature[:1200], "parameters": parameters or [],
        "return_type": return_type, "module": str(Path(path).parent),
        **extra,
    })

def relation(output, path, sha, revision, method, kind, target,
             line, status="possible", target_file=None, **extra):
    output["edges"].append({
        **evidence(path, sha, revision, method, status, line),
        "kind": kind, "target_name": target[:600],
        "target_file": target_file, "target_symbol": None, **extra,
    })

def parse_python(text, path, sha, revision, out):
    tree = ast.parse(text, filename=path)
    def label(n):
        try:
            return ast.unparse(n)
        except Exception:
            return "unknown"
    def parameters(args):
        entries = []
        positional = [*args.posonlyargs, *args.args]
        first_default = len(positional) - len(args.defaults)
        for i, arg in enumerate(positional):
            default = args.defaults[i - first_default] if i >= first_default else None
            entries.append({"name": arg.arg,
                            "type": label(arg.annotation) if arg.annotation else "unknown",
                            "default": label(default) if default is not None else None})
        if args.vararg:
            entries.append({"name": "*" + args.vararg.arg,
                            "type": label(args.vararg.annotation) if args.vararg.annotation else "unknown",
                            "default": None})
        for arg, default in zip(args.kwonlyargs, args.kw_defaults):
            entries.append({"name": arg.arg,
                            "type": label(arg.annotation) if arg.annotation else "unknown",
                            "default": label(default) if default is not None else None})
        if args.kwarg:
            entries.append({"name": "**" + args.kwarg.arg,
                            "type": label(args.kwarg.annotation) if args.kwarg.annotation else "unknown",
                            "default": None})
        return entries
    def walk(body, prefix=""):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = prefix + node.name
                if isinstance(node, ast.ClassDef):
                    signature = "class " + node.name
                    kind = "class"
                    for base in node.bases:
                        relation(out, path, sha, revision, "python_ast", "inherits",
                                 label(base), node.lineno)
                else:
                    kind = "method" if prefix else "function"
                    intro = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                    signature = intro + " " + node.name + "(" + label(node.args) + ")"
                    signature += (" -> " + label(node.returns)) if node.returns else ""
                declaration(out, path, sha, revision, "python_ast", "verified",
                            node.name, qualified, kind, signature,
                            node.lineno, node.end_lineno,
                            parameters=None if isinstance(node, ast.ClassDef) else parameters(node.args),
                            return_type=(label(node.returns) if not isinstance(node, ast.ClassDef)
                                         and node.returns else "unknown"))
                walk(node.body, qualified + ".")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [x.name for x in node.names]
                module = node.module or "" if isinstance(node, ast.ImportFrom) else ""
                for name in names:
                    relation(out, path, sha, revision, "python_ast",
                             "imports", (module + "." + name).strip("."), node.lineno)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        declaration(out, path, sha, revision, "python_ast",
                                    "verified", target.id, prefix + target.id,
                                    "field" if prefix else "variable",
                                    text.splitlines()[node.lineno - 1].strip(),
                                    node.lineno, node.end_lineno)
    walk(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            relation(out, path, sha, revision, "python_ast",
                     "calls", label(node.func), node.lineno)
        elif isinstance(node, (ast.Name, ast.Attribute)):
            if isinstance(node.ctx, ast.Store):
                kind = "writes"
            elif isinstance(node.ctx, ast.Load):
                kind = "reads"
            else:
                continue
            # Reads/writes are locations, not proof of a globally resolved symbol.
            if isinstance(node, ast.Name):
                relation(out, path, sha, revision, "python_ast", kind, node.id,
                         node.lineno)
    out["depth"] = "deep"

def _parser_for(language):
    try:
        from tree_sitter_language_pack import get_language
        from tree_sitter import Parser
        return Parser(get_language(language))
    except Exception as exc:
        return str(exc)

def parse_tree_sitter(text, path, sha, revision, language, out):
    parser = _parser_for(language)
    if isinstance(parser, str):
        out["warnings"].append("Tree-sitter parser unavailable for " + language + ": " + parser)
        return
    raw = text.encode("utf-8")
    tree = parser.parse(raw)
    if tree is None:
        out["warnings"].append("parser returned no syntax tree")
        return
    if tree.root_node.has_error:
        out["warnings"].append("syntax tree contains ERROR nodes; related declarations unverified")
    status = "unverified" if tree.root_node.has_error else "verified"
    def data(node):
        return raw[node.start_byte:node.end_byte].decode("utf-8", "replace")
    def field(node, name):
        return node.child_by_field_name(name)
    def walk(node, prefix="", depth=0):
        if depth > 512:
            out["warnings"].append("AST traversal depth capped")
            return
        kind = DECL_NODES.get(node.type)
        new_prefix = prefix
        if kind:
            name_node = field(node, "name") or field(node, "declarator")
            if name_node is None:
                name_node = next((c for c in node.named_children
                                  if c.type in {"identifier", "type_identifier", "name",
                                                "property_identifier"}), None)
            name = data(name_node).strip() if name_node is not None else ""
            if name and len(name) <= 256 and "\n" not in name:
                qualified = prefix + name
                first = data(node).split("{", 1)[0].split("\n", 1)[0].strip()
                parameter_nodes = field(node, "parameters")
                parameters = []
                if parameter_nodes:
                    for item in parameter_nodes.named_children:
                        pname = field(item, "name") or field(item, "pattern")
                        ptype = field(item, "type")
                        default = field(item, "value") or field(item, "default_value")
                        parameters.append({
                            "name": data(pname) if pname else data(item).split(":", 1)[0][:128],
                            "type": data(ptype) if ptype else "unknown",
                            "default": data(default) if default else None})
                result_type = field(node, "return_type") or field(node, "type")
                declaration(out, path, sha, revision, "tree_sitter", status,
                            name, qualified, kind, first,
                            node.start_point.row + 1, node.end_point.row + 1,
                            parameters=parameters,
                            return_type=data(result_type) if result_type else "unknown")
                if kind in {"class", "interface", "struct"}:
                    new_prefix = qualified + "."
        if node.type in IMPORT_NODES:
            value = data(node)
            source = re.search(r'\bfrom\s*["\x27]([^"\x27]+)', value)
            if not source:
                source = re.search(r'[#]include\s*[<"]([^>"]+)', value)
            if not source:
                source = re.search(r'^\s*(?:using|import)\s+([\w.]+)\s*;', value)
            target = source.group(1) if source else value.strip()
            relation(out, path, sha, revision, "tree_sitter", "imports",
                     target, node.start_point.row + 1,
                     statement=value.strip()[:400])
        if node.type in CALL_NODES:
            fn = field(node, "function") or field(node, "name")
            if fn is not None:
                relation(out, path, sha, revision, "tree_sitter", "calls",
                         data(fn), node.start_point.row + 1)
        if node.type in {"base_class_clause", "base_list", "superclasses",
                         "base_type", "base_class"}:
            relation(out, path, sha, revision, "tree_sitter", "inherits",
                     data(node), node.start_point.row + 1)
        if node.type in {"implements_clause", "interface_list"}:
            relation(out, path, sha, revision, "tree_sitter", "implements",
                     data(node), node.start_point.row + 1)
        if node.type in {"export_statement", "export_declaration"}:
            relation(out, path, sha, revision, "tree_sitter", "exports",
                     data(node).split("\n", 1)[0][:400], node.start_point.row + 1)
        if node.type in {"identifier", "property_identifier", "type_identifier"}:
            if len(out["edges"]) < 3000:
                relation(out, path, sha, revision, "tree_sitter", "references",
                         data(node), node.start_point.row + 1, status="possible")
        for child in node.named_children:
            walk(child, new_prefix, depth + 1)
    walk(tree.root_node)
    out["depth"] = "deep"

def parse_config(text, path, sha, revision, lang, out):
    if lang == "json":
        obj = json.loads(text)
    elif lang == "toml":
        obj = tomllib.loads(text)
    else:
        try:
            import yaml
        except ImportError:
            out["warnings"].append("PyYAML unavailable: YAML structure not parsed")
            return
        obj = yaml.safe_load(text)
    def visit(value, prefix="", depth=0):
        if depth > 32 or len(out["symbols"]) >= 3000:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                name = str(key)
                q = (prefix + "." + name).strip(".")
                # Use a deterministic line locator; repeated keys are not certified unique.
                m = re.search(r'(?m)^\s*["\x27]?' + re.escape(name) +
                              r'["\x27]?\s*[:=]', text)
                line = text.count("\n", 0, m.start()) + 1 if m else 1
                declaration(out, path, sha, revision, lang + "_parser",
                            "possible" if not m else "verified",
                            name, q, "config_key", name, line, line)
                visit(item, q, depth + 1)
        elif isinstance(value, list):
            for item in value[:100]:
                visit(item, prefix, depth + 1)
    visit(obj)
    out["depth"] = "deep"

RESOURCE = re.compile(r'\[([A-Za-z_]+)([^\]]*)\]')
KV = re.compile(r'(\w+)\s*=\s*"((?:\\.|[^"\\])*)"')
PATH = re.compile(r'\b(?:preload|load|ResourceLoader\.load)\(\s*["\x27]([^"\x27]+)["\x27]')
NODE_PATH = re.compile(r'\b(?:get_node|NodePath)\(\s*["\x27]([^"\x27]+)["\x27]')
CLASS = re.compile(r'^\s*class_name\s+([A-Za-z_]\w*)')
SIGNAL = re.compile(r'^\s*signal\s+([A-Za-z_]\w*)')
EXPORT = re.compile(r'^\s*@export(?:_[a-z_]+)?\s+var\s+([A-Za-z_]\w*)')
ONREADY = re.compile(r'^\s*@onready\s+var\s+([A-Za-z_]\w*)')
GDEXTENDS = re.compile(r'^\s*extends\s+([A-Za-z_][\w.]*)')

def parse_godot(text, path, sha, revision, lang, out):
    resources = {}
    scene_root = None
    current_node = None
    for line, value in enumerate(text.splitlines(), 1):
        if lang == "gdscript":
            for regex, kind in ((CLASS, "class"), (SIGNAL, "signal"),
                                (EXPORT, "export"), (ONREADY, "onready")):
                m = regex.match(value)
                if m:
                    declaration(out, path, sha, revision, "godot_lexical",
                                "possible", m.group(1), m.group(1), kind,
                                value.strip(), line, line)
            m = GDEXTENDS.match(value)
            if m:
                relation(out, path, sha, revision, "godot_lexical",
                         "inherits", m.group(1), line)
            for regex, kind in ((PATH, "resource_reference"),
                                (NODE_PATH, "references")):
                for m in regex.finditer(value):
                    target = m.group(1)
                    relation(out, path, sha, revision, "godot_literal",
                             kind, target, line, target_file=target[6:] if
                             target.startswith("res://") else None)
            for m in re.finditer(r'\b([A-Za-z_]\w*)\.connect\s*\(', value):
                relation(out, path, sha, revision, "godot_lexical",
                         "connect", m.group(1), line, status="possible",
                         expression=value.strip())
        else:
            m = RESOURCE.match(value.strip())
            if m:
                section, attrs = m.groups()
                attrs = dict(KV.findall(attrs))
                if section == "ext_resource":
                    identifier = attrs.get("id", "")
                    target = attrs.get("path", "")
                    if identifier:
                        resources[identifier] = target
                    relation(out, path, sha, revision, "godot_resource",
                             "resource_reference", target or attrs.get("uid", ""),
                             line, status="verified" if target else "possible",
                             target_file=target[6:] if target.startswith("res://") else None,
                             uid=attrs.get("uid"))
                elif section == "node":
                    name = attrs.get("name", "Node")
                    parent = attrs.get("parent")
                    if scene_root is None:
                        scene_root = name
                    if parent is None:
                        qualified = name
                    elif parent == ".":
                        qualified = scene_root + "/" + name
                    else:
                        qualified = scene_root + "/" + parent.strip("/") + "/" + name
                    current_node = qualified
                    declaration(out, path, sha, revision, "godot_resource",
                                "verified", name, qualified, "scene_node",
                                value.strip(), line, line,
                                parent_path=parent, node_type=attrs.get("type"),
                                scene_path=qualified)
                    instance = re.search(r'\binstance\s*=\s*ExtResource\("([^"]+)"\)', value)
                    if instance:
                        identifier = instance.group(1)
                        target = resources.get(identifier, identifier)
                        relation(out, path, sha, revision, "godot_resource",
                                 "resource_reference", target, line,
                                 target_file=target[6:] if target.startswith("res://") else None,
                                 scene_node=qualified, scene_instance=True)
                elif section == "resource":
                    current_node = None
                elif section == "connection":
                    relation(out, path, sha, revision, "godot_resource",
                             "connect", attrs.get("signal", ""), line,
                             status="verified", signal=attrs.get("signal"),
                             from_node=attrs.get("from"), to_node=attrs.get("to"),
                             handler_method=attrs.get("method"))
            # Properties in scene/resource nodes may override @export fields.
            # This is a possible write until scene/script ownership is resolved.
            prop = re.match(r'^\s*([A-Za-z_]\w*)\s*=\s*(.+)$', value)
            if prop and prop.group(1) not in {"script", "load_steps", "format"}:
                relation(out, path, sha, revision, "godot_resource",
                         "writes", prop.group(1), line, status="possible",
                         expression=prop.group(2)[:250],
                         scene_node=current_node)
            for m in re.finditer(r'ExtResource\("([^"]+)"\)', value):
                relation(out, path, sha, revision, "godot_resource",
                         "resource_reference", resources.get(m.group(1), m.group(1)),
                         line, status="possible", resource_id=m.group(1),
                         scene_node=current_node)
            for m in re.finditer(r'\b(?:res://)[^"\x27\s,)]+', value):
                target = m.group(0)
                relation(out, path, sha, revision, "godot_resource",
                         "resource_reference", target, line, "possible",
                         target_file=target[6:])
            if lang == "godot_project":
                m = re.match(r'^\s*([A-Za-z_]\w*)\s*=\s*"\*?(res://[^"]+)"', value)
                if m:
                    relation(out, path, sha, revision, "godot_project",
                             "resource_reference", m.group(2), line,
                             status="verified", target_file=m.group(2)[6:],
                             autoload=m.group(1))
    if out["depth"] != "deep":
        out["depth"] = "resource"

def parse_file(path, source_path, language, sha, revision):
    out = {"symbols": [], "edges": [], "depth": "indexed", "warnings": []}
    try:
        text = path.read_text(encoding="utf-8-sig")
        if language == "python":
            parse_python(text, source_path, sha, revision, out)
        elif language in {"json", "yaml", "toml"}:
            parse_config(text, source_path, sha, revision, language, out)
        elif language in {"gdscript", "javascript", "typescript", "tsx",
                          "csharp", "c", "cpp"}:
            parse_tree_sitter(text, source_path, sha, revision, language, out)
        if language in {"gdscript", "godot_resource", "godot_project"}:
            parse_godot(text, source_path, sha, revision, language, out)
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError) as exc:
        out["warnings"].append(type(exc).__name__ + ": " + str(exc)[:300])
    return out
