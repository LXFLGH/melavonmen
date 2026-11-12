"""Launch Melavonmen's independent MCP server or terminal interface."""

import argparse
from html import escape
import json
from pathlib import Path
import sqlite3
import sys

from melavonmen_index.protocol import Server
from melavonmen_index.tools import Tools, edge_text
from melavonmen_index.workspace import IndexErrorWithCode, Workspace, project_root


def base_options(parser):
    parser.add_argument("--project", default=argparse.SUPPRESS)
    parser.add_argument("--config", default=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    parser.add_argument("--host", choices=["codex"], default=argparse.SUPPRESS, help=argparse.SUPPRESS)


def cli_parser():
    cli = argparse.ArgumentParser(description="Melavonmen code index")
    base_options(cli)
    commands = cli.add_subparsers(dest="command", required=True)

    def command(name):
        sub = commands.add_parser(name)
        base_options(sub)
        return sub

    status = command("status")
    status.add_argument("--check-freshness", dest="checkFreshness", action="store_true")
    indexing = command("index")
    for flag, destination in (("force", "force"), ("estimate-only", "estimateOnly"), ("dry-run", "dryRun"), ("verbose", "verbose")):
        indexing.add_argument("--" + flag, dest=destination, action="store_true")
    command("health")
    command("metrics")
    command("logs").add_argument("--limit", type=int)
    for name, dest in (("search", "query"), ("peek", "query"), ("definition", "query"), ("similar", "code"),
                       ("context", "query"), ("edit-context", "query")):
        search = command(name)
        search.add_argument(dest)
        if name != "edit-context":
            search.add_argument("--limit", type=int)
        if name in ("context", "edit-context", "definition"):
            search.add_argument("--token-budget", dest="tokenBudget", type=int)
    graph = command("graph")
    graph.add_argument("direction", choices=["callers", "callees", "both"])
    graph.add_argument("name")
    graph.add_argument("--file", dest="filePath")
    path = command("path")
    path.add_argument("from")
    path.add_argument("to")
    architecture = command("architecture")
    architecture.add_argument("--directory")
    architecture.add_argument("--query")
    architecture.add_argument("--depth", type=int)
    command("communities").add_argument("--branch")
    impact = command("impact")
    group = impact.add_mutually_exclusive_group()
    group.add_argument("--working-tree", dest="workingTree", action="store_true")
    group.add_argument("--branch")
    group.add_argument("--pr", type=int)
    workspace = command("workspace")
    workspace.add_argument("action", choices=["status"])
    workspace.add_argument("--repo", action="append", required=True, metavar="NAME=PATH")
    history = command("history")
    history_actions = history.add_subparsers(dest="action", required=True)
    for action in ("status", "sync", "search", "clear"):
        sub = history_actions.add_parser(action)
        base_options(sub)
        sub.add_argument("--repository")
        if action == "sync":
            sub.add_argument("--since")
        if action == "search":
            sub.add_argument("query")
            sub.add_argument("--kind")
            sub.add_argument("--state")
            sub.add_argument("--author")
            sub.add_argument("--limit", type=int)
    visualize = command("visualize")
    visualize.add_argument("--output", type=Path, required=True)
    return cli


COMMANDS = {
    "status": "index_status", "index": "index_codebase", "health": "index_health_check",
    "metrics": "index_metrics", "logs": "index_logs", "search": "codebase_search",
    "peek": "codebase_peek", "definition": "implementation_lookup", "similar": "find_similar",
    "graph": "call_graph", "path": "call_graph_path", "context": "codebase_context",
    "edit-context": "codebase_edit_context", "architecture": "architecture_context",
    "communities": "code_communities", "impact": "pr_impact",
}


def render_graph(tools, destination):
    graph = tools.graph(None)
    paths = sorted(graph.by_file)
    rows = []
    for path in paths:
        rows.append(f"<details><summary>{escape(path)}</summary><ul>")
        for key in sorted(graph.by_file[path]):
            symbol = graph.symbols[key]
            links = "".join(f"<li>{escape(edge_text(graph, edge))}</li>" for edge in graph.edges(key, "both"))
            rows.append(f"<li>{escape(symbol['qualifiedName'])} · line {symbol['lineStart']}<ul>{links}</ul></li>")
        rows.append("</ul></details>")
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Melavonmen code graph</title><style>body{font:16px system-ui;max-width:70rem;margin:2rem auto;padding:0 1rem}
details{padding:.5rem;border-bottom:1px solid #aaa}summary{cursor:pointer}li{margin:.2rem 0}</style>
<h1>Melavonmen code graph</h1>""" + "\n".join(rows) + "</html>\n"
    with destination.open("x", encoding="utf-8") as output:
        output.write(page)
    return {"path": str(destination.resolve()), "symbols": len(graph.symbols),
            "edges": sum(map(len, graph.outgoing.values()))}


def cli(argv):
    options = vars(cli_parser().parse_args(argv))
    command = options.pop("command")
    use_json = options.pop("json", False)
    project = options.pop("project", None)
    override = options.pop("config", None)
    options.pop("host", None)
    tools = Tools(Workspace(project_root(project), override))
    if command == "workspace":
        result = {}
        for repo in options["repo"]:
            name, sep, path = repo.partition("=")
            if not sep or not name or not path or name in result:
                raise IndexErrorWithCode("Workspace repositories require unique NAME=PATH arguments")
            result[name] = Tools(Workspace(project_root(path), override)).index.status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if command == "visualize":
        print(json.dumps(render_graph(tools, options["output"]), ensure_ascii=False, indent=2))
        return
    if command == "history":
        name = "repository_history_" + options.pop("action")
    else:
        name = COMMANDS[command]
    result = tools.invoke(name, {key: value for key, value in options.items() if value is not None})
    if use_json:
        print(json.dumps(result["structuredContent"], ensure_ascii=False, indent=2))
    else:
        print(result["content"][0]["text"])


def main(argv):
    if argv[:1] == ["--cli"]:
        cli(argv[1:])
        return
    parser = argparse.ArgumentParser(description="Melavonmen MCP over stdio")
    parser.add_argument("--project")
    parser.add_argument("--config")
    parser.add_argument("--host", choices=["codex"], help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    Server(Tools(Workspace(project_root(args.project), args.config))).run()


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (IndexErrorWithCode, OSError, sqlite3.Error, ValueError) as exc:
        print(f"Melavonmen: {exc}", file=sys.stderr)
        sys.exit(1)
