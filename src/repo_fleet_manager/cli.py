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


BASH_COMPLETION = r'''
# bash completion for Repo Fleet Manager (rfm)
# Install manually with:
#   rfm completion bash > ~/.local/share/bash-completion/completions/rfm

_rfm()
{
    local cur prev words cword
    if declare -F _init_completion >/dev/null 2>&1; then
        _init_completion -n : || return
    else
        words=("${COMP_WORDS[@]}")
        cword=$COMP_CWORD
        cur="${COMP_WORDS[COMP_CWORD]}"
        prev="${COMP_WORDS[COMP_CWORD-1]}"
    fi

    local commands="doctor catalog repos submodules git source compose images docs completion"
    local global_opts="--help --version --config --root"

    case "$prev" in
        --config)
            if declare -F _filedir >/dev/null 2>&1; then
                _filedir '@(json)'
            else
                COMPREPLY=( $(compgen -f -- "$cur") )
            fi
            return
            ;;
        --root)
            if declare -F _filedir >/dev/null 2>&1; then
                _filedir -d
            else
                COMPREPLY=( $(compgen -d -- "$cur") )
            fi
            return
            ;;
        --provider)
            COMPREPLY=( $(compgen -W "github gitlab" -- "$cur") )
            return
            ;;
        --visibility)
            COMPREPLY=( $(compgen -W "private public" -- "$cur") )
            return
            ;;
        completion)
            COMPREPLY=( $(compgen -W "bash fish" -- "$cur") )
            return
            ;;
    esac

    local cmd="" token i skip_next=0
    for ((i=1; i<cword; i++)); do
        token="${words[i]}"
        if (( skip_next )); then
            skip_next=0
            continue
        fi
        case "$token" in
            --config|--root|--provider|--namespace|--visibility)
                skip_next=1
                continue
                ;;
            --*)
                continue
                ;;
        esac
        case " $commands " in
            *" $token "*) cmd="$token"; break ;;
        esac
    done

    if [[ -z "$cmd" ]]; then
        COMPREPLY=( $(compgen -W "$commands $global_opts" -- "$cur") )
        return
    fi

    local opts action=""
    case "$cmd" in
        doctor)
            opts="--help --config --root"
            ;;
        catalog)
            opts="--help --config --root --json"
            ;;
        repos)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "audit" || "${words[i]}" == "create" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "audit create --help --config --root" -- "$cur") )
                return
            fi
            case "$action" in
                audit) opts="--help --provider --namespace --check-remote --json" ;;
                create) opts="--help --provider --namespace --visibility --apply" ;;
            esac
            ;;
        submodules)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "sync" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "sync --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --provider --namespace --apply"
            ;;
        git)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "status" || "${words[i]}" == "pull" || "${words[i]}" == "push" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "status pull push --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --config --root --apply --no-root"
            ;;
        source)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "fingerprint" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "fingerprint --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --write"
            ;;
        compose)
            for ((i=1; i<cword; i++)); do
                case "${words[i]}" in
                    ps|up|down|build|pull|logs) action="${words[i]}" ;;
                esac
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "ps up down build pull logs --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --apply"
            ;;
        images)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "verify" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "verify --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --json"
            ;;
        docs)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "validate-links" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "validate-links --help --config --root" -- "$cur") )
                return
            fi
            opts="--help"
            ;;
        completion)
            opts="bash fish --help"
            ;;
    esac

    COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
}

complete -F _rfm rfm
'''

