from __future__ import annotations

import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import ProjectConfig, Repository
from .shell import run, run_interactive, shlex_join
from .operations import backup_file, track_created_path, track_git_head, track_git_remote
from .graph import execute_levels

SEED_USER_NAME = "Repo Fleet Manager"
SEED_USER_EMAIL = "rfm@example.invalid"
ROOT_GITIGNORE_PATTERNS = [".repo-fleet/build/", ".repo-fleet/tmp/", ".repo-fleet/remotes/", ".repo-fleet/operations/", ".repo-fleet/lock"]
UPSTREAM_KEYS = ("mirror_source", "upstream_url", "source_url", "fork_from", "clone_url")
EXISTING_KEYS = ("existing_path", "local_source", "import_from")


@dataclass(slots=True)
class LocalPlanRow:
    path: str
    repo: str
    source_type: str
    remote_mode: str
    branch: str
    source: str | None
    local_remote: str
    worktree_exists: bool
    local_remote_exists: bool
    action: str


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


def _first_extra(repo: Repository, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = repo.extra.get(key)
        if value:
            return str(value)
    return None


def upstream_source_url(repo: Repository) -> str | None:
    return _first_extra(repo, UPSTREAM_KEYS)


def existing_source_path(repo: Repository, root: Path) -> Path | None:
    value = _first_extra(repo, EXISTING_KEYS)
    if not value:
        default_path = root if repo.is_root else root / repo.path
        if repo.source_type == "existing" and default_path.exists():
            return default_path.resolve()
        return None
    return resolve_under_root(root, value)


def repo_source_label(repo: Repository, root: Path) -> str | None:
    if repo.source_type == "upstream":
        return upstream_source_url(repo)
    if repo.source_type == "existing":
        path = existing_source_path(repo, root)
        return str(path) if path else None
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
    if apply:
        track_git_head(path)
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
        backup_file(gitignore)
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
            backup_file(readme)
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
            track_created_path(path)
            path.mkdir(parents=True, exist_ok=True)
    if not git_is_worktree(path):
        print(f"[INIT] {repo.path}: git init -b {repo.branch}")
        if apply and not (path / ".git").exists():
            track_created_path(path / ".git")
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
        previous_result = run(["git", "remote", "get-url", "origin"], cwd=path)
        previous = previous_result.stdout if previous_result.code == 0 else None
        if apply:
            track_git_remote(path, "origin", previous)
        if previous:
            code = run_interactive(["git", "remote", "set-url", "origin", url], cwd=path, dry_run=not apply)
        else:
            code = run_interactive(["git", "remote", "add", "origin", url], cwd=path, dry_run=not apply)
        if code != 0:
            return code
    return 0


def update_existing_mirror(target: Path, apply: bool) -> int:
    print(f"[UPDATE] local mirror: {target}")
    return run_interactive(["git", f"--git-dir={target}", "remote", "update", "--prune"], dry_run=not apply)


def push_existing_to_bare(repo: Repository, source: Path, target: Path, apply: bool) -> int:
    if not git_is_worktree(source):
        print(f"[WARN] {repo.path}: existing source is not a git worktree: {source}")
        return 1
    print(f"[IMPORT] {repo.repo}: {source} -> {target}")
    if not target.exists():
        ensure_parent(target, apply)
        code = run_interactive(["git", "init", "--bare", "-b", repo.branch, str(target)], cwd=source, dry_run=not apply)
        if code != 0:
            return code
    code = run_interactive(["git", "push", str(target), f"HEAD:{repo.branch}"], cwd=source, dry_run=not apply)
    if code != 0:
        return code
    # Push tags when present, but do not fail the whole import if there are none.
    run_interactive(["git", "push", str(target), "--tags"], cwd=source, dry_run=not apply)
    return 0


def ensure_bare_remote(repo: Repository, root: Path, remotes: Path, apply: bool, mirror_sources: bool = False, update_mirrors: bool = False) -> int:
    ensure_git_available()
    target = local_bare_path(repo, remotes)
    source_type = repo.source_type
    if target.exists():
        bare_check = run(["git", f"--git-dir={target}", "rev-parse", "--is-bare-repository"])
        if bare_check.code != 0 or bare_check.stdout != "true":
            print(f"[WARN] local remote path exists but is not a bare Git repository: {target}")
            return 1
        if source_type == "upstream" and (mirror_sources or update_mirrors):
            return update_existing_mirror(target, apply)
        print(f"[SKIP] local remote exists: {target}")
        return 0

    ensure_parent(target, apply)
    if apply:
        track_created_path(target)

    if source_type == "upstream":
        source = upstream_source_url(repo)
        if not source:
            print(f"[WARN] {repo.path}: source_type=upstream but no upstream_url/source_url/fork_from/clone_url configured")
            return 1
        print(f"[MIRROR] {repo.repo}: {source} -> {target}")
        return run_interactive(["git", "clone", "--mirror", source, str(target)], cwd=root, dry_run=not apply)

    if source_type == "existing":
        source_path = existing_source_path(repo, root)
        if source_path and source_path.exists():
            return push_existing_to_bare(repo, source_path, target, apply)
        print(f"[WARN] {repo.path}: source_type=existing but source path is missing; creating empty local bare remote")

    print(f"[INIT] local bare remote: {target}")
    code = run_interactive(["git", "init", "--bare", "-b", repo.branch, str(target)], cwd=root, dry_run=not apply)
    if code == 0 and apply:
        run(["git", f"--git-dir={target}", "symbolic-ref", "HEAD", f"refs/heads/{repo.branch}"])
    return code


def seed_bare_remote(repo: Repository, remotes: Path, apply: bool) -> int:
    if repo.source_type != "new":
        print(f"[SKIP] {repo.repo}: seed is only for source_type=new")
        return 0
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


def local_plan_rows(config: ProjectConfig, root: Path, remotes_override: str | None = None) -> list[LocalPlanRow]:
    remotes = remotes_dir(config, root, remotes_override)
    rows: list[LocalPlanRow] = []
    for repo in config.repositories:
        local_remote = local_bare_path(repo, remotes)
        worktree = root if repo.is_root else root / repo.path
        source = repo_source_label(repo, root)
        if repo.source_type == "new":
            action = "init-empty-local-remote + create worktree if missing"
        elif repo.source_type == "upstream":
            action = "mirror upstream into local bare remote + clone/submodule from local mirror"
        elif repo.source_type == "existing":
            action = "import existing local worktree into local bare remote + reuse/clone locally"
        else:
            action = "unknown"
        rows.append(LocalPlanRow(repo.path, repo.repo, repo.source_type, repo.remote_mode, repo.branch, source, str(local_remote), worktree.exists(), local_remote.exists(), action))
    return rows


def print_local_plan(config: ProjectConfig, root: Path, remotes_override: str | None = None, json_output: bool = False) -> int:
    rows = local_plan_rows(config, root, remotes_override)
    if json_output:
        import json
        print(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False))
        return 0
    print("Local materialization plan")
    print("=" * 42)
    print(f"root:          {root}")
    print(f"local remotes: {remotes_dir(config, root, remotes_override)}")
    print()
    for row in rows:
        print(f"- {row.path} -> {row.repo}")
        print(f"  source_type: {row.source_type} | remote_mode: {row.remote_mode} | branch: {row.branch}")
        print(f"  source:      {row.source or '-'}")
        print(f"  local bare:  {row.local_remote}")
        print(f"  exists:      worktree={row.worktree_exists} local_remote={row.local_remote_exists}")
        print(f"  action:      {row.action}")
    return 0


