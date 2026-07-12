from __future__ import annotations

import configparser
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import ProjectConfig, Repository
from .shell import command_exists, run, run_interactive, shlex_join


@dataclass(slots=True)
class RepoAuditRow:
    path: str
    repo: str
    provider: str
    expected_url: str
    gitmodules_url: str | None
    root_config: bool
    local_path: bool
    git_worktree: bool
    gitdir_type: str
    branch: str | None
    origin: str | None
    remote_exists: str | None
    issues: list[str]


def git_output(args: list[str], cwd: Path) -> str | None:
    result = run(["git", *args], cwd=cwd)
    return result.stdout if result.code == 0 else None


def parse_gitmodules(root: Path) -> dict[str, str]:
    path = root / ".gitmodules"
    if not path.exists():
        return {}
    parser = configparser.RawConfigParser()
    parser.read(path, encoding="utf-8")
    result: dict[str, str] = {}
    for section in parser.sections():
        if not section.startswith("submodule "):
            continue
        sub_path = parser.get(section, "path", fallback="").strip()
        url = parser.get(section, "url", fallback="").strip()
        if sub_path:
            result[sub_path] = url
    return result


def parse_root_submodule_config(root: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    out = git_output(["config", "--get-regexp", r"^submodule\..*\.(path|url)$"], root)
    if not out:
        return result
    by_name: dict[str, dict[str, str]] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        key, value = line.split(maxsplit=1)
        if not key.startswith("submodule."):
            continue
        body = key[len("submodule."):]
        name, _, field = body.rpartition(".")
        if field in {"path", "url"}:
            by_name.setdefault(name, {})[field] = value
    for item in by_name.values():
        if item.get("path"):
            result[item["path"]] = item
    return result


def detect_gitdir_type(path: Path) -> str:
    marker = path / ".git"
    if marker.is_file():
        return "gitfile-submodule"
    if marker.is_dir():
        return "embedded-gitdir"
    return "missing"


def provider_view_command(provider_name: str, cli: str, namespace: str, repo: str) -> list[str]:
    full = f"{namespace}/{repo}"
    if provider_name == "github":
        return [cli, "repo", "view", full]
    if provider_name == "gitlab":
        return [cli, "repo", "view", full]
    return [cli, "repo", "view", full]


def provider_create_command(provider_name: str, cli: str, namespace: str, repo: str, visibility: str, description: str) -> list[str]:
    full = f"{namespace}/{repo}"
    visibility_flag = "--private" if visibility == "private" else "--public"
    if provider_name == "github":
        return [cli, "repo", "create", full, visibility_flag, "--disable-wiki", "--description", description]
    if provider_name == "gitlab":
        return [cli, "repo", "create", full, visibility_flag, "--description", description]
    return [cli, "repo", "create", full, visibility_flag, "--description", description]


def remote_exists(provider_name: str, cli: str, namespace: str, repo: str, root: Path) -> str:
    if not command_exists(cli):
        return "cli-missing"
    result = run(provider_view_command(provider_name, cli, namespace, repo), cwd=root)
    return "yes" if result.code == 0 else "no-or-auth-failed"


def audit(config: ProjectConfig, root: Path, provider_override: str | None = None, namespace: str | None = None, check_remote: bool = False) -> dict:
    gitmodules = parse_gitmodules(root)
    root_cfg = parse_root_submodule_config(root)
    rows: list[RepoAuditRow] = []
    for repo in config.submodules():
        provider = config.provider_for(repo, provider_override, namespace)
        full_path = root / repo.path
        expected = provider.expected_url(repo.repo)
        exists = full_path.exists()
        worktree = False
        branch = None
        origin = None
        gitdir_type = "missing-path" if not exists else detect_gitdir_type(full_path)
        issues: list[str] = []
        if exists:
            check = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=full_path)
            worktree = check.code == 0 and check.stdout == "true"
            if worktree:
                branch = git_output(["branch", "--show-current"], full_path)
                origin = git_output(["remote", "get-url", "origin"], full_path)
        gm_url = gitmodules.get(repo.path)
        remote_state = remote_exists(provider.name, provider.cli, provider.namespace, repo.repo, root) if check_remote else None
        if gm_url != expected:
            issues.append("gitmodules-url-mismatch")
        if repo.path not in root_cfg:
            issues.append("submodule-not-initialized-in-root-config")
        if not exists:
            issues.append("local-path-missing")
        elif not worktree:
            issues.append("not-a-git-worktree")
        if gitdir_type == "embedded-gitdir":
            issues.append("embedded-gitdir-use-git-submodule-absorbgitdirs")
        if origin and origin != expected:
            issues.append("origin-url-mismatch")
        if not origin and worktree:
            issues.append("origin-missing")
        if branch == "master" and repo.branch == "main":
            issues.append("branch-master-consider-main")
        if remote_state in {"cli-missing", "no-or-auth-failed"}:
            issues.append(f"remote-{remote_state}")
        rows.append(RepoAuditRow(repo.path, repo.repo, provider.name, expected, gm_url, repo.path in root_cfg, exists, worktree, gitdir_type, branch, origin, remote_state, issues))
    root_repo = config.root_repository
    root_provider = config.provider_for(root_repo, provider_override, namespace) if root_repo else None
    root_origin = git_output(["remote", "get-url", "origin"], root)
    root_expected = root_provider.expected_url(root_repo.repo) if root_provider and root_repo else None
    root_issues: list[str] = []
    if root_expected and root_origin != root_expected:
        root_issues.append("root-origin-url-mismatch")
    return {
        "project": config.project.get("name"),
        "root": str(root),
        "config": str(config.path),
        "root_origin": root_origin,
        "root_expected_url": root_expected,
        "root_issues": root_issues,
        "submodule_count": len(rows),
        "issue_count": sum(1 for row in rows if row.issues) + len(root_issues),
        "rows": [asdict(row) for row in rows],
    }


