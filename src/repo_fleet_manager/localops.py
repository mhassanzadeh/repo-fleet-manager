from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import ProjectConfig, Repository
from .shell import run, run_interactive

SEED_USER_NAME = "Repo Fleet Manager"
SEED_USER_EMAIL = "rfm@example.invalid"
ROOT_GITIGNORE_PATTERNS = [".repo-fleet/build/", ".repo-fleet/tmp/", ".repo-fleet/remotes/"]


def resolve_under_root(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def remotes_dir(config: ProjectConfig, root: Path, override: str | None = None) -> Path:
    value = override or config.local.get("remotes_dir") or ".repo-fleet/remotes"
    return resolve_under_root(root, str(value))


def local_bare_path(repo: Repository, remotes: Path) -> Path:
    return remotes / f"{repo.repo}.git"


def local_bare_url(repo: Repository, remotes: Path) -> str:
    return local_bare_path(repo, remotes).resolve().as_uri()


def path_from_file_url(url: str) -> Path | None:
    if not url.startswith("file://"):
        path = Path(url).expanduser()
        return path if path.is_absolute() or url.endswith(".git") else None
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc not in {"", "localhost"}:
        return Path(f"//{parsed.netloc}{unquote(parsed.path)}")
    return Path(unquote(parsed.path))


def repo_source_url(repo: Repository, root: Path) -> str | None:
    for key in ("mirror_source", "upstream_url", "source_url", "fork_from", "clone_url", "local_source"):
        value = repo.extra.get(key)
        if value:
            text = str(value)
            if key == "local_source":
                return str(resolve_under_root(root, text))
            return text
    return None


def git_is_worktree(path: Path) -> bool:
    return path.exists() and run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path).code == 0


def git_has_head(path: Path) -> bool:
    return run(["git", "rev-parse", "--verify", "HEAD"], cwd=path).code == 0


def bare_has_head(path: Path) -> bool:
    return path.exists() and run(["git", f"--git-dir={path}", "rev-parse", "--verify", "HEAD"]).code == 0


def ensure_parent(path: Path, apply: bool) -> None:
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)


def ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("git is required for local repository operations")


def commit_if_dirty(path: Path, message: str, apply: bool) -> int:
    status = run(["git", "status", "--porcelain"], cwd=path)
    if status.code != 0:
        return status.code
    if not status.stdout.strip():
        return 0
    add = ["git", "add", "."]
    commit = [
        "git",
        "-c", f"user.name={SEED_USER_NAME}",
        "-c", f"user.email={SEED_USER_EMAIL}",
        "commit", "-m", message,
    ]
    code = run_interactive(add, cwd=path, dry_run=not apply)
    if code != 0:
        return code
    return run_interactive(commit, cwd=path, dry_run=not apply)


def ensure_root_gitignore(path: Path, apply: bool) -> None:
    gitignore = path / ".gitignore"
    if not apply:
        print("[DRY-RUN] ensure root .gitignore contains .repo-fleet local runtime paths")
        return
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    existing_set = set(existing)
    changed = False
    for pattern in ROOT_GITIGNORE_PATTERNS:
        if pattern not in existing_set:
            existing.append(pattern)
            changed = True
    if changed:
        gitignore.write_text("\n".join(existing).rstrip() + "\n", encoding="utf-8")


def ensure_initial_commit(repo: Repository, path: Path, apply: bool) -> int:
    if git_has_head(path):
        if repo.is_root:
            ensure_root_gitignore(path, apply)
            return commit_if_dirty(path, "chore: update local repo-fleet gitignore", apply)
        return 0
    readme = path / "README.md"
    if apply:
        if not readme.exists():
            readme.write_text(f"# {repo.repo}\n\nLocal repository managed by Repo Fleet Manager.\n", encoding="utf-8")
        if repo.is_root:
            ensure_root_gitignore(path, apply)
    else:
        print(f"[DRY-RUN] seed initial README/commit in {repo.path}")
    return commit_if_dirty(path, f"chore: initialize {repo.repo}", apply)


