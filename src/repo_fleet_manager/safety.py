from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import ProjectConfig, Repository
from .operations import SafetyError
from .shell import run


@dataclass(slots=True)
class RepoSafetyState:
    repo: str
    path: str
    exists: bool
    worktree: bool
    dirty: bool
    branch: str | None
    expected_branch: str
    detached: bool
    branch_mismatch: bool
    upstream: str | None
    ahead: int
    behind: int
    diverged: bool


def repository_path(repo: Repository, root: Path) -> Path:
    if repo.source_type == "existing":
        for key in ("existing_path", "local_source", "import_from"):
            value = repo.extra.get(key)
            if value:
                path = Path(str(value)).expanduser()
                return (path if path.is_absolute() else root / path).resolve()
    return (root if repo.is_root else root / repo.path).resolve()


def repository_safety_state(repo: Repository, root: Path) -> RepoSafetyState:
    path = repository_path(repo, root)
    empty = RepoSafetyState(repo.repo, str(path), False, False, False, None, repo.branch, False, False, None, 0, 0, False)
    if not path.exists():
        return empty
    inside = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
    if inside.code != 0:
        empty.exists = True
        return empty
    dirty = bool(run(["git", "status", "--porcelain"], cwd=path).stdout.strip())
    branch = run(["git", "branch", "--show-current"], cwd=path).stdout or None
    detached = branch is None
    branch_mismatch = bool(branch and repo.branch and branch != repo.branch)
    upstream_result = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], cwd=path)
    upstream = upstream_result.stdout if upstream_result.code == 0 else None
    ahead = behind = 0
    if upstream:
        counts = run(["git", "rev-list", "--left-right", "--count", f"{upstream}...HEAD"], cwd=path)
        if counts.code == 0 and counts.stdout:
            parts = counts.stdout.replace("\t", " ").split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])
    return RepoSafetyState(
        repo.repo, str(path), True, True, dirty, branch, repo.branch,
        detached, branch_mismatch, upstream, ahead, behind, ahead > 0 and behind > 0,
    )


def workspace_safety_report(config: ProjectConfig, root: Path) -> list[RepoSafetyState]:
    return [repository_safety_state(repo, root) for repo in config.repositories]


def assert_workspace_safe(
    config: ProjectConfig,
    root: Path,
    action: str,
    force: bool = False,
    reason: str | None = None,
    require_clean: bool = True,
    reject_diverged: bool = True,
    reject_detached: bool = True,
    reject_branch_mismatch: bool = False,
    repositories: list[Repository] | None = None,
) -> list[RepoSafetyState]:
    if force and not (reason and reason.strip()):
        raise SafetyError("--force requires --reason")
    targets = repositories or config.repositories
    states = [repository_safety_state(repo, root) for repo in targets]
    unsafe: list[str] = []
    if require_clean:
        unsafe.extend(f"{state.repo}: dirty worktree ({state.path})" for state in states if state.worktree and state.dirty)
    if reject_diverged:
        unsafe.extend(
            f"{state.repo}: branch diverged from {state.upstream} (ahead={state.ahead}, behind={state.behind})"
            for state in states if state.diverged
        )
    if reject_detached:
        unsafe.extend(f"{state.repo}: detached HEAD ({state.path})" for state in states if state.worktree and state.detached)
    if reject_branch_mismatch:
        unsafe.extend(
            f"{state.repo}: active branch {state.branch!r} differs from configured branch {state.expected_branch!r}"
            for state in states if state.branch_mismatch
        )
    if unsafe and not force:
        raise SafetyError(
            f"refusing unsafe operation `{action}`:\n - " + "\n - ".join(unsafe) +
            "\nCommit/stash/synchronize first, or use --force --reason '<explicit reason>'."
        )
    return states
