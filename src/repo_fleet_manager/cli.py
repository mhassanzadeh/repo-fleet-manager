from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .compose import run_compose
from .config import load_config
from .docs import validate_links
from .fingerprint import build_metadata, write_compose_override, write_metadata
from .gitops import audit, create_repositories, git_foreach, print_audit_report, sync_submodules
from .images import verify_images
from .shell import command_exists


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", help="Path to repo-fleet.json. Defaults to nearest repo-fleet.json above cwd.")
    parser.add_argument("--root", default=".", help="Repository root. Default: current directory.")


def cmd_doctor(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    root = Path(args.root).resolve()
    required = ["git", "python3"]
    optional = ["docker", "podman", "podman-compose", "gh", "glab"]
    print(f"Repo Fleet Manager {__version__}")
    print(f"config: {cfg.path}")
    print(f"root:   {root}")
    print("\nRequired commands:")
    failed = False
    for cmd in required:
        ok = command_exists(cmd)
        failed = failed or not ok
        print(f" - {cmd:<14} {'OK' if ok else 'MISSING'}")
    print("\nOptional commands:")
    for cmd in optional:
        print(f" - {cmd:<14} {'OK' if command_exists(cmd) else 'missing'}")
    print("\nConfig:")
    print(f" - project:       {cfg.project.get('name')}")
    print(f" - providers:     {', '.join(cfg.providers)}")
    print(f" - repositories:  {len(cfg.repositories)}")
    print(f" - submodules:    {len(cfg.submodules())}")
    print(f" - services:      {len(cfg.services())}")
    return 1 if failed else 0


def cmd_catalog(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    rows = [asdict(repo) for repo in cfg.repositories]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    print("PATH                                REPOSITORY                              KIND       PROVIDER")
    print("-" * 98)
    for repo in cfg.repositories:
        print(f"{repo.path:<35} {repo.repo:<39} {repo.kind:<10} {repo.provider or cfg.default_provider_name}")
    return 0


def cmd_repos_audit(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    report = audit(cfg, Path(args.root).resolve(), args.provider, args.namespace, args.check_remote)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["issue_count"] == 0 else 2
    return print_audit_report(report)


def cmd_repos_create(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    return create_repositories(cfg, Path(args.root).resolve(), args.provider, args.namespace, args.visibility, args.apply)


def cmd_submodules_sync(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    return sync_submodules(cfg, Path(args.root).resolve(), args.provider, args.namespace, args.apply)


def cmd_git(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    return git_foreach(cfg, Path(args.root).resolve(), args.git_action, args.apply, include_root=not args.no_root)


def cmd_source_fingerprint(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    root = Path(args.root).resolve()
    metadata = build_metadata(cfg, root)
    if args.write:
        build_dir = write_metadata(cfg, root, metadata)
        override = write_compose_override(cfg, root, metadata)
        print(f"[OK] wrote {build_dir / 'metadata.json'}")
        print(f"[OK] wrote {build_dir / 'compose.env'}")
        print(f"[OK] wrote {override}")
    else:
        print(json.dumps(metadata, indent=2, ensure_ascii=False))
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    extra = args.extra or []
    if extra and extra[0] == "--":
        extra = extra[1:]
    return run_compose(cfg, Path(args.root).resolve(), args.compose_action, extra, args.apply)


def cmd_images_verify(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    return verify_images(cfg, Path(args.root).resolve(), args.json)


def cmd_docs_validate(args: argparse.Namespace) -> int:
    return validate_links(Path(args.root).resolve())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rfm", description="Config-driven manager for large multi-repository/submodule projects.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="Check local dependencies and config summary.")
    add_common(p); p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("catalog", help="Print repository catalog from config.")
    add_common(p); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_catalog)

    repos = sub.add_parser("repos", help="Repository provider operations.")
    add_common(repos); repos_sub = repos.add_subparsers(dest="repos_action", required=True)
    p = repos_sub.add_parser("audit", help="Audit .gitmodules, local remotes and optional remote existence.")
    p.add_argument("--provider", choices=["github", "gitlab"]); p.add_argument("--namespace"); p.add_argument("--check-remote", action="store_true"); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_repos_audit)
    p = repos_sub.add_parser("create", help="Create missing repositories through gh/glab. Dry-run by default.")
    p.add_argument("--provider", choices=["github", "gitlab"]); p.add_argument("--namespace"); p.add_argument("--visibility", choices=["private", "public"], default="private"); p.add_argument("--apply", action="store_true"); p.set_defaults(func=cmd_repos_create)

    p = sub.add_parser("submodules", help="Submodule operations.")
    add_common(p); subm = p.add_subparsers(dest="submodules_action", required=True)
    sp = subm.add_parser("sync", help="Rewrite .gitmodules and local origin URLs from config. Dry-run by default.")
    sp.add_argument("--provider", choices=["github", "gitlab"]); sp.add_argument("--namespace"); sp.add_argument("--apply", action="store_true"); sp.set_defaults(func=cmd_submodules_sync)

    p = sub.add_parser("git", help="Run git operations across root + submodules.")
    add_common(p); p.add_argument("git_action", choices=["status", "pull", "push"]); p.add_argument("--apply", action="store_true"); p.add_argument("--no-root", action="store_true"); p.set_defaults(func=cmd_git)

    p = sub.add_parser("source", help="Source/image metadata operations.")
    add_common(p); source_sub = p.add_subparsers(dest="source_action", required=True)
    sp = source_sub.add_parser("fingerprint", help="Compute service source digests; write compose metadata with --write.")
    sp.add_argument("--write", action="store_true"); sp.set_defaults(func=cmd_source_fingerprint)

    p = sub.add_parser("compose", help="Run compose operations with generated source metadata.")
    add_common(p); p.add_argument("compose_action", choices=["ps", "up", "down", "build", "pull", "logs"]); p.add_argument("--apply", action="store_true", help="Required for state-changing compose commands."); p.add_argument("extra", nargs=argparse.REMAINDER); p.set_defaults(func=cmd_compose)

    p = sub.add_parser("images", help="Verify built image labels against source fingerprints.")
    add_common(p); img_sub = p.add_subparsers(dest="images_action", required=True)
    sp = img_sub.add_parser("verify", help="Compare image labels with current fingerprint metadata.")
    sp.add_argument("--json", action="store_true"); sp.set_defaults(func=cmd_images_verify)

    p = sub.add_parser("docs", help="Documentation utilities.")
    add_common(p); docs_sub = p.add_subparsers(dest="docs_action", required=True)
    sp = docs_sub.add_parser("validate-links", help="Validate local Markdown links.")
    sp.set_defaults(func=cmd_docs_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