def ensure_worktree_repo(repo: Repository, root: Path, apply: bool, set_origin: bool = False, remotes: Path | None = None) -> int:
    path = root if repo.is_root else root / repo.path
    if not path.exists():
        print(f"[CREATE] {repo.path}: directory")
        if apply:
            path.mkdir(parents=True, exist_ok=True)
    if not git_is_worktree(path):
        print(f"[INIT] {repo.path}: git init -b {repo.branch}")
        code = run_interactive(["git", "init", "-b", repo.branch], cwd=path, dry_run=not apply)
        if code != 0:
            code = run_interactive(["git", "init"], cwd=path, dry_run=not apply)
            if code == 0:
                code = run_interactive(["git", "checkout", "-B", repo.branch], cwd=path, dry_run=not apply)
        if code != 0:
            return code
    code = ensure_initial_commit(repo, path, apply)
    if code != 0:
        return code
    if set_origin and remotes is not None:
        url = local_bare_url(repo, remotes)
        if run(["git", "remote", "get-url", "origin"], cwd=path).code == 0:
            code = run_interactive(["git", "remote", "set-url", "origin", url], cwd=path, dry_run=not apply)
        else:
            code = run_interactive(["git", "remote", "add", "origin", url], cwd=path, dry_run=not apply)
        if code != 0:
            return code
    return 0


def ensure_bare_remote(repo: Repository, root: Path, remotes: Path, apply: bool, mirror_sources: bool = False) -> int:
    ensure_git_available()
    target = local_bare_path(repo, remotes)
    if target.exists():
        print(f"[SKIP] local remote exists: {target}")
        return 0
    source = repo_source_url(repo, root)
    ensure_parent(target, apply)
    if source and mirror_sources:
        print(f"[MIRROR] {repo.repo}: {source} -> {target}")
        return run_interactive(["git", "clone", "--mirror", source, str(target)], cwd=root, dry_run=not apply)
    print(f"[INIT] local bare remote: {target}")
    code = run_interactive(["git", "init", "--bare", "-b", repo.branch, str(target)], cwd=root, dry_run=not apply)
    if code == 0 and apply:
        run(["git", f"--git-dir={target}", "symbolic-ref", "HEAD", f"refs/heads/{repo.branch}"])
    return code


def seed_bare_remote(repo: Repository, remotes: Path, apply: bool) -> int:
    target = local_bare_path(repo, remotes)
    if bare_has_head(target):
        print(f"[SKIP] local remote already has commits: {repo.repo}")
        return 0
    print(f"[SEED] {repo.repo}: initial commit -> {target}")
    if not apply:
        print(f"[DRY-RUN] create temporary worktree, commit README, push {repo.branch}")
        return 0
    with tempfile.TemporaryDirectory(prefix="rfm-seed-") as td:
        work = Path(td) / repo.repo
        work.mkdir(parents=True)
        code = run_interactive(["git", "init", "-b", repo.branch], cwd=work, dry_run=False)
        if code != 0:
            code = run_interactive(["git", "init"], cwd=work, dry_run=False)
            if code != 0:
                return code
            code = run_interactive(["git", "checkout", "-B", repo.branch], cwd=work, dry_run=False)
            if code != 0:
                return code
        (work / "README.md").write_text(f"# {repo.repo}\n\nSeeded local repository managed by Repo Fleet Manager.\n", encoding="utf-8")
        if repo.is_root:
            (work / ".gitignore").write_text("\n".join(ROOT_GITIGNORE_PATTERNS) + "\n", encoding="utf-8")
        code = commit_if_dirty(work, f"chore: seed {repo.repo}", apply=True)
        if code != 0:
            return code
        code = run_interactive(["git", "remote", "add", "origin", local_bare_url(repo, remotes)], cwd=work, dry_run=False)
        if code != 0:
            return code
        return run_interactive(["git", "push", "-u", "origin", repo.branch], cwd=work, dry_run=False)


def create_local_remotes(config: ProjectConfig, root: Path, remotes_override: str | None, apply: bool, mirror_sources: bool, seed: bool = False, seed_root: bool = True) -> int:
    remotes = remotes_dir(config, root, remotes_override)
    print(f"local remotes: {remotes}")
    failed = False
    for repo in config.repositories:
        code = ensure_bare_remote(repo, root, remotes, apply, mirror_sources=mirror_sources)
        failed = failed or code != 0
        if code == 0 and seed and (seed_root or not repo.is_root):
            failed = failed or seed_bare_remote(repo, remotes, apply) != 0
    return 1 if failed else 0