FISH_COMPLETION = r'''
# fish completion for Repo Fleet Manager (rfm)
# Install manually with:
#   rfm completion fish > ~/.config/fish/completions/rfm.fish

complete -c rfm -f
complete -c rfm -s h -l help -d 'Show help'
complete -c rfm -l version -d 'Show version'
complete -c rfm -l config -r -d 'Path to repo-fleet.json'
complete -c rfm -l root -r -a '(__fish_complete_directories)' -d 'Repository root'

complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules git source compose images docs completion' -a doctor -d 'Check dependencies and config'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules git source compose images docs completion' -a catalog -d 'Print repository catalog'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules git source compose images docs completion' -a repos -d 'Repository provider operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules git source compose images docs completion' -a submodules -d 'Submodule operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules git source compose images docs completion' -a git -d 'Run git across root and submodules'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules git source compose images docs completion' -a source -d 'Source/image metadata operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules git source compose images docs completion' -a compose -d 'Run compose operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules git source compose images docs completion' -a images -d 'Verify image labels'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules git source compose images docs completion' -a docs -d 'Documentation utilities'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules git source compose images docs completion' -a completion -d 'Print shell completion script'

complete -c rfm -n '__fish_seen_subcommand_from completion' -a bash -d 'Print Bash completion'
complete -c rfm -n '__fish_seen_subcommand_from completion' -a fish -d 'Print Fish completion'

complete -c rfm -n '__fish_seen_subcommand_from catalog' -l json -d 'Print JSON output'

complete -c rfm -n '__fish_seen_subcommand_from repos; and not __fish_seen_subcommand_from audit create' -a audit -d 'Audit .gitmodules and remotes'
complete -c rfm -n '__fish_seen_subcommand_from repos; and not __fish_seen_subcommand_from audit create' -a create -d 'Create repositories'
complete -c rfm -n '__fish_seen_subcommand_from repos' -l provider -r -a 'github gitlab' -d 'Repository provider'
complete -c rfm -n '__fish_seen_subcommand_from repos' -l namespace -r -d 'Provider namespace/group/org'
complete -c rfm -n '__fish_seen_subcommand_from audit' -l check-remote -d 'Check remote existence'
complete -c rfm -n '__fish_seen_subcommand_from audit' -l json -d 'Print JSON output'
complete -c rfm -n '__fish_seen_subcommand_from create' -l visibility -r -a 'private public' -d 'Repository visibility'
complete -c rfm -n '__fish_seen_subcommand_from create' -l apply -d 'Apply changes'

complete -c rfm -n '__fish_seen_subcommand_from submodules; and not __fish_seen_subcommand_from sync' -a sync -d 'Sync .gitmodules and origins'
complete -c rfm -n '__fish_seen_subcommand_from submodules' -l provider -r -a 'github gitlab' -d 'Repository provider'
complete -c rfm -n '__fish_seen_subcommand_from submodules' -l namespace -r -d 'Provider namespace/group/org'
complete -c rfm -n '__fish_seen_subcommand_from submodules' -l apply -d 'Apply changes'

complete -c rfm -n '__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status pull push' -a status -d 'Run git status'
complete -c rfm -n '__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status pull push' -a pull -d 'Run git pull'
complete -c rfm -n '__fish_seen_subcommand_from git; and not __fish_seen_subcommand_from status pull push' -a push -d 'Run git push'
complete -c rfm -n '__fish_seen_subcommand_from git' -l apply -d 'Apply changes'
complete -c rfm -n '__fish_seen_subcommand_from git' -l no-root -d 'Skip root repository'

complete -c rfm -n '__fish_seen_subcommand_from source; and not __fish_seen_subcommand_from fingerprint' -a fingerprint -d 'Compute source digests'
complete -c rfm -n '__fish_seen_subcommand_from fingerprint' -l write -d 'Write metadata files'

complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a ps -d 'Compose ps'
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a up -d 'Compose up'
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a down -d 'Compose down'
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a build -d 'Compose build'
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a pull -d 'Compose pull'
complete -c rfm -n '__fish_seen_subcommand_from compose; and not __fish_seen_subcommand_from ps up down build pull logs' -a logs -d 'Compose logs'
complete -c rfm -n '__fish_seen_subcommand_from compose' -l apply -d 'Apply changes'

complete -c rfm -n '__fish_seen_subcommand_from images; and not __fish_seen_subcommand_from verify' -a verify -d 'Verify image labels'
complete -c rfm -n '__fish_seen_subcommand_from verify' -l json -d 'Print JSON output'

complete -c rfm -n '__fish_seen_subcommand_from docs; and not __fish_seen_subcommand_from validate-links' -a validate-links -d 'Validate Markdown links'
'''


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", help="Path to repo-fleet.json. Defaults to nearest repo-fleet.json above cwd.")
    parser.add_argument("--root", default=".", help="Repository root. Default: current directory.")


def cmd_completion(args: argparse.Namespace) -> int:
    if args.shell == "bash":
        print(BASH_COMPLETION.strip())
    elif args.shell == "fish":
        print(FISH_COMPLETION.strip())
    else:  # argparse prevents this branch.
        raise ValueError(f"Unsupported shell: {args.shell}")
    return 0


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

    p = sub.add_parser("completion", help="Print shell completion script.")
    p.add_argument("shell", choices=["bash", "fish"], help="Shell to generate completion for.")
    p.set_defaults(func=cmd_completion)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
