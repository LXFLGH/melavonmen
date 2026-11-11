#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""maker_server.py — MelavonmenTD 的 MCP 服务（stdio，换行分隔 JSON-RPC）

涵盖 3D 制作与验收流水线的九个动词：
- 几何事实与参数化建模：内置 CAD 引擎 (maker_cad)
- 场景装配与规格校验：maker_spec
- 帧级度量与感官闸门：maker_frame, maker_shot, maker_compare
- 交付与闭环验收闸门：maker_glbcheck, maker_verify, maker_deliver
- 环境自检：maker_doctor

    python maker_server.py            # 跑服务
    python maker_server.py --list     # 打印工具清单（调试用）
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

# 保证在 Windows 环境下 stdin/stdout/stderr 始终为 utf-8，避免 UnicodeEncodeError
if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stdin, "buffer"):
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PROTOCOL = "2024-11-05"


def run_node(script: str, args: list[str], timeout: int = 180, cwd: str | None = None) -> dict:
    cmd = ["node", str(SCRIPTS / script), *args]
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd or os.getcwd(),
        )
    except FileNotFoundError:
        return {"ok": False, "error": {"code": "E_NO_NODE", "message": "node 不在 PATH", "fix": "装 Node 18+"}}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": {"code": "E_TIMEOUT", "message": f"{script} 超时 {timeout}s", "fix": "缩小视口或减少 views"}}
    out = (p.stdout or "").strip()
    tail = "\n".join(out.splitlines()[-60:])
    return {"ok": p.returncode == 0, "exit": p.returncode, "stdout": tail,
            "stderr": (p.stderr or "").strip()[-2000:]}


def need(args: dict, *keys: str) -> str | None:
    for k in keys:
        if not args.get(k):
            return k
    return None


TOOLS = [
    {
        "name": "maker_doctor",
        "description": "环境体检：node / puppeteer-core / chrome / blender / cad，给出完整可用性矩阵与深度诊断。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "maker_spec",
        "description": "校验并编译 maker.spec/v1：检查 unit_mm、owner、bbox 区间，拆解 CAD spec、manifest 与场景常量。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec": {"type": "string", "description": "spec 文件路径"},
                "out": {"type": "string", "description": "产物目录，默认 out/"},
            },
            "required": ["spec"],
        },
    },
    {
        "name": "maker_cad",
        "description": "基于内置 CAD 几何引擎构建、度量、验证并交付 owner=cad 零件（GLB/STEP/STL），产出 S3 几何真 receipt。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec": {"type": "string", "description": "maker.spec.json 或 spec.cad.json 文件路径"},
                "out": {"type": "string", "description": "产物输出目录，默认 out/"},
                "part": {"type": "string", "description": "指定单个 cad 零件名（默认构建所有 cad 零件）"},
                "formats": {"type": "string", "description": "导出格式，逗号分隔，默认 glb（可选 glb,step,stl,obj）"},
                "quality": {"type": "string", "description": "质量级别：draft / review / deliver，默认 deliver"},
                "json": {"type": "string", "description": "receipt 输出路径，默认 out/cad.receipt.json"},
            },
            "required": ["spec"],
        },
    },
    {
        "name": "maker_frame",
        "description": "帧级度量并出 receipt：主体覆盖率、texel 密度、draw call/三角形预算。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "页面 file:// 地址"},
                "root": {"type": "string", "description": "主体表达式，如 window.CRT.aio.group"},
                "ready": {"type": "string", "description": "就绪表达式，默认 window.__crtReady===true"},
                "texel": {"type": "string", "description": "name=expr:min，逗号分隔"},
                "budget": {"type": "string", "description": "calls=250,tris=150000"},
                "coverage": {"type": "string", "description": "0.25..0.55"},
                "json": {"type": "string", "description": "receipt 输出路径"},
                "cwd": {"type": "string", "description": "项目根目录（解析 puppeteer-core 用）"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "maker_shot",
        "description": "按 views.json 批量出图，支持 auto 取景与裁剪到某个物体。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "views": {"type": "string"},
                "out": {"type": "string"},
                "root": {"type": "string"},
                "cwd": {"type": "string"},
            },
            "required": ["url", "views"],
        },
    },
    {
        "name": "maker_compare",
        "description": "两张剪影图求 IoU（blockout 与参考比对）。",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "string"}, "min": {"type": "string"}},
            "required": ["a", "b"],
        },
    },
    {
        "name": "maker_glbcheck",
        "description": "校验 GLB 的单位换算后 bbox 是否等于 spec 的 mm 尺寸与三角面预算。",
        "inputSchema": {
            "type": "object",
            "properties": {"glb": {"type": "string"}, "spec": {"type": "string"}, "part": {"type": "string"}, "json": {"type": "string"}},
            "required": ["glb"],
        },
    },
    {
        "name": "maker_verify",
        "description": "合并 frame / cad / glbcheck 的 receipt，全部通过且 spec_hash 一致才算通过。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame": {"type": "string", "description": "frame receipt 路径"},
                "cad": {"type": "string", "description": "cad receipt 路径"},
                "glb": {"type": "string", "description": "glbcheck receipt 路径"},
                "json": {"type": "string", "description": "合并后 receipt 路径"},
            },
        },
    },
    {
        "name": "maker_deliver",
        "description": "交付闸门：关联的 receipts 全部 pass 且 spec_hash 一致才返回文件清单。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "frame": {"type": "string"},
                "cad": {"type": "string"},
                "glb": {"type": "string"},
                "files": {"type": "string", "description": "交付文件列表，逗号分隔"},
            },
        },
    },
]


