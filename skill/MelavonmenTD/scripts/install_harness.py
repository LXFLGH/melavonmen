#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install_harness.py — 跨 Agent Harness 自动配置与安装助手

支持不同 agent harness 的 MCP 服务注入与技能挂载：
  1. Antigravity (反重力): ~/.gemini/config/mcp_config.json
  2. Claude Desktop/Code: claude_desktop_config.json / .claude/
  3. Cursor:              .cursor/mcp.json / .cursorrules
  4. Codex:               ~/.codex/config.toml
  5. Windsurf:            ~/.codeium/windsurf/mcp_config.json
  6. Cline / Roo-Code:    cline_mcp_settings.json

用法：
    python install_harness.py antigravity            # 配置反重力全局 MCP
    python install_harness.py claude --print         # 仅打印 Claude Desktop 配置片段
    python install_harness.py cursor                 # 配置 Cursor MCP
    python install_harness.py codex                  # 生成/打印 Codex TOML
    python install_harness.py all                    # 一键配置所有本地已安装的 harnesses
    python install_harness.py link <target>          # 将技能链接到目标项目的技能目录
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
from pathlib import Path

# Windows console UTF-8 wrapper
if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SKILL_DIR = Path(__file__).resolve().parent.parent
MAKER_SERVER_PY = SKILL_DIR / "mcp" / "maker_server.py"

BLENDER_CANDIDATES = [
    os.environ.get("BLENDER_PATH"),
    "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe",
    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe",
    "C:/Program Files/Blender Foundation/Blender 5.0/blender.exe",
    "C:/Program Files/Blender Foundation/Blender 4.3/blender.exe",
    "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe",
    "/usr/bin/blender",
    "/Applications/Blender.app/Contents/MacOS/Blender",
]


def detect_blender() -> str | None:
    for p in BLENDER_CANDIDATES:
        if p and Path(p).is_file():
            return str(Path(p).resolve()).replace("\\", "/")
    return None


def get_maker_mcp_entry(python_bin: str | None = None) -> dict:
    blender = detect_blender()
    py = python_bin or sys.executable.replace("\\", "/")
    env = {
        "PYTHONUNBUFFERED": "1",
    }
    if blender:
        env["BLENDER_PATH"] = blender

    return {
        "command": py,
        "args": [str(MAKER_SERVER_PY.resolve()).replace("\\", "/")],
        "env": env,
    }


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"警告：无法读取或解析 JSON {path} ({e})，将避免覆盖。")
        return {}


def save_json(path: Path, data: dict, dry_run: bool = False) -> bool:
    if dry_run:
        print(f"--- 目标文件: {path} (dry-run) ---")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    print(f"✔ 已更新: {path}")
    return True


# --------------------------------------------------------------------------- #
# Harness Adapters
# --------------------------------------------------------------------------- #


def configure_antigravity(dry_run: bool = False) -> None:
    p = Path.home() / ".gemini" / "config" / "mcp_config.json"
    cfg = load_json(p)
    servers = cfg.setdefault("mcpServers", {})
    servers["melavonmen-td"] = get_maker_mcp_entry()
    save_json(p, cfg, dry_run)


def configure_claude(dry_run: bool = False) -> None:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        p = Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        p = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"

    cfg = load_json(p)
    servers = cfg.setdefault("mcpServers", {})
    servers["melavonmen-td"] = get_maker_mcp_entry()
    save_json(p, cfg, dry_run)


def configure_cursor(dry_run: bool = False) -> None:
    p = Path.cwd() / ".cursor" / "mcp.json"
    cfg = load_json(p)
    servers = cfg.setdefault("mcpServers", {})
    servers["melavonmen-td"] = get_maker_mcp_entry()
    save_json(p, cfg, dry_run)


def configure_windsurf(dry_run: bool = False) -> None:
    p = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
    cfg = load_json(p)
    servers = cfg.setdefault("mcpServers", {})
    servers["melavonmen-td"] = get_maker_mcp_entry()
    save_json(p, cfg, dry_run)


def configure_cline(dry_run: bool = False) -> None:
    p = Path.cwd() / "cline_mcp_settings.json"
    cfg = load_json(p)
    servers = cfg.setdefault("mcpServers", {})
    servers["melavonmen-td"] = get_maker_mcp_entry()
    save_json(p, cfg, dry_run)


def configure_codex(dry_run: bool = False) -> None:
    maker = get_maker_mcp_entry()
    p = Path.home() / ".codex" / "config.toml"

    quote = lambda v: json.dumps(v, ensure_ascii=False)
    lines = [
        "# --- MelavonmenTD 3D Pipeline ---",
        "[mcp_servers.melavonmen-td]",
        f"command = {quote(maker['command'])}",
        f"args = {json.dumps(maker['args'])}",
        "",
        "[mcp_servers.melavonmen-td.env]",
    ]
    for k, v in maker["env"].items():
        lines.append(f"{k} = {quote(v)}")

    toml_text = "\n".join(lines) + "\n"
    if dry_run:
        print(f"--- Codex TOML ({p}) ---")
        print(toml_text)
        return

    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text(encoding="utf-8") if p.is_file() else ""
    if "[mcp_servers.melavonmen-td]" not in existing:
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n" + toml_text)
        print(f"✔ 已追加配置至: {p}")
    else:
        print(f"ℹ {p} 中已存在 melavonmen-td 配置，跳过。")


def link_skill(target_dir: str) -> None:
    dest = Path(target_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    link_path = dest / "MelavonmenTD"
    if link_path.exists():
        print(f"目标已存在: {link_path}")
        return
    try:
        os.symlink(SKILL_DIR, link_path, target_is_directory=True)
        print(f"✔ 符号链接已创建: {link_path} -> {SKILL_DIR}")
    except OSError:
        shutil.copytree(SKILL_DIR, link_path)
        print(f"✔ 技能目录已复制至: {link_path}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MelavonmenTD 多 Agent Harness 配置与安装工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="harness", help="目标 Agent Harness")

    for h in ("antigravity", "claude", "cursor", "codex", "windsurf", "cline", "all"):
        p = sub.add_parser(h, help=f"配置 {h}")
        p.add_argument("--print", action="store_true", dest="dry_run", help="仅打印生成的配置片段，不写入")

    link_p = sub.add_parser("link", help="将技能挂载到指定 Harness 或项目路径")
    link_p.add_argument("target", help="目标技能目录，例如 ~/.gemini/config/skills 或 .agents/skills")

    args = parser.parse_args()

    if not args.harness:
        parser.print_help()
        sys.exit(0)

    if args.harness == "link":
        link_skill(args.target)
        return

    dry = getattr(args, "dry_run", False)

    dispatch = {
        "antigravity": configure_antigravity,
        "claude": configure_claude,
        "cursor": configure_cursor,
        "codex": configure_codex,
        "windsurf": configure_windsurf,
        "cline": configure_cline,
    }

    if args.harness == "all":
        for name, fn in dispatch.items():
            print(f"\n[配置 {name}]")
            fn(dry)
    elif args.harness in dispatch:
        dispatch[args.harness](dry)


if __name__ == "__main__":
    main()