def print_audit_report(report: dict) -> int:
    print("Repository/Submodule Audit")
    print("=" * 36)
    print(f"project:      {report.get('project') or '-'}")
    print(f"root:         {report['root']}")
    print(f"config:       {report['config']}")
    print(f"root origin:  {report.get('root_origin') or '-'}")
    print(f"root expect:  {report.get('root_expected_url') or '-'}")
    if report.get("root_issues"):
        print(f"root issues:  {', '.join(report['root_issues'])}")
    print(f"submodules:   {report['submodule_count']}")
    print(f"issues:       {report['issue_count']}")
    print()
    for idx, row in enumerate(report["rows"], start=1):
        marker = "OK" if not row["issues"] else "WARN"
        print(f"[{idx:02d}] {marker} {row['path']} -> {row['repo']} ({row['provider']})")
        print(f"     expected:    {row['expected_url']}")
        print(f"     .gitmodules: {row['gitmodules_url'] or '-'}")
        print(f"     origin:      {row['origin'] or '-'}")
        print(f"     branch:      {row['branch'] or '-'} | worktree: {row['git_worktree']} | gitdir: {row['gitdir_type']}")
        if row["remote_exists"] is not None:
            print(f"     remote:      {row['remote_exists']}")
        if row["issues"]:
            print(f"     issues:      {', '.join(row['issues'])}")
        print()
    return 0 if report["issue_count"] == 0 else 2


def sync_submodules(config: ProjectConfig, root: Path, provider_override: str | None, namespace: str | None, apply: bool) -> int:
    lines: list[str] = []
    for repo in config.submodules():
        provider = config.provider_for(repo, provider_override, namespace)
        url = provider.expected_url(repo.repo)
        lines.extend([f'[submodule "{repo.path}"]', f"\tpath = {repo.path}", f"\turl = {url}"])
    content = "\n".join(lines) + "\n"
    gitmodules = root / ".gitmodules"
    if not apply:
        print("[DRY-RUN] Would write .gitmodules:")
        print(content)
        for repo in config.submodules():
            provider = config.provider_for(repo, provider_override, namespace)
            path = root / repo.path
            if path.exists():
                print(f"[DRY-RUN] git -C {repo.path} remote set-url origin {provider.expected_url(repo.repo)}")
        print("[DRY-RUN] git submodule sync --recursive")
        return 0
    if gitmodules.exists():
        backup = root / f".gitmodules.backup.{time.strftime('%Y%m%d%H%M%S')}"
        backup.write_text(gitmodules.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[INFO] Backup written: {backup.name}")
    gitmodules.write_text(content, encoding="utf-8")
    for repo in config.submodules():
        provider = config.provider_for(repo, provider_override, namespace)
        path = root / repo.path
        if not path.exists():
            continue
        if run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path).code == 0:
            result = run(["git", "remote", "set-url", "origin", provider.expected_url(repo.repo)], cwd=path)
            if result.code != 0:
                run(["git", "remote", "add", "origin", provider.expected_url(repo.repo)], cwd=path, check=True)
    run(["git", "submodule", "sync", "--recursive"], cwd=root, check=True)
    print("[OK] .gitmodules and local submodule origin URLs synchronized.")
    return 0


def create_repositories(config: ProjectConfig, root: Path, provider_override: str | None, namespace: str | None, visibility: str, apply: bool) -> int:
    repositories = config.repositories
    failed = False
    for repo in repositories:
        provider = config.provider_for(repo, provider_override, namespace)
        desc = repo.description or f"{config.project.get('name', 'platform')} repository: {repo.repo}"
        view_cmd = provider_view_command(provider.name, provider.cli, provider.namespace, repo.repo)
        create_cmd = provider_create_command(provider.name, provider.cli, provider.namespace, repo.repo, visibility, desc)
        if not command_exists(provider.cli):
            print(f"[WARN] CLI missing for {provider.name}: {provider.cli}")
            print(f"[DRY-RUN] {shlex_join(create_cmd)}")
            failed = failed or apply
            continue
        state = run(view_cmd, cwd=root)
        if state.code == 0:
            print(f"[SKIP] {provider.name}:{provider.namespace}/{repo.repo} exists")
            continue
        code = run_interactive(create_cmd, cwd=root, dry_run=not apply)
        if code != 0:
            failed = True
    return 1 if failed else 0


def git_foreach(config: ProjectConfig, root: Path, action: str, apply: bool, include_root: bool = True) -> int:
    targets = list(config.repositories)
    if not include_root:
        targets = [repo for repo in targets if not repo.is_root]
    failed = False
    for repo in targets:
        path = root / repo.path
        if not path.exists():
            print(f"[SKIP] {repo.path}: path missing")
            continue
        if run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path).code != 0:
            print(f"[SKIP] {repo.path}: not a git worktree")
            continue
        branch = git_output(["branch", "--show-current"], path) or repo.branch
        if action == "pull":
            cmd = ["git", "pull", "--ff-only"]
        elif action == "push":
            if not branch:
                print(f"[SKIP] {repo.path}: detached head")
                continue
            cmd = ["git", "push", "-u", "origin", branch]
        elif action == "status":
            print(f"\n== {repo.path} ==")
            cmd = ["git", "status", "--short", "--branch"]
        else:
            raise ValueError(action)
        code = run_interactive(cmd, cwd=path, dry_run=False if action == "status" else not apply)
        failed = failed or code != 0
    return 1 if failed else 0
