#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, json, re
from collections import defaultdict
from pathlib import Path
from typing import Any

APP_PATH = Path("services/api-gateway/src/goftaroo_api_gateway/interfaces/http/app.py")
PHASE_BLOCK_RE = re.compile(r"^# GOFTAROO PHASE (?P<phase>[0-9.]+) (?P<title>.*?) (?P<edge>START|END)$")
PHASE_FUNC_RE = re.compile(r"^_phase(?P<digits>[0-9]+)_(?P<name>[A-Za-z0-9_]+)$")

def phase_from_digits(digits: str) -> str:
    if len(digits) == 2:
        return f"3.{digits[-1]}"
    if len(digits) == 3:
        return f"3.{digits[-2:]}"
    return digits

def block_ranges(lines: list[str]) -> list[dict[str, Any]]:
    stack: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        match = PHASE_BLOCK_RE.match(line.strip())
        if not match:
            continue
        phase, title, edge = match.group("phase"), match.group("title").strip(), match.group("edge")
        if edge == "START":
            stack.append({"phase": phase, "title": title, "start_line": idx})
        else:
            for pos in range(len(stack) - 1, -1, -1):
                if stack[pos]["phase"] == phase:
                    item = stack.pop(pos)
                    item["end_line"] = idx
                    item["line_count"] = idx - item["start_line"] + 1
                    blocks.append(item)
                    break
            else:
                blocks.append({"phase": phase, "title": title, "end_line": idx, "unmatched_end": True})
    for item in stack:
        item["unmatched_start"] = True
        blocks.append(item)
    return sorted(blocks, key=lambda item: item.get("start_line") or item.get("end_line") or 10**9)

def ast_inventory(source: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tree = ast.parse(source)
    funcs: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            match = PHASE_FUNC_RE.match(node.name)
            if match:
                funcs.append({
                    "name": node.name,
                    "phase": phase_from_digits(match.group("digits")),
                    "stable_candidate": match.group("name"),
                    "line": node.lineno,
                    "async": isinstance(node, ast.AsyncFunctionDef),
                })
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    if isinstance(dec.func.value, ast.Name) and dec.func.value.id == "app" and dec.func.attr in {"get", "post", "put", "patch", "delete"}:
                        path = None
                        if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                            path = dec.args[0].value
                        routes.append({"method": dec.func.attr.upper(), "path": path, "handler": node.name, "line": node.lineno})
    return sorted(funcs, key=lambda item: item["line"]), sorted(routes, key=lambda item: item["line"])

def build_report(root: Path) -> dict[str, Any]:
    app_path = root / APP_PATH
    if not app_path.exists():
        raise SystemExit(f"app.py not found: {app_path}")
    source = app_path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    funcs, routes = ast_inventory(source)
    blocks = block_ranges(lines)
    by_phase: dict[str, dict[str, Any]] = defaultdict(lambda: {"function_count": 0, "route_count": 0, "functions": []})
    for func in funcs:
        by_phase[func["phase"]]["function_count"] += 1
        by_phase[func["phase"]]["functions"].append(func["name"])
    route_map: dict[tuple[str, str], list[str]] = defaultdict(list)
    for route in routes:
        if route["path"]:
            route_map[(route["method"], route["path"])].append(route["handler"])
        match = PHASE_FUNC_RE.match(route["handler"])
        if match:
            by_phase[phase_from_digits(match.group("digits"))]["route_count"] += 1
    duplicate_routes = [
        {"method": method, "path": path, "handlers": handlers}
        for (method, path), handlers in sorted(route_map.items())
        if len(handlers) > 1
    ]
    return {
        "app_path": str(APP_PATH),
        "app_line_count": len(lines),
        "phase_block_count": len(blocks),
        "phase_function_count": len(funcs),
        "route_count": len(routes),
        "duplicate_route_count": len(duplicate_routes),
        "duplicate_routes": duplicate_routes,
        "phase_blocks": blocks,
        "phase_functions": funcs,
        "routes": routes,
        "by_phase": dict(sorted(by_phase.items())),
        "next_safe_refactor_order": [
            "Phase 3.20 audit integrity helpers",
            "Phase 3.21 export verification helpers",
            "Phase 3.16/3.17 audit sink/export helpers",
            "Phase 3.18 export worker helpers",
            "Phase 3.10-3.15 proxy/policy/RBAC helpers",
        ],
    }

def render_markdown(report: dict[str, Any]) -> str:
    out = ["# Phase 3.23 — API Gateway Phase Inventory", "", "Generated by `scripts/api-gateway-phase-inventory.py`.", "", "## Summary", "", "| Metric | Value |", "|---|---:|"]
    for key in ["app_line_count", "phase_block_count", "phase_function_count", "route_count", "duplicate_route_count"]:
        out.append(f"| `{key}` | {report[key]} |")
    out += ["", "## Phase buckets", "", "| Phase | Function count | Route count |", "|---|---:|---:|"]
    for phase, data in report["by_phase"].items():
        out.append(f"| {phase} | {data['function_count']} | {data['route_count']} |")
    out += ["", "## Phase blocks", "", "| Phase | Lines | Title |", "|---|---:|---|"]
    for item in report["phase_blocks"]:
        loc = f"{item.get('start_line','?')}-{item.get('end_line','?')}"
        out.append(f"| {item.get('phase')} | {loc} | {item.get('title','')} |")
    if report["duplicate_routes"]:
        out += ["", "## Duplicate routes", "", "| Method | Path | Handlers |", "|---|---|---|"]
        for item in report["duplicate_routes"]:
            out.append(f"| {item['method']} | `{item['path']}` | `{', '.join(item['handlers'])}` |")
    out += ["", "## Next safe refactor order", ""]
    for idx, item in enumerate(report["next_safe_refactor_order"], start=1):
        out.append(f"{idx}. {item}")
    out.append("")
    return "\n".join(out)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--markdown", dest="markdown_path")
    parser.add_argument("--fail-on-duplicates", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = build_report(root)
    print(f"app.py lines: {report['app_line_count']}")
    print(f"phase blocks: {report['phase_block_count']}")
    print(f"phase-prefixed functions: {report['phase_function_count']}")
    print(f"routes: {report['route_count']}")
    print(f"duplicate method/path routes: {report['duplicate_route_count']}")
    if args.json_path:
        out = root / args.json_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote JSON report: {out}")
    if args.markdown_path:
        out = root / args.markdown_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote Markdown report: {out}")
    if args.fail_on_duplicates and report["duplicate_route_count"]:
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
