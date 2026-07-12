#!/usr/bin/env python3
from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

CATALOG: list[tuple[str, str]] = [
    ("services/api-gateway", "goftaroo-api-gateway"),
    ("services/identity-service", "goftaroo-identity-service"),
    ("services/tenant-service", "goftaroo-tenant-service"),
    ("services/device-registry-service", "goftaroo-device-registry-service"),
    ("services/subscription-service", "goftaroo-subscription-service"),
    ("services/billing-service", "goftaroo-billing-service"),
    ("services/usage-metering-service", "goftaroo-usage-metering-service"),
    ("services/voice-session-service", "goftaroo-voice-session-service"),
    ("services/conversation-service", "goftaroo-conversation-service"),
    ("services/speech-provider-service", "goftaroo-speech-provider-service"),
    ("services/llm-gateway-service", "goftaroo-llm-gateway-service"),
    ("services/agent-orchestrator-service", "goftaroo-agent-orchestrator-service"),
    ("services/skill-registry-service", "goftaroo-skill-registry-service"),
    ("services/notification-service", "goftaroo-notification-service"),
    ("services/audit-export-worker-service", "goftaroo-audit-export-worker-service"),
    ("clients/kmp-client", "goftaroo-kmp-client"),
    ("clients/admin-dashboard", "goftaroo-admin-dashboard"),
    ("clients/user-dashboard", "goftaroo-user-dashboard"),
    ("clients/embedded-runtime", "goftaroo-embedded-runtime"),
    ("packages/shared-contracts", "goftaroo-shared-contracts"),
    ("infra/platform-infra", "goftaroo-platform-infra"),
]
ROOT_REPO = "goftaroo-platform"


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def git_out(args: list[str], cwd: Path) -> str | None:
    code, out, _ = run(["git", *args], cwd)
    return out if code == 0 else None


def expected_url(owner: str, repo: str) -> str:
    return f"git@github.com:{owner}/{repo}.git"


def short_mirror_name(repo: str) -> str:
    return repo.removeprefix("goftaroo-") + ".git"


def parse_gitmodules(root: Path) -> dict[str, str]:
    path = root / ".gitmodules"
    if not path.exists():
        return {}
    parser = configparser.RawConfigParser()
    parser.read(path)
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
    code, out, _ = run(["git", "config", "--get-regexp", r"^submodule\..*\.(path|url)$"], root)
    if code != 0:
        return result
    for line in out.splitlines():
        if not line.strip():
            continue
        key, value = line.split(maxsplit=1)
        match = re.match(r"submodule\.(?P<name>.+)\.(?P<field>path|url)$", key)
        if not match:
            continue
        name = match.group("name")
        field = match.group("field")
        result.setdefault(name, {})[field] = value
    by_path: dict[str, dict[str, str]] = {}
    for item in result.values():
        sub_path = item.get("path")
        if sub_path:
            by_path[sub_path] = item
    return by_path


def detect_gitdir_type(path: Path) -> str:
    git_marker = path / ".git"
    if git_marker.is_file():
        return "gitfile"
    if git_marker.is_dir():
        return "embedded-gitdir"
    return "missing"


def github_exists(owner: str, repo: str, root: Path) -> str:
    code, _, _ = run(["gh", "repo", "view", f"{owner}/{repo}"], root)
    if code == 0:
        return "yes"
    return "no-or-auth-failed"


@dataclass
class Row:
    path: str
    repo: str
    expected_url: str
    gitmodules_url: str | None
    root_config: bool
    local_path: bool
    git_worktree: bool
    gitdir_type: str
    branch: str | None
    origin: str | None
    local_mirror: bool
    github: str | None
    issues: list[str]