def create_local_remotes(
    config: ProjectConfig,
    root: Path,
    remotes_override: str | None,
    apply: bool,
    mirror_sources: bool,
    seed: bool = False,
    seed_root: bool = False,
    update_mirrors: bool = False,
    jobs: int = 1,
) -> int:
    remotes = remotes_dir(config, root, remotes_override)
    print(f"local remotes: {remotes}")

    def worker(repo: Repository) -> int:
        code = ensure_bare_remote(repo, root, remotes, apply, mirror_sources=mirror_sources, update_mirrors=update_mirrors)
        if code == 0 and seed and (seed_root or not repo.is_root):
            code = seed_bare_remote(repo, remotes, apply)
        return code

    results = execute_levels(config, worker, jobs=max(1, jobs))
    return 1 if any(code != 0 for _, code in results) else 0


def init_local_worktrees(config: ProjectConfig, root: Path, remotes_override: str | None, apply: bool, with_remotes: bool, set_origin: bool, jobs: int = 1) -> int:
    remotes = remotes_dir(config, root, remotes_override)
    failed = False
    if with_remotes or set_origin:
        failed = create_local_remotes(config, root, remotes_override, apply, mirror_sources=True, seed=False, jobs=jobs) != 0
    for repo in config.repositories:
        # Upstream repositories should be cloned from local mirrors; `init` is for new/existing local worktrees.
        if repo.source_type == "upstream":
            print(f"[SKIP] {repo.path}: upstream repo; use `rfm local clone` or `rfm local localize`")
            continue
        code = ensure_worktree_repo(repo, root, apply, set_origin=set_origin, remotes=remotes)
        failed = failed or code != 0
        if code == 0 and set_origin and apply:
            push = run_interactive(["git", "push", "-u", "origin", repo.branch], cwd=(root if repo.is_root else root / repo.path), dry_run=False)
            failed = failed or push != 0
    return 1 if failed else 0


