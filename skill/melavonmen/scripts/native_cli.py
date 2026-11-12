"""Portable command line for Melavonmen Native Codebase Intelligence.

Examples:
  python native_cli.py --project /repo build
  python native_cli.py --project /repo query calculate_price --mode symbol --limit 5
  python native_cli.py --project /repo graph Pricing --reverse --depth 3
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

from native_engine import (
    audit, connect, context, doctor, graph, impact, query, rebuild, references,
    sync_status, update, inside,
)

def benchmark(root, database, phrases, runs=5):
    # No user data is deleted: the benchmark gets its own unique cache path.
    temp = ".melavonmen/bench-" + str(os.getpid()) + "-" + str(time.time_ns()) + ".sqlite"
    measurements = {"cold_build_ms": 0, "warm_update_ms": [], "query_ms": [],
                    "queries": phrases}
    try:
        start = time.perf_counter()
        result = update(root, temp, full=True)
        measurements["cold_build_ms"] = round((time.perf_counter() - start) * 1000, 2)
        for _ in range(max(1, min(runs, 50))):
            start = time.perf_counter()
            update(root, temp)
            measurements["warm_update_ms"].append((time.perf_counter() - start) * 1000)
            for phrase in phrases:
                start = time.perf_counter()
                query(root, phrase, dbpath=temp)
                measurements["query_ms"].append((time.perf_counter() - start) * 1000)
        def dist(samples):
            samples = sorted(samples)
            if not samples:
                return {}
            return {"p50_ms": round(statistics.median(samples), 2),
                    "p95_ms": round(samples[min(len(samples)-1, int(.95 * (len(samples)-1)))], 2),
                    "runs": len(samples)}
        measurements["warm_update"] = dist(measurements.pop("warm_update_ms"))
        measurements["query"] = dist(measurements.pop("query_ms"))
        measurements["stats"] = result["stats"]
        return measurements
    finally:
        for suffix in ("", "-wal", "-shm"):
            path = inside(Path(root).resolve(), temp + suffix)
            if path.is_file():
                path.unlink()

def export_routes(root, database):
    root = Path(root).resolve()
    db = connect(root, database, readonly=True)
    sources = [dict(row) for row in db.execute(
        "SELECT path,sha256,language,depth FROM files ORDER BY path")]
    routes = {"schema_version": "melavonmen.native-routes/1", "generated": True,
              "sources": sources, "note": "Machine-generated. Not authoritative Wiki facts."}
    output = inside(root, ".melavonmen/wiki-routes.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = output.with_suffix(".json.stage")
    stage.write_text(json.dumps(routes, ensure_ascii=False, indent=2), "utf-8")
    os.replace(stage, output)
    db.close()
    return {"output": str(output.relative_to(root)), "count": len(sources)}

def parser():
    p = argparse.ArgumentParser(description="Melavonmen native codebase intelligence")
    p.add_argument("--project", type=Path, default=Path.cwd())
    p.add_argument("--database", default=None, help="relative SQLite path inside workspace")
    p.add_argument("--human", action="store_true")
    commands = p.add_subparsers(dest="command", required=True)
    for cmd in ("build", "update", "check", "audit", "doctor", "rebuild",
                "sync-status", "export-routes", "benchmark"):
        sub = commands.add_parser(cmd)
        if cmd in ("build", "update"):
            sub.add_argument("--full", action="store_true")
        if cmd == "benchmark":
            sub.add_argument("--runs", type=int, default=5)
            sub.add_argument("--phrase", action="append", default=[])
    q = commands.add_parser("query")
    q.add_argument("phrase")
    q.add_argument("--mode", choices=["auto", "file", "path", "symbol",
                                      "definition", "text", "contract", "natural"],
                   default="auto")
    q.add_argument("--limit", type=int, default=20)
    q.add_argument("--offset", type=int, default=0)
    q.add_argument("--language")
    q.add_argument("--directory")
    q.add_argument("--token-budget", type=int, default=1500)
    f = commands.add_parser("find")
    f.add_argument("symbol")
    r = commands.add_parser("references")
    r.add_argument("symbol")
    r.add_argument("--limit", type=int, default=100)
    g = commands.add_parser("graph")
    g.add_argument("name")
    g.add_argument("--reverse", action="store_true")
    g.add_argument("--depth", type=int, default=2)
    g.add_argument("--kind", action="append")
    i = commands.add_parser("impact")
    i.add_argument("changed", nargs="+")
    i.add_argument("--depth", type=int, default=3)
    c = commands.add_parser("context")
    c.add_argument("path")
    c.add_argument("--line", type=int, default=1)
    c.add_argument("--before", type=int, default=6)
    c.add_argument("--after", type=int, default=12)
    return p

def main(argv=None):
    args = parser().parse_args(argv)
    root = args.project.resolve()
    try:
        if args.command in ("build", "update", "check"):
            result = update(root, args.database,
                            full=getattr(args, "full", False),
                            check=args.command == "check")
        elif args.command == "audit":
            result = audit(root, connect(root, args.database, readonly=True))
        elif args.command == "doctor":
            result = doctor(root)
        elif args.command == "rebuild":
            result = rebuild(root, args.database)
        elif args.command == "query":
            result = query(root, args.phrase, mode=args.mode, limit=args.limit,
                           offset=args.offset, language=args.language,
                           directory=args.directory, token_budget=args.token_budget,
                           dbpath=args.database)
        elif args.command == "find":
            result = query(root, args.symbol, mode="definition", dbpath=args.database)
        elif args.command == "references":
            result = references(root, args.symbol, args.limit, dbpath=args.database)
        elif args.command == "graph":
            result = graph(root, args.name, args.reverse, args.depth,
                           kinds=args.kind, dbpath=args.database)
        elif args.command == "impact":
            result = impact(root, args.changed, args.depth, dbpath=args.database)
        elif args.command == "context":
            result = context(root, args.path, args.line, args.before,
                             args.after, dbpath=args.database)
        elif args.command == "sync-status":
            result = sync_status(root)
        elif args.command == "export-routes":
            result = export_routes(root, args.database)
        else:
            result = benchmark(root, args.database, args.phrase or
                               ["calculate", "load", "class_name"], args.runs)
        if args.human:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 1 if isinstance(result, dict) and result.get("ok") is False else 0
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

if __name__ == "__main__":
    sys.exit(main())