def build_report(root: Path, owner: str, check_github: bool) -> list[Row]:
    gitmodules = parse_gitmodules(root)
    config_by_path = parse_root_submodule_config(root)
    rows: list[Row] = []

    for sub_path, repo in CATALOG:
        full_path = root / sub_path
        exp_url = expected_url(owner, repo)
        gm_url = gitmodules.get(sub_path)
        cfg = config_by_path.get(sub_path)
        path_exists = full_path.exists()
        worktree = False
        branch = None
        origin = None
        gitdir_type = "missing-path" if not path_exists else detect_gitdir_type(full_path)
        issues: list[str] = []

        if path_exists:
            code, out, _ = run(["git", "rev-parse", "--is-inside-work-tree"], full_path)
            worktree = code == 0 and out == "true"
            branch = git_out(["branch", "--show-current"], full_path) if worktree else None
            origin = git_out(["remote", "get-url", "origin"], full_path) if worktree else None

        mirror = (root / "_git-remotes" / short_mirror_name(repo)).exists()
        gh_state = github_exists(owner, repo, root) if check_github else None

        if gm_url != exp_url:
            issues.append("gitmodules-url-mismatch")
        if sub_path not in config_by_path:
            issues.append("submodule-not-initialized-in-root-config")
        if not path_exists:
            issues.append("local-path-missing")
        elif not worktree:
            issues.append("not-a-git-worktree")
        if gitdir_type == "embedded-gitdir":
            issues.append("embedded-gitdir-use-absorbgitdirs")
        if origin and origin != exp_url:
            issues.append("origin-url-mismatch")
        if not origin and worktree:
            issues.append("origin-missing")
        if branch == "master":
            issues.append("branch-master-consider-main")
        if not mirror:
            issues.append("local-mirror-missing")
        if gh_state == "no-or-auth-failed":
            issues.append("github-repo-missing-or-gh-auth-failed")

        rows.append(Row(
            path=sub_path,
            repo=repo,
            expected_url=exp_url,
            gitmodules_url=gm_url,
            root_config=bool(cfg),
            local_path=path_exists,
            git_worktree=worktree,
            gitdir_type=gitdir_type,
            branch=branch,
            origin=origin,
            local_mirror=mirror,
            github=gh_state,
            issues=issues,
        ))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Goftaroo GitHub repository, submodule, and local mirror state.")
    parser.add_argument("--owner", default="mhassanzadeh", help="GitHub owner/org. Default: mhassanzadeh")
    parser.add_argument("--root", default=".", help="Repository root. Default: current directory")
    parser.add_argument("--github-check", action="store_true", help="Use gh repo view to check GitHub repository existence")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    rows = build_report(root, args.owner, args.github_check)

    root_origin = git_out(["remote", "get-url", "origin"], root)
    root_branch = git_out(["branch", "--show-current"], root)
    root_expected = expected_url(args.owner, ROOT_REPO)
    root_issues: list[str] = []
    if root_origin != root_expected:
        root_issues.append("root-origin-url-mismatch")

    payload = {
        "root": str(root),
        "owner": args.owner,
        "root_repo": ROOT_REPO,
        "root_expected_url": root_expected,
        "root_origin": root_origin,
        "root_branch": root_branch,
        "root_issues": root_issues,
        "submodule_count": len(rows),
        "issue_count": sum(1 for row in rows if row.issues),
        "rows": [asdict(row) for row in rows],
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if not payload["issue_count"] and not root_issues else 2

    print("Goftaroo GitHub/Submodule Audit")
    print("=" * 38)
    print(f"root:              {root}")
    print(f"owner:             {args.owner}")
    print(f"root origin:       {root_origin or '-'}")
    print(f"root expected:     {root_expected}")
    print(f"root branch:       {root_branch or '-'}")
    print(f"submodules:        {len(rows)}")
    print(f"submodules issues: {payload['issue_count']}")
    if root_issues:
        print(f"root issues:       {', '.join(root_issues)}")
    print()

    for idx, row in enumerate(rows, start=1):
        marker = "OK" if not row.issues else "WARN"
        print(f"[{idx:02d}] {marker} {row.path} -> {row.repo}")
        print(f"     .gitmodules: {row.gitmodules_url or '-'}")
        print(f"     origin:      {row.origin or '-'}")
        print(f"     root config: {row.root_config} | path: {row.local_path} | worktree: {row.git_worktree} | gitdir: {row.gitdir_type}")
        print(f"     branch:      {row.branch or '-'} | _git-remotes: {row.local_mirror} | github: {row.github or 'not-checked'}")
        if row.issues:
            print(f"     issues:      {', '.join(row.issues)}")
        print()

    if payload["issue_count"] or root_issues:
        print("Recommended next commands:")
        print("  ./scripts/replace-submodule-remotes.sh", args.owner)
        print("  git submodule init")
        print("  ./scripts/normalize-audit-worker-submodule.sh --apply")
        print("  ./scripts/goftaroo-github-remote-sync.sh", args.owner, "--check")
        print("  ./scripts/goftaroo-github-remote-audit.py --owner", args.owner)
        return 2

    print("All catalogued repositories look consistent locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
