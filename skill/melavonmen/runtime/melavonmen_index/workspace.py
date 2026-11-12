"""Workspace discovery, configuration, and Git evidence."""

from contextlib import contextmanager
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit


class IndexErrorWithCode(RuntimeError):
    def __init__(self, message, code="INVALID_ARGUMENT"):
        super().__init__(message)
        self.code = code


LANGUAGES = {
    **dict.fromkeys((".py", ".pyi"), "python"),
    **dict.fromkeys((".ts", ".tsx", ".mts", ".cts"), "typescript"),
    **dict.fromkeys((".js", ".jsx", ".mjs", ".cjs"), "javascript"),
    **dict.fromkeys((".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx", ".metal"), "c-family"),
    ".rs": "rust", ".go": "go", ".swift": "swift", ".kt": "kotlin", ".kts": "kotlin",
    ".java": "java", ".cs": "csharp", ".rb": "ruby", ".php": "php", ".cls": "apex",
    ".trigger": "apex", ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".zig": "zig",
    ".gd": "gdscript", ".m": "matlab", ".lua": "lua", ".sql": "sql",
    ".json": "json", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
    ".md": "markdown", ".mdx": "markdown", ".rst": "text", ".txt": "text",
    ".html": "markup", ".xml": "markup", ".svg": "markup", ".css": "text",
}
EXCLUDED = {".git", ".melavonmen", ".codebase-index", ".opencode", ".claude", ".venv", "venv",
            "node_modules", "vendor", "build", "dist", "target", "__pycache__", "coverage"}
SENSITIVE_NAMES = {".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials.json", ".netrc"}
SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".kdbx"}
MAX_FILE_BYTES = 2 * 1024 * 1024


def run_git(root, *args):
    try:
        return subprocess.run(
            ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(root), *args],
            capture_output=True, timeout=25, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def git_output(root, *args):
    result = run_git(root, *args)
    return result.stdout if result is not None and not result.returncode else None


def git_text(root, *args):
    data = git_output(root, *args)
    return os.fsdecode(data).strip() if data is not None else None


def split_paths(data):
    return [os.fsdecode(part) for part in data.split(b"\0") if part]


def project_stat(path):
    try:
        info = path.stat()
        return info.st_mtime_ns, info.st_size
    except OSError:
        return None


def project_root(explicit=None):
    root = Path(explicit or Path.cwd()).expanduser().resolve()
    if not root.is_dir():
        raise IndexErrorWithCode(f"Project directory does not exist: {root}")
    if explicit is None:
        found = git_text(root, "rev-parse", "--show-toplevel")
        if found:
            return Path(found).resolve()
    return root


def match(path, pattern):
    return fnmatch.fnmatchcase(path, pattern) or (
        pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:])
    )


def permitted(path):
    parts = PurePosixPath(path).parts
    if not parts or any(part in EXCLUDED for part in parts):
        return False
    name = parts[-1].lower()
    return (not name.startswith(".env") and name not in SENSITIVE_NAMES
            and PurePosixPath(name).suffix not in SENSITIVE_SUFFIXES
            and name not in {"package-lock.json", "cargo.lock", "pnpm-lock.yaml", "yarn.lock"})


def config_file(root):
    own = root / ".melavonmen" / "config.json"
    legacy = root / ".codebase-index" / "config.json"
    return legacy if not own.exists() and legacy.is_file() else own