def init_local_worktrees(config: ProjectConfig, root: Path, remotes_override: str | None, apply: bool, with_remotes: bool, set_origin: bool) -> int:
    remotes = remotes_dir(config, root, remotes_override)
    failed = False
    if with_remotes or set_origin:
        failed = create_local_remotes(config, root, remotes_override, apply, mirror_sources=False, seed=False) != 0
    for repo in config.repositories:
        code = ensure_worktree_repo(repo, root, apply, set_origin=set_origin, remotes=remotes)
        failed = failed or code != 0
        if code == 0 and set_origin and apply:
            push = run_interactive(["git", "push", "-u", "origin", repo.branch], cwd=(root if repo.is_root else root / repo.path), dry_run=False)
            failed = failed or push != 0
    return 1 if failed else 0


def clone_local_repositories(config: ProjectConfig, root: Path, remotes_override: str | None, apply: bool, mirror_sources: bool) -> int:
    remotes = remotes_dir(config, root, remotes_override)
    create_local_remotes(config, root, remotes_override, apply, mirror_sources=mirror_sources, seed=False)
    failed = False
    for repo in config.repositories:
        url = local_bare_url(repo, remotes)
        if repo.is_root:
            if git_is_worktree(root):
                print("[SKIP] root: already a git worktree")
                continue
            if any(root.iterdir()):
                print("[SKIP] root: destination is not empty; use `rfm local bootstrap` or pass an empty --root")
                continue
            print(f"[CLONE] root: {url} -> {root}")
            failed = failed or run_interactive(["git", "-c", "protocol.file.allow=always", "clone", url, str(root)], cwd=root.parent, dry_run=not apply) != 0
            continue
        path = root / repo.path
        if path.exists():
            print(f"[SKIP] {repo.path}: path exists")
            continue
        print(f"[CLONE] {repo.path}: {url}")
        ensure_parent(path, apply)
        failed = failed or run_interactive(["git", "-c", "protocol.file.allow=always", "clone", "-b", repo.branch, url, str(path)], cwd=root, dry_run=not apply) != 0
    return 1 if failed else 0


def sync_gitmodules_for_local(config: ProjectConfig, root: Path, remotes: Path, apply: bool) -> int:
    lines: list[str] = []
    for repo in config.submodules():
        url = local_bare_url(repo, remotes)
        lines.extend([f'[submodule "{repo.path}"]', f"\tpath = {repo.path}", f"\turl = {url}"])
    content = "\n".join(lines) + "\n"
    if not apply:
        print("[DRY-RUN] Would write .gitmodules with local file:// URLs:")
        print(content)
        return 0
    (root / ".gitmodules").write_text(content, encoding="utf-8")
    return 0


def bootstrap_local(config: ProjectConfig, root: Path, remotes_override: str | None, apply: bool, mirror_sources: bool, set_origin: bool) -> int:
    remotes = remotes_dir(config, root, remotes_override)
    root_repo = config.root_repository
    if root_repo is None:
        raise RuntimeError("config must include one root repository with path '.' or kind 'root'")
    print(f"root:          {root}")
    print(f"local remotes: {remotes}")
    failed = False
    failed = create_local_remotes(config, root, remotes_override, apply, mirror_sources=mirror_sources, seed=False) != 0
    for repo in config.submodules():
        failed = failed or seed_bare_remote(repo, remotes, apply) != 0
    failed = failed or ensure_worktree_repo(root_repo, root, apply, set_origin=set_origin, remotes=remotes) != 0
    if set_origin and apply:
        run_interactive(["git", "push", "-u", "origin", root_repo.branch], cwd=root, dry_run=False)
    for repo in config.submodules():
        path = root / repo.path
        if path.exists():
            print(f"[SKIP] submodule path exists: {repo.path}")
            continue
        ensure_parent(path, apply)
        cmd = ["git", "-c", "protocol.file.allow=always", "submodule", "add", "-b", repo.branch, local_bare_url(repo, remotes), repo.path]
        failed = failed or run_interactive(cmd, cwd=root, dry_run=not apply) != 0
    failed = failed or sync_gitmodules_for_local(config, root, remotes, apply) != 0
    failed = failed or commit_if_dirty(root, "chore: bootstrap local repository fleet", apply) != 0
    if set_origin and apply:
        run_interactive(["git", "push", "-u", "origin", root_repo.branch], cwd=root, dry_run=False)
    return 1 if failed else 0
