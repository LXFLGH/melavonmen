"""Build a local Codex plugin from the maintained skill and runtime files."""

import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DESTINATION = BUILD / "melavonmen"
FILES = (
    ".codex-plugin/plugin.json",
    "README.md", "runtime/launch.py", "runtime/package.json", "runtime/package-lock.json",
)


def package():
    BUILD.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix=".package-", dir=BUILD) as temporary:
        stage = Path(temporary) / "plugin"
        for relative in FILES:
            path = stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, path)
        # Codex's native manifest inherits the chat cwd. Its stdio arguments
        # are literal, so resolve the launcher from the local marketplace.
        mcp = {"mcpServers": {"codebase-index": {
            "command": "python3",
            "args": [str(DESTINATION / "runtime" / "launch.py")],
            "startup_timeout_sec": 120,
            "tool_timeout_sec": 900,
        }}}
        (stage / ".mcp.json").write_text(json.dumps(mcp, indent=2) + "\n", encoding="utf-8")
        skill = stage / "skills" / "melavonmen"
        skill.mkdir(parents=True)
        for name in ("SKILL.md", "README.md"):
            shutil.copyfile(ROOT / name, skill / name)
        for name in ("references", "scripts", "templates"):
            shutil.copytree(ROOT / name, skill / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        backup = Path(temporary) / "previous"
        if DESTINATION.exists():
            DESTINATION.rename(backup)
        try:
            stage.rename(DESTINATION)
        except OSError:
            if backup.exists():
                backup.rename(DESTINATION)
            raise
    print(DESTINATION)


if __name__ == "__main__":
    package()