def read_config(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IndexErrorWithCode(f"Cannot read configuration {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise IndexErrorWithCode(f"Expected a JSON object in {path}")
    for key in ("indexing", "search", "reranker", "customProvider", "repositoryHistory"):
        if key in data and not isinstance(data[key], dict):
            raise IndexErrorWithCode(f"{key} must be an object")
    for group in (data, data.get("indexing", {})):
        for key in ("include", "exclude", "additionalInclude", "knowledgeBases"):
            if key in group and (not isinstance(group[key], list)
                                 or any(not isinstance(value, str) for value in group[key])):
                raise IndexErrorWithCode(f"{key} must be a list of strings")
    return data


def atomic_json(path, obj):
    atomic_write(path, (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode())


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        name = Path(tmp.name)
        try:
            tmp.write(data)
            tmp.close()
            name.replace(path)
        finally:
            name.unlink(missing_ok=True)


class Workspace:
    def __init__(self, root, override=None):
        self.root = root
        self.override = Path(override).expanduser().resolve() if override else None

    @property
    def settings(self):
        return read_config(self.override or config_file(self.root))

    @property
    def branch(self):
        named = git_text(self.root, "symbolic-ref", "--quiet", "--short", "HEAD")
        head = git_text(self.root, "rev-parse", "--verify", "HEAD")
        return named or (f"detached:{head}" if head else "default")

    @property
    def head(self):
        return git_text(self.root, "rev-parse", "--verify", "HEAD")

    def knowledge_roots(self, settings):
        seen = set()
        for item in settings.get("knowledgeBases", []):
            if not isinstance(item, str):
                raise IndexErrorWithCode("knowledgeBases must contain directory paths")
            directory = (self.root / Path(item).expanduser()).resolve()
            if directory == self.root or self.root.is_relative_to(directory):
                raise IndexErrorWithCode("Select a knowledge-base directory outside the project root or inside it")
            if directory not in seen:
                seen.add(directory)
                yield directory

    def _names(self, root, settings):
        git_scope = git_text(root, "rev-parse", "--is-inside-work-tree") == "true"
        if git_scope:
            args = ["ls-files", "-z", "--cached", "--others"]
            if not settings.get("includeIgnored"):
                args.append("--exclude-standard")
            data = git_output(root, *args, "--")
            if data is None:
                raise IndexErrorWithCode("Git could not list files", "GIT_ERROR")
            yield from split_paths(data)
            return
        for directory, dirs, files in os.walk(root):
            folder = Path(directory).relative_to(root)
            dirs[:] = sorted(d for d in dirs if permitted((folder / d).as_posix()))
            yield from ((folder / f).as_posix() for f in files)

    def source_files(self, settings):
        indexing = settings.get("indexing", {})
        includes = settings.get("include", indexing.get("include", []))
        extra = settings.get("additionalInclude", indexing.get("additionalInclude", []))
        excludes = settings.get("exclude", indexing.get("exclude", []))
        max_bytes = indexing.get("maxFileSize", MAX_FILE_BYTES)
        seen = set()
        for root in (self.root, *self.knowledge_roots(settings)):
            for name in sorted(set(self._names(root, settings))):
                if not permitted(name) or any(match(name, pat) for pat in excludes):
                    continue
                candidate = root / name
                suffix = candidate.suffix.lower()
                explicitly_included = any(match(name, pat) for pat in extra)
                if not explicitly_included and (not any(match(name, pat) for pat in includes)
                    if includes else suffix not in LANGUAGES):
                    continue
                try:
                    path = candidate.resolve(strict=True)
                    if candidate != path or path in seen or not path.is_relative_to(root) or not path.is_file():
                        continue
                    if path.stat().st_size > max_bytes:
                        continue
                except OSError:
                    continue
                seen.add(path)
                key = path.relative_to(self.root).as_posix() if path.is_relative_to(self.root) else str(path)
                yield key, path, LANGUAGES.get(suffix, "text")

    def changed(self, base=None, end=None):
        if base:
            ref = self.commit(base)
            args = ["diff", "--name-only", "-z", "--no-renames", ref]
            if end:
                args.append(self.commit(end))
            data = git_output(self.root, *args, "--")
            if data is None:
                raise IndexErrorWithCode("Unable to read Git diff", "GIT_ERROR")
            return sorted(set(split_paths(data)))
        data = git_output(self.root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames", "--")
        if data is None:
            raise IndexErrorWithCode("Working-tree analysis requires a Git checkout", "GIT_ERROR")
        return sorted({entry[3:] for entry in split_paths(data)})

    def commit(self, revision):
        sha = git_text(self.root, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}")
        if not sha:
            raise IndexErrorWithCode(f"Git revision unavailable: {revision}", "REF_NOT_FOUND")
        return sha

    def base_ref(self):
        default = git_text(self.root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
        for name in (default, "origin/main", "main", "origin/master", "master"):
            if name and git_text(self.root, "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}"):
                return name
        return "HEAD"

    def merge_base(self, left, right):
        base = git_text(self.root, "merge-base", self.commit(left), self.commit(right))
        if not base:
            raise IndexErrorWithCode("No merge base for the selected revisions", "REF_NOT_FOUND")
        return base

    def remote_repository(self):
        url = git_text(self.root, "remote", "get-url", "origin") or ""
        ssh = re.fullmatch(r"git@([^:]+):(.+)", url)
        if ssh:
            return f"{ssh[1]}/{ssh[2].removesuffix('.git')}"
        parts = urlsplit(url)
        if parts.hostname and parts.path.count("/") == 2:
            return f"{parts.hostname}/{parts.path.strip('/').removesuffix('.git')}"
        raise IndexErrorWithCode("No GitHub origin found. Specify the repository explicitly.")


@contextmanager
def operation_connection(connection):
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