def call(name: str, a: dict) -> dict:
    if name == "maker_doctor":
        return run_node("doctor.mjs", ["--json", "out/doctor.json"])

    if name == "maker_spec":
        miss = need(a, "spec")
        if miss:
            return {"ok": False, "error": {"code": "E_ARGS", "message": f"缺 {miss}", "fix": "传 spec 路径"}}
        return run_node("compile.mjs", ["--spec", a["spec"], "--out", a.get("out", "out")], cwd=a.get("cwd"))

    if name == "maker_cad":
        miss = need(a, "spec")
        if miss:
            return {"ok": False, "error": {"code": "E_ARGS", "message": f"缺 {miss}", "fix": "传 spec 路径"}}
        args = ["--spec", a["spec"], "--out", a.get("out", "out")]
        for k, flag in (("part", "--part"), ("formats", "--formats"), ("quality", "--quality"), ("json", "--json")):
            if a.get(k):
                args += [flag, str(a[k])]
        return run_node("cad.mjs", args, cwd=a.get("cwd"))

    if name == "maker_frame":
        miss = need(a, "url")
        if miss:
            return {"ok": False, "error": {"code": "E_ARGS", "message": "缺 url", "fix": "传页面地址"}}
        args = ["--url", a["url"]]
        for k, flag in (("root", "--root"), ("ready", "--ready"), ("texel", "--texel"),
                        ("budget", "--budget"), ("coverage", "--coverage"), ("json", "--json")):
            if a.get(k):
                args += [flag, str(a[k])]
        return run_node("frame.mjs", args, cwd=a.get("cwd"))

    if name == "maker_shot":
        miss = need(a, "url", "views")
        if miss:
            return {"ok": False, "error": {"code": "E_ARGS", "message": f"缺 {miss}", "fix": "传 url 与 views"}}
        args = ["--url", a["url"], "--views", a["views"], "--out", a.get("out", "shots")]
        if a.get("root"):
            args += ["--root", a["root"]]
        return run_node("shot.mjs", args, cwd=a.get("cwd"))

    if name == "maker_compare":
        miss = need(a, "a", "b")
        if miss:
            return {"ok": False, "error": {"code": "E_ARGS", "message": f"缺 {miss}", "fix": "传两张图"}}
        args = ["--a", a["a"], "--b", a["b"]]
        if a.get("min"):
            args += ["--min", str(a["min"])]
        return run_node("compare.mjs", args, cwd=a.get("cwd"))

    if name == "maker_glbcheck":
        miss = need(a, "glb")
        if miss:
            return {"ok": False, "error": {"code": "E_ARGS", "message": "缺 glb", "fix": "传 GLB 路径"}}
        args = ["--glb", a["glb"]]
        for k, flag in (("spec", "--spec"), ("part", "--part"), ("json", "--json")):
            if a.get(k):
                args += [flag, str(a[k])]
        return run_node("glbcheck.mjs", args)

    if name in ("maker_verify", "maker_deliver"):
        paths = [a[k] for k in ("frame", "cad", "glb") if a.get(k)]
        if not paths:
            return {"ok": False, "error": {"code": "E_ARGS", "message": "需至少提供 frame / cad / glb receipt 之一", "fix": "传入 receipt 路径"}}
        receipts = []
        for p in paths:
            try:
                receipts.append(json.loads(Path(p).read_text(encoding="utf-8")))
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "error": {"code": "E_RECEIPT", "message": str(e), "path": p,
                                               "fix": "重跑对应闸门生成 receipt"}}
        bad = [r for r in receipts if r.get("verdict") != "pass"]
        hashes = {r.get("spec_hash") or r.get("build", {}).get("spec_hash") for r in receipts if (r.get("spec_hash") or r.get("build", {}).get("spec_hash"))}
        if bad:
            bad_gates = [b.get("gate", "unknown") for b in bad]
            return {"ok": False, "error": {"code": "E_NOT_VERIFIED",
                                           "message": f"{len(bad)} 份 receipt 未 pass: {bad_gates}", "fix": "按 checks 里的 fix 修复"}}
        if len(hashes) > 1:
            return {"ok": False, "error": {"code": "E_HASH_MISMATCH",
                                           "message": f"receipt 之间 spec_hash 不一致: {hashes}", "fix": "以同一 spec 重跑各闸门"}}
        if name == "maker_deliver":
            files = [f for f in (a.get("files") or "").split(",") if f]
            missing = [f for f in files if not Path(f).exists()]
            if missing:
                return {"ok": False, "error": {"code": "E_FILE_MISSING", "message": ", ".join(missing),
                                               "fix": "重新导出缺失的文件"}}
            return {"ok": True, "verdict": "pass", "files": files, "receipts_verified": len(receipts)}
        return {"ok": True, "verdict": "pass", "receipts_verified": len(receipts)}

    return {"ok": False, "error": {"code": "E_NO_TOOL", "message": f"未知工具 {name}", "fix": "先 tools/list"}}


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    if "--list" in sys.argv:
        print(json.dumps(TOOLS, ensure_ascii=False, indent=2))
        return
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        mid = req.get("id")
        method = req.get("method")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "melavonmen-td", "version": "1.2.0"},
            }})
        elif method in ("notifications/initialized", "initialized"):
            continue
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = req.get("params") or {}
            res = call(params.get("name", ""), params.get("arguments") or {})
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2)}],
                "isError": not res.get("ok", False),
            }})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"not found: {method}"}})


if __name__ == "__main__":
    main()