def clone_one_from_local_bare(repo: Repository, root: Path, remotes: Path, apply: bool, as_submodule: bool = False) -> int:
    url = local_bare_url(repo, remotes)
    if repo.is_root:
        if git_is_worktree(root):
            print("[SKIP] root: already a git worktree")
            return 0
        if root.exists() and any(root.iterdir()):
            print("[SKIP] root: destination is not empty; use `rfm local localize` inside the cloned root")
            return 0
        print(f"[CLONE] root: {url} -> {root}")
        if apply:
            track_created_path(root)
        return run_interactive(["git", "-c", "protocol.file.allow=always", "clone", url, str(root)], cwd=root.parent, dry_run=not apply)
    path = root / repo.path
    if path.exists():
        print(f"[SKIP] {repo.path}: path exists")
        return 0
    ensure_parent(path, apply)
    if apply:
        track_created_path(path)
    if as_submodule:
        print(f"[SUBMODULE] {repo.path}: {url}")
        if apply:
            track_created_path(root / ".git" / "modules" / repo.path)
        return run_interactive(["git", "-c", "protocol.file.allow=always", "submodule", "add", "-b", repo.branch, url, repo.path], cwd=root, dry_run=not apply)
    print(f"[CLONE] {repo.path}: {url}")
    return run_interactive(["git", "-c", "protocol.file.allow=always", "clone", "-b", repo.branch, url, str(path)], cwd=root, dry_run=not apply)


def clone_local_repositories(config: ProjectConfig, root: Path, remotes_override: str | None, apply: bool, mirror_sources: bool, jobs: int = 1) -> int:
    remotes = remotes_dir(config, root, remotes_override)
    remotes_code = create_local_remotes(config, root, remotes_override, apply, mirror_sources=mirror_sources, seed=False, jobs=jobs)
    if remotes_code != 0:
        return remotes_code
    results = execute_levels(config, lambda repo: clone_one_from_local_bare(repo, root, remotes, apply, as_submodule=False), jobs=max(1, jobs))
    return 1 if any(code != 0 for _, code in results) else 0


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
    backup_file(root / ".gitmodules")
    (root / ".gitmodules").write_text(content, encoding="utf-8")
    return run_interactive(["git", "submodule", "sync", "--recursive"], cwd=root, dry_run=False, description="sync local submodule URLs")


def localize(config: ProjectConfig, root: Path, remotes_override: str | None, apply: bool, set_origin: bool = True, update_mirrors: bool = False, jobs: int = 1) -> int:
    """Materialize a cloned root into a fully local submodule workspace.\n\n    This is the high-level local workflow:\n    1. Create local bare remotes for every repository.\n       - new: empty/seeded bare remote.\n       - upstream: mirror external Git URL into local bare remote.\n       - existing: import local worktree into local bare remote.\n    2. Make sure the cloned root is a Git worktree.\n    3. Add missing submodules from local file:// remotes.\n    4. Point submodule origins to local remotes so the whole flow works offline.\n    """
    remotes = remotes_dir(config, root, remotes_override)
    root_repo = config.root_repository
    if root_repo is None:
        raise RuntimeError("config must include one root repository with path '.' or kind 'root'")
    print(f"root:          {root}")
    print(f"local remotes: {remotes}")
    failed = create_local_remotes(
        config, root, remotes_override, apply, mirror_sources=True, seed=False,
        update_mirrors=update_mirrors, jobs=jobs,
    ) != 0
    if failed:
        return 1

    for repo in config.submodules():
        if repo.source_type == "new":
            code = seed_bare_remote(repo, remotes, apply)
            if code != 0:
                return code

    code = ensure_worktree_repo(root_repo, root, apply, set_origin=set_origin, remotes=remotes)
    if code != 0:
        return code
    if set_origin and apply:
        code = run_interactive(["git", "push", "-u", "origin", root_repo.branch], cwd=root, dry_run=False, description=f"push root {root_repo.repo}")
        if code != 0:
            return code

    for repo in config.submodules():
        code = clone_one_from_local_bare(repo, root, remotes, apply, as_submodule=True)
        if code != 0:
            return code

    code = sync_gitmodules_for_local(config, root, remotes, apply)
    if code != 0:
        return code
    code = commit_if_dirty(root, "chore: localize repository fleet", apply)
    if code != 0:
        return code
    if set_origin and apply:
        code = run_interactive(["git", "push", "-u", "origin", root_repo.branch], cwd=root, dry_run=False, description=f"push localized root {root_repo.repo}")
        if code != 0:
            return code
    return 0


def bootstrap_local(config: ProjectConfig, root: Path, remotes_override: str | None, apply: bool, mirror_sources: bool, set_origin: bool, jobs: int = 1) -> int:
    # Backward-compatible alias. `mirror_sources` is kept for old CLI use; localize always honors repo source_type.
    return localize(config, root, remotes_override, apply, set_origin=set_origin, update_mirrors=mirror_sources, jobs=jobs)
