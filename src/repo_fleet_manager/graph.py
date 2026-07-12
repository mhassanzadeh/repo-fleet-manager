from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

from .config import ProjectConfig, Repository

T = TypeVar("T")


@dataclass(slots=True)
class GraphNode:
    repo: Repository
    dependencies: list[str]


def dependency_graph(config: ProjectConfig) -> dict[str, GraphNode]:
    lookup = config.repository_map()
    graph: dict[str, GraphNode] = {}
    for repo in config.repositories:
        dependencies: list[str] = []
        for item in repo.depends_on:
            dep = lookup[item]
            dependencies.append(dep.repo)
        graph[repo.repo] = GraphNode(repo, dependencies)
    return graph


def topological_levels(config: ProjectConfig, repositories: Iterable[Repository] | None = None) -> list[list[Repository]]:
    selected = list(repositories or config.repositories)
    selected_names = {repo.repo for repo in selected}
    graph = dependency_graph(config)
    remaining = {
        repo.repo: {dep for dep in graph[repo.repo].dependencies if dep in selected_names}
        for repo in selected
    }
    levels: list[list[Repository]] = []
    done: set[str] = set()
    by_name = {repo.repo: repo for repo in selected}
    while remaining:
        ready = sorted((name for name, deps in remaining.items() if deps <= done), key=lambda name: (by_name[name].path, name))
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise ValueError(f"dependency graph contains a cycle among: {cycle}")
        levels.append([by_name[name] for name in ready])
        done.update(ready)
        for name in ready:
            remaining.pop(name, None)
    return levels


def execute_levels(
    config: ProjectConfig,
    worker: Callable[[Repository], T],
    repositories: Iterable[Repository] | None = None,
    jobs: int = 1,
) -> list[tuple[Repository, T]]:
    results: list[tuple[Repository, T]] = []
    for level in topological_levels(config, repositories):
        if jobs <= 1 or len(level) <= 1:
            for repo in level:
                results.append((repo, worker(repo)))
            continue
        with ThreadPoolExecutor(max_workers=min(jobs, len(level)), thread_name_prefix="rfm") as executor:
            futures = {executor.submit(worker, repo): repo for repo in level}
            completed: dict[str, tuple[Repository, T]] = {}
            for future in as_completed(futures):
                repo = futures[future]
                completed[repo.repo] = (repo, future.result())
            for repo in level:
                results.append(completed[repo.repo])
    return results


def render_graph(config: ProjectConfig, output_format: str = "text") -> str:
    levels = topological_levels(config)
    if output_format == "json":
        payload = {
            "levels": [[repo.repo for repo in level] for level in levels],
            "nodes": [
                {"repo": repo.repo, "path": repo.path, "depends_on": repo.depends_on}
                for repo in config.repositories
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output_format == "dot":
        lines = ["digraph rfm {", "  rankdir=LR;"]
        for repo in config.repositories:
            label = f"{repo.repo}\\n{repo.path}"
            lines.append(f'  "{repo.repo}" [label="{label}"];')
            for dep in repo.depends_on:
                target = config.repository_map()[dep].repo
                lines.append(f'  "{target}" -> "{repo.repo}";')
        lines.append("}")
        return "\n".join(lines) + "\n"
    lines = ["Repository dependency graph"]
    for index, level in enumerate(levels):
        lines.append(f"level {index}: " + ", ".join(repo.repo for repo in level))
        for repo in level:
            lines.append(f"  - {repo.repo} ({repo.path}) depends_on={repo.depends_on or []}")
    return "\n".join(lines) + "\n"
