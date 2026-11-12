"""Start the pinned index engine from a lockfile-keyed local cache."""

import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parent
ENTRYPOINTS = {"mcp": "cli.js", "cli": "cbi.js"}


def find_node():
    configured = os.environ.get("MELAVONMEN_NODE")
    if configured:
        node = shutil.which(configured)
        if not node:
            raise RuntimeError("MELAVONMEN_NODE does not point to an executable Node.js")
        return Path(node).absolute()

    candidates = []
    if node := shutil.which("node"):
        candidates.append(Path(node))
    if codex := shutil.which("codex"):
        candidates.append(Path(codex).resolve().parent / "cua_node" / "bin" / "node")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.absolute()
    raise RuntimeError("Install Node.js 22.13+ or set MELAVONMEN_NODE")


def install_runtime(env, destination):
    npm = shutil.which("npm", path=env["PATH"])
    corepack = shutil.which("corepack", path=env["PATH"])
    if npm:
        installer = [npm]
    elif corepack:
        installer = [corepack, "npm@11.6.2"]
    else:
        raise RuntimeError("npm or Corepack is required to install the index engine")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".install-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "runtime"
        stage.mkdir()
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(ROOT / name, stage / name)
        subprocess.run(
            [*installer, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=stage, env=env, stdin=subprocess.DEVNULL, stdout=sys.stderr, check=True,
        )
        for entrypoint in ENTRYPOINTS.values():
            if not engine_path(stage, entrypoint).is_file():
                raise RuntimeError(f"Installed package is missing {entrypoint}")
        try:
            stage.rename(destination)
        except OSError:
            if not all(engine_path(destination, entrypoint).is_file()
                       for entrypoint in ENTRYPOINTS.values()):
                raise


def engine_path(root, entrypoint):
    return root / "node_modules" / "open-codebase-index" / "dist" / entrypoint


def main(args):
    mode = "cli" if args[:1] == ["--cli"] else "mcp"
    if mode == "cli":
        args = args[1:]

    node = find_node()
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(node.parent), env.get("PATH", "")))
    env["COREPACK_ENABLE_AUTO_PIN"] = "0"

    lock_hash = hashlib.sha256((ROOT / "package-lock.json").read_bytes()).hexdigest()
    cache = Path(env.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    target = cache / "melavonmen" / f"{platform.system()}-{platform.machine()}-{lock_hash}"
    entrypoint = engine_path(target, ENTRYPOINTS[mode])
    if not entrypoint.is_file():
        install_runtime(env, target)
    if not any(arg == "--host" or arg.startswith("--host=") for arg in args):
        args = [*args, "--host", "codex"] if args or mode == "mcp" else ["--help"]
    os.execve(node, [str(node), str(entrypoint), *args], env)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Melavonmen index: {exc}", file=sys.stderr)
        sys.exit(1)
