from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from importlib.resources import files

from . import __version__
from .compose import run_compose
from .backup import create_backup, list_backups, restore_backup, verify_backup
from .cache import bootstrap_from_cache, export_cache, import_cache, list_caches, verify_cache
from .config import find_config, load_config, load_raw_config
from .docs import validate_links
from .fingerprint import build_metadata, write_compose_override, write_metadata
from .gitops import audit, create_repositories, git_foreach, print_audit_report, publish_repositories, sync_submodules
from .localops import bootstrap_local, clone_local_repositories, create_local_remotes, init_local_worktrees, localize, print_local_plan
from .images import verify_images
from .shell import command_exists
from .service_catalog import load_service_catalog, render_catalog, summary as catalog_summary
from .schema import CURRENT_SCHEMA_VERSION, ConfigValidationError, ValidationIssue, migrate_config_data, validate_config_data, validate_or_raise, write_migrated_config
from .profiles import ConfigResolutionError
from .scaffold import (
    DEFAULT_LOCK_FILE,
    SUPPORTED_REPOSITORY_TEMPLATES,
    init_project,
    scaffold_repository,
    verify_bootstrap_lock,
    write_bootstrap_lock,
)
from .operations import SafetyError, backup_file, list_operation_files, load_operation, lock_path, mutation_context, operations_dir
from .provider import auth_report, fork_repositories, mirror_repositories, reconcile_repositories, require_provider_auth
from .graph import render_graph
from .safety import assert_workspace_safe, workspace_safety_report


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

    local commands="doctor catalog repos submodules local git source compose images docs completion"
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
            COMPREPLY=( $(compgen -W "github gitlab local" -- "$cur") )
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
            opts="--help --config --root --view --format --json --output --catalog-file --priority --status --check-evidence"
            ;;
        repos)
            for ((i=1; i<cword; i++)); do
                [[ "${words[i]}" == "audit" || "${words[i]}" == "create" || "${words[i]}" == "publish" ]] && action="${words[i]}"
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "audit create publish --help --config --root" -- "$cur") )
                return
            fi
            case "$action" in
                audit) opts="--help --provider --namespace --check-remote --json" ;;
                create) opts="--help --provider --namespace --visibility --apply" ;;
                publish) opts="--help --provider --namespace --visibility --only --remote-name --no-create --apply" ;;
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
        local)
            for ((i=1; i<cword; i++)); do
                case "${words[i]}" in
                    plan|remotes|init|clone|bootstrap|localize|backup|verify-backup|backups|restore) action="${words[i]}" ;;
                esac
            done
            if [[ -z "$action" ]]; then
                COMPREPLY=( $(compgen -W "plan remotes init clone bootstrap localize backup verify-backup backups restore --help --config --root" -- "$cur") )
                return
            fi
            opts="--help --config --root --remotes-dir --backups-dir --output --config-output --apply --mirror-sources --update-mirrors --seed --with-remotes --set-origin --no-set-origin --include-operations --restore-operations --retention --overwrite --no-config --json"
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

complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a doctor -d 'Check dependencies and config'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a catalog -d 'Print repository catalog'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a repos -d 'Repository provider operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a submodules -d 'Submodule operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a local -d 'Local-only repository operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a git -d 'Run git across root and submodules'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a source -d 'Source/image metadata operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a compose -d 'Run compose operations'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a images -d 'Verify image labels'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a docs -d 'Documentation utilities'
complete -c rfm -n 'not __fish_seen_subcommand_from doctor catalog repos submodules local git source compose images docs completion' -a completion -d 'Print shell completion script'

complete -c rfm -n '__fish_seen_subcommand_from completion' -a bash -d 'Print Bash completion'
complete -c rfm -n '__fish_seen_subcommand_from completion' -a fish -d 'Print Fish completion'

complete -c rfm -n '__fish_seen_subcommand_from catalog' -l view -r -a 'repositories summary tree gaps all' -d 'Catalog view'
complete -c rfm -n '__fish_seen_subcommand_from catalog' -l format -r -a 'text json markdown' -d 'Output format'
complete -c rfm -n '__fish_seen_subcommand_from catalog' -l json -d 'Alias for JSON output'
complete -c rfm -n '__fish_seen_subcommand_from catalog' -l output -r -d 'Write catalog to file'
complete -c rfm -n '__fish_seen_subcommand_from catalog' -l catalog-file -r -d 'Override capability catalog JSON'
complete -c rfm -n '__fish_seen_subcommand_from catalog' -l priority -r -a 'P0 P1 P2 P3' -d 'Filter gaps by priority'
complete -c rfm -n '__fish_seen_subcommand_from catalog' -l status -r -a 'implemented partial planned missing' -d 'Filter gaps by status'
complete -c rfm -n '__fish_seen_subcommand_from catalog' -l check-evidence -d 'Fail when component evidence is missing'

complete -c rfm -n '__fish_seen_subcommand_from repos; and not __fish_seen_subcommand_from audit create publish' -a audit -d 'Audit .gitmodules and remotes'
complete -c rfm -n '__fish_seen_subcommand_from repos; and not __fish_seen_subcommand_from audit create publish' -a create -d 'Create repositories'
complete -c rfm -n '__fish_seen_subcommand_from repos; and not __fish_seen_subcommand_from audit create publish' -a publish -d 'Publish local repositories'
complete -c rfm -n '__fish_seen_subcommand_from repos' -l provider -r -a 'github gitlab local' -d 'Repository provider'
complete -c rfm -n '__fish_seen_subcommand_from repos' -l namespace -r -d 'Provider namespace/group/org'
complete -c rfm -n '__fish_seen_subcommand_from audit' -l check-remote -d 'Check remote existence'
complete -c rfm -n '__fish_seen_subcommand_from audit' -l json -d 'Print JSON output'
complete -c rfm -n '__fish_seen_subcommand_from create' -l visibility -r -a 'private public' -d 'Repository visibility'
complete -c rfm -n '__fish_seen_subcommand_from create' -l apply -d 'Apply changes'
complete -c rfm -n '__fish_seen_subcommand_from publish' -l only -r -a 'all new upstream existing' -d 'Source type filter'
complete -c rfm -n '__fish_seen_subcommand_from publish' -l remote-name -r -d 'Remote name for publishing'
complete -c rfm -n '__fish_seen_subcommand_from publish' -l no-create -d 'Do not create provider repo'
complete -c rfm -n '__fish_seen_subcommand_from publish' -l apply -d 'Apply changes'

complete -c rfm -n '__fish_seen_subcommand_from submodules; and not __fish_seen_subcommand_from sync' -a sync -d 'Sync .gitmodules and origins'
complete -c rfm -n '__fish_seen_subcommand_from submodules' -l provider -r -a 'github gitlab local' -d 'Repository provider'
complete -c rfm -n '__fish_seen_subcommand_from submodules' -l namespace -r -d 'Provider namespace/group/org'
complete -c rfm -n '__fish_seen_subcommand_from submodules' -l apply -d 'Apply changes'

complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize backup verify-backup backups restore' -a plan -d 'Show local materialization plan'
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize backup verify-backup backups restore' -a remotes -d 'Create local bare remotes'
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize backup verify-backup backups restore' -a init -d 'Create local working repositories'
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize backup verify-backup backups restore' -a clone -d 'Clone from local remotes'
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize backup verify-backup backups restore' -a bootstrap -d 'Bootstrap full local submodule workspace'
complete -c rfm -n '__fish_seen_subcommand_from local; and not __fish_seen_subcommand_from plan remotes init clone bootstrap localize backup verify-backup backups restore' -a localize -d 'Materialize local workspace'
complete -c rfm -n '__fish_seen_subcommand_from local' -l remotes-dir -r -a '(__fish_complete_directories)' -d 'Local bare remotes directory'
complete -c rfm -n '__fish_seen_subcommand_from local' -l apply -d 'Apply changes'
complete -c rfm -n '__fish_seen_subcommand_from local' -l update-mirrors -d 'Update existing local mirrors'
complete -c rfm -n '__fish_seen_subcommand_from local' -l json -d 'Print JSON output'
complete -c rfm -n '__fish_seen_subcommand_from localize' -l no-set-origin -d 'Keep current root origin'
complete -c rfm -n '__fish_seen_subcommand_from local' -l mirror-sources -d 'Mirror configured source/upstream URLs'
complete -c rfm -n '__fish_seen_subcommand_from remotes' -l seed -d 'Seed empty bare repositories with an initial commit'
complete -c rfm -n '__fish_seen_subcommand_from init' -l with-remotes -d 'Create local bare remotes too'
complete -c rfm -n '__fish_seen_subcommand_from init' -l set-origin -d 'Point origin to local bare remotes'
complete -c rfm -n '__fish_seen_subcommand_from bootstrap' -l set-origin -d 'Point root origin to local bare remote'

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
    parser.add_argument("--profile", action="append", help="Apply a named config profile. Repeat or use comma-separated names.")
    parser.add_argument("--group", action="append", help="Operate on a named repository group. Repeat or use comma-separated names.")


def add_safety_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--force", action="store_true", help="Override workspace safety guards. Requires --reason.")
    parser.add_argument("--reason", help="Required explanation when --force is used; recorded in the operation journal.")


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root).expanduser().resolve()


def _config(args: argparse.Namespace):
    return load_config(
        args.config,
        profiles=getattr(args, "profile", None),
        groups=getattr(args, "group", None),
    )


def _optional_config(
    path: str | None = None,
    start: Path | None = None,
    *,
    profiles=None,
    groups=None,
):
    if path:
        return load_config(path, profiles=profiles, groups=groups)
    try:
        return load_config(find_config(start=start), profiles=profiles, groups=groups)
    except FileNotFoundError:
        return None


def _mutate(
    args: argparse.Namespace,
    cfg,
    label: str,
    callback,
    *,
    require_clean: bool = False,
    reject_diverged: bool = False,
) -> int:
    if not getattr(args, "apply", False):
        return callback()
    root = _root(args)
    force = bool(getattr(args, "force", False))
    reason = getattr(args, "reason", None)
    if require_clean or reject_diverged:
        assert_workspace_safe(cfg, root, label, force=force, reason=reason, require_clean=require_clean, reject_diverged=reject_diverged)
    op_dir = operations_dir(root, cfg.local.get("operations_dir"))
    lock = lock_path(root, cfg.local.get("lock_file"))
    operation_id = os.environ.get("RFM_OPERATION_ID")
    with mutation_context(
        root,
        label,
        list(getattr(args, "_argv", [])),
        op_dir,
        lock,
        force=force,
        reason=reason,
        operation_id=operation_id,
    ) as journal:
        code = int(callback())
        journal.complete(code)
        stream = sys.stderr if getattr(args, "json", False) else sys.stdout
        print(f"[OPERATION] {journal.id} status={journal.data['status']} journal={journal.path}", file=stream)
        return code



def _provider_preflight(cfg, root: Path, provider_override: str | None, strict_scopes: bool = False) -> None:
    names: set[str] = set()
    if provider_override:
        names.add(provider_override)
    else:
        for repo in cfg.repositories:
            names.add(repo.provider or cfg.default_provider_name)
    for name in sorted(names):
        provider = cfg.providers.get(name)
        if provider and not provider.is_local:
            status = require_provider_auth(cfg, root, name, strict_scopes=strict_scopes)
            print(f"[AUTH] {name} driver={status.driver} host={status.host} user={status.active_user or '-'} scopes={'known' if status.scopes_known else 'unknown'}")

def cmd_completion(args: argparse.Namespace) -> int:
    resource = files("repo_fleet_manager").joinpath(f"data/rfm.{args.shell}")
    print(resource.read_text(encoding="utf-8").rstrip())
    return 0


def cmd_config_validate(args: argparse.Namespace) -> int:
    path, raw = load_raw_config(args.config)
    if args.strict:
        issues = validate_config_data(raw)
        migrated = raw
        changes: list[str] = []
    else:
        migrated, changes = migrate_config_data(raw)
        issues = validate_config_data(migrated)
    resolved_profiles: list[str] = []
    resolved_groups: list[str] = []
    resolution_changes: list[str] = []
    if not issues and (getattr(args, "profile", None) or getattr(args, "group", None)):
        try:
            resolved = _config(args)
            resolved_profiles = list(resolved.active_profiles)
            resolved_groups = list(resolved.active_groups)
            resolution_changes = list(resolved.resolution_changes)
        except ConfigValidationError as exc:
            issues.extend(exc.issues)
        except ConfigResolutionError as exc:
            issues.append(ValidationIssue("$", str(exc), "config-resolution"))
    if args.json:
        print(json.dumps({
            "path": str(path),
            "valid": not issues,
            "schema_version": migrated.get("schema_version"),
            "migration_changes": changes,
            "profiles": resolved_profiles,
            "groups": resolved_groups,
            "resolution_changes": resolution_changes,
            "issues": [asdict(issue) for issue in issues],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"config: {path}")
        print(f"schema: {migrated.get('schema_version') or '-'} (current {CURRENT_SCHEMA_VERSION})")
        if changes:
            print("migration required:")
            for change in changes:
                print(f" - {change}")
        if resolved_profiles or resolved_groups:
            print(f"resolved profiles: {', '.join(resolved_profiles) or '-'}")
            print(f"resolved groups:   {', '.join(resolved_groups) or '-'}")
        if issues:
            print("validation errors:")
            for issue in issues:
                print(f" - {issue.render()}")
        else:
            print("[OK] configuration is valid")
    return 2 if issues else 0


def cmd_config_render(args: argparse.Namespace) -> int:
    cfg = _config(args)
    content = json.dumps(cfg.raw, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        print(f"[OK] wrote resolved configuration: {output}")
    else:
        print(content, end="")
    return 0


def cmd_config_profiles(args: argparse.Namespace) -> int:
    _, raw = load_raw_config(args.config)
    migrated, _ = migrate_config_data(raw)
    rows = migrated.get("profiles") or {}
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for name, profile in rows.items():
            extends = profile.get("extends") if isinstance(profile, dict) else None
            print(f"{name}\textends={extends or '-'}")
    return 0


def cmd_config_groups(args: argparse.Namespace) -> int:
    _, raw = load_raw_config(args.config)
    migrated, _ = migrate_config_data(raw)
    rows = migrated.get("groups") or {}
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for name, group in rows.items():
            print(f"{name}\t{json.dumps(group, ensure_ascii=False)}")
    return 0

def cmd_config_migrate(args: argparse.Namespace) -> int:
    path, raw = load_raw_config(args.config)
    migrated, changes = migrate_config_data(raw, args.to)
    validate_or_raise(migrated)
    print(f"config: {path}")
    if not changes:
        print("[OK] configuration already uses the current schema")
        return 0
    for change in changes:
        print(f" - {change}")
    if not args.apply:
        print("[DRY-RUN] no file changed; re-run with --apply")
        return 0
    cfg = load_config(args.config)
    def apply_migration() -> int:
        backup_file(path)
        backup = write_migrated_config(path, migrated, backup=not args.no_backup)
        print(f"[OK] migrated {path}")
        if backup:
            print(f"[OK] backup {backup}")
        return 0
    return _mutate(args, cfg, "config migrate", apply_migration)



def cmd_init_project(args: argparse.Namespace) -> int:
    directory = Path(args.directory or args.name)
    result = init_project(
        args.name,
        directory=directory,
        branch=args.branch,
        provider=args.provider,
        namespace=args.namespace or "",
        visibility=args.visibility,
        description=args.description,
        owner=args.owner,
        apply=args.apply,
        force=args.force,
        git_init=args.git_init,
    )
    print(f"[{'OK' if args.apply else 'DRY-RUN'}] project scaffold: {result.target}")
    print(f"     files={len(result.written)} skipped={len(result.skipped)}")
    if not args.apply:
        print("[DRY-RUN] no files changed; re-run with --apply")
    return 0


def cmd_scaffold_templates(args: argparse.Namespace) -> int:
    rows = [
        {"name": "generic", "kind": "module", "description": "README, license, gitignore and RFM template metadata."},
        {"name": "python-cli", "kind": "tooling", "description": "Installable Python CLI with unittest and CI."},
        {"name": "python-service", "kind": "service", "description": "Python service baseline with health function, tests, Dockerfile and CI."},
        {"name": "node-service", "kind": "service", "description": "Node.js service baseline with node:test, Dockerfile and CI."},
    ]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row['name']:<16} kind={row['kind']:<8} {row['description']}")
    return 0


def cmd_scaffold_repository(args: argparse.Namespace) -> int:
    root = _root(args)
    config_path = find_config(start=root, explicit=args.config)
    result = scaffold_repository(
        config_path.resolve(),
        root=root,
        name=args.name,
        path=args.path,
        template=args.template,
        kind=args.kind,
        description=args.description,
        branch=args.branch,
        provider=args.provider,
        visibility=args.visibility,
        tags=args.tag,
        depends_on=args.depends_on,
        owner=args.owner,
        apply=args.apply,
        force=args.force,
        update_lock=not args.no_update_lock,
    )
    print(f"[{'OK' if args.apply else 'DRY-RUN'}] repository scaffold: {result.target}")
    print(f"     files={len(result.written)} skipped={len(result.skipped)}")
    if not args.apply:
        print("[DRY-RUN] no files changed; re-run with --apply")
    return 0


def cmd_bootstrap_lock(args: argparse.Namespace) -> int:
    config_path = find_config(start=_root(args), explicit=args.config)
    _, raw = load_raw_config(config_path)
    config, _ = migrate_config_data(raw)
    validate_or_raise(config)
    path = write_bootstrap_lock(
        config,
        root=_root(args),
        output=args.output,
        apply=args.apply,
        force=args.force,
    )
    if args.apply:
        print(f"[OK] bootstrap lock written: {path}")
    else:
        print("[DRY-RUN] no file changed; re-run with --apply")
    return 0


def cmd_bootstrap_verify(args: argparse.Namespace) -> int:
    config_path = find_config(start=_root(args), explicit=args.config)
    _, raw = load_raw_config(config_path)
    config, _ = migrate_config_data(raw)
    validate_or_raise(config)
    report = verify_bootstrap_lock(config, root=_root(args), lock_file=args.lock_file)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["valid"]:
        print(f"[OK] bootstrap contract verified: {report['lock']}")
        print(f"     project={report.get('project') or '-'} repositories={report['repositories']} files={report['files']}")
    else:
        print(f"[FAIL] bootstrap contract is invalid: {report['lock']}")
        for issue in report["issues"]:
            print(f" - {issue}")
    return 0 if report["valid"] else 2

def cmd_doctor(args: argparse.Namespace) -> int:
    cfg = _config(args)
    root = _root(args)
    required = ["git", "python3"]
    optional = ["docker", "podman", "podman-compose", "gh", "glab"]
    print(f"Repo Fleet Manager {__version__}")
    print(f"config: {cfg.path}")
    print(f"schema: {cfg.schema_version}")
    print(f"root:   {root}")
    if cfg.migration_changes:
        print(f"[WARN] config is legacy; run `rfm config migrate --apply` ({len(cfg.migration_changes)} changes)")
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
    print(f" - default jobs:  {cfg.default_jobs}")
    print(f" - profiles:      {', '.join(cfg.active_profiles) or '-'}")
    print(f" - groups:        {', '.join(cfg.active_groups) or '-'}")
    if args.auth:
        print("\nProvider authentication:")
        for row in auth_report(cfg, root, args.provider):
            mark = "OK" if row["authenticated"] else "FAIL"
            print(f" - [{mark}] {row['provider']} host={row['host']} user={row['active_user'] or '-'} profile={row['profile'] or '-'}")
            print(f"   driver={row['driver']} profile={row['profile'] or '-'} capabilities={row['capabilities']} token_env={row['token_environment'] or []}")
            print(f"   required_scopes={row['required_scopes']} detected_scopes={row['scopes'] if row['scopes_known'] else 'unknown'}")
            if not row["authenticated"] or (args.strict_auth and row["required_scopes"] and not row["scopes_known"]):
                failed = True
    return 1 if failed else 0


def cmd_auth_status(args: argparse.Namespace) -> int:
    cfg = _config(args)
    rows = auth_report(cfg, _root(args), args.provider)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            mark = "OK" if row["authenticated"] else "FAIL"
            print(
                f"[{mark}] {row['provider']} driver={row['driver']} cli={row['cli']} "
                f"host={row['host']} profile={row['profile'] or '-'} "
                f"active_user={row['active_user'] or '-'} expected_user={row['expected_user'] or '-'}"
            )
            detected = row["scopes"] if row["scopes_known"] else "unknown"
            print(
                f"     required_scopes={row['required_scopes']} detected_scopes={detected} "
                f"missing_scopes={row['missing_scopes']} token_env={row['token_environment'] or []}"
            )
            print(f"     capabilities={row['capabilities']} non_interactive={row['non_interactive']}")
            if args.verbose:
                print("     " + row["detail"].replace("\n", "\n     "))
    failed = any(not row["authenticated"] for row in rows if row["driver"] != "local")
    if args.strict_scopes:
        failed = failed or any(row["required_scopes"] and not row["scopes_known"] for row in rows if row["driver"] != "local")
    return 2 if failed else 0


def cmd_catalog(args: argparse.Namespace) -> int:
    root = _root(args)
    output_format = "json" if args.json else args.format
    if args.view == "repositories":
        cfg = _config(args)
        rows = [asdict(repo) for repo in cfg.repositories]
        if output_format == "json":
            content = json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
        elif output_format == "markdown":
            lines = [
                f"# {cfg.project.get('name', 'RFM')} repository catalog", "",
                "| Path | Repository | Kind | Source type | Provider | Dependencies |",
                "|---|---|---|---|---|---|",
            ]
            for repo in cfg.repositories:
                lines.append(f"| `{repo.path}` | `{repo.repo}` | {repo.kind} | {repo.source_type} | {repo.provider or cfg.default_provider_name} | {', '.join(repo.depends_on) or '—'} |")
            content = "\n".join(lines) + "\n"
        else:
            lines = ["PATH                                REPOSITORY                              KIND       SOURCE      PROVIDER   DEPENDS_ON", "-" * 132]
            for repo in cfg.repositories:
                lines.append(f"{repo.path:<35} {repo.repo:<39} {repo.kind:<10} {repo.source_type:<11} {repo.provider or cfg.default_provider_name:<10} {','.join(repo.depends_on) or '-'}")
            content = "\n".join(lines) + "\n"
    else:
        catalog = load_service_catalog(root, args.catalog_file)
        content = render_catalog(catalog, root, args.view, output_format, priority=args.priority, status=args.status)
    if args.output:
        destination = Path(args.output).expanduser()
        if not destination.is_absolute():
            destination = root / destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        print(f"[OK] wrote {destination}")
    else:
        print(content, end="")
    if args.check_evidence and args.view != "repositories":
        catalog = load_service_catalog(root, args.catalog_file)
        missing = catalog_summary(catalog, root)["missing_evidence"]
        if missing:
            print(f"[ERROR] catalog evidence missing for: {', '.join(missing)}", file=sys.stderr)
            return 2
    return 0


def cmd_graph_show(args: argparse.Namespace) -> int:
    cfg = _config(args)
    content = render_graph(cfg, args.format)
    if args.output:
        path = Path(args.output).expanduser()
        if not path.is_absolute():
            path = _root(args) / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"[OK] wrote {path}")
    else:
        print(content, end="")
    return 0


def cmd_safety_status(args: argparse.Namespace) -> int:
    cfg = _config(args)
    rows = workspace_safety_report(cfg, _root(args))
    payload = [asdict(row) for row in rows]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            issues = []
            if row.dirty:
                issues.append("dirty")
            if row.diverged:
                issues.append(f"diverged(ahead={row.ahead},behind={row.behind})")
            if row.detached:
                issues.append("detached")
            if row.branch_mismatch:
                issues.append(f"branch-mismatch(expected={row.expected_branch})")
            print(f"[{'WARN' if issues else 'OK'}] {row.repo} path={row.path} branch={row.branch or '-'} upstream={row.upstream or '-'} {' '.join(issues)}")
    return 2 if any(row.dirty or row.diverged or row.detached or row.branch_mismatch for row in rows) else 0


def cmd_repos_audit(args: argparse.Namespace) -> int:
    cfg = _config(args)
    report = audit(cfg, _root(args), args.provider, args.namespace, args.check_remote)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["issue_count"] == 0 else 2
    return print_audit_report(report)


def cmd_repos_create(args: argparse.Namespace) -> int:
    cfg = _config(args)
    root = _root(args)
    if args.apply:
        _provider_preflight(cfg, root, args.provider, strict_scopes=args.strict_scopes)
    return _mutate(args, cfg, "repos create", lambda: create_repositories(cfg, root, args.provider, args.namespace, args.visibility, args.apply))


def cmd_repos_publish(args: argparse.Namespace) -> int:
    cfg = _config(args)
    root = _root(args)
    if args.apply:
        _provider_preflight(cfg, root, args.provider, strict_scopes=args.strict_scopes)
    callback = lambda: publish_repositories(cfg, root, args.provider, args.namespace, args.visibility, args.apply, only=args.only, remote_name=args.remote_name, create_remote=not args.no_create)
    return _mutate(args, cfg, "repos publish", callback, require_clean=True)


def cmd_repos_fork(args: argparse.Namespace) -> int:
    cfg = _config(args)
    root = _root(args)
    if args.apply:
        _provider_preflight(cfg, root, args.provider, strict_scopes=args.strict_scopes)
    callback = lambda: fork_repositories(cfg, root, args.provider, args.namespace, args.apply, remote_name=args.remote_name)
    return _mutate(args, cfg, "repos fork", callback, require_clean=True)


def cmd_repos_mirror(args: argparse.Namespace) -> int:
    cfg = _config(args)
    root = _root(args)
    if args.apply:
        _provider_preflight(cfg, root, args.provider, strict_scopes=args.strict_scopes)
    callback = lambda: mirror_repositories(cfg, root, args.provider, args.namespace, args.apply)
    return _mutate(args, cfg, "repos mirror", callback, require_clean=False)


def cmd_repos_reconcile(args: argparse.Namespace) -> int:
    cfg = _config(args)
    root = _root(args)
    if args.apply:
        _provider_preflight(cfg, root, args.provider, strict_scopes=args.strict_scopes)
    callback = lambda: reconcile_repositories(cfg, root, args.provider, args.namespace, args.json, apply=args.apply)
    return _mutate(args, cfg, "repos reconcile", callback, require_clean=False)


def cmd_submodules_sync(args: argparse.Namespace) -> int:
    cfg = _config(args)
    callback = lambda: sync_submodules(cfg, _root(args), args.provider, args.namespace, args.apply)
    return _mutate(args, cfg, "submodules sync", callback, require_clean=True)


def cmd_local_plan(args: argparse.Namespace) -> int:
    cfg = _config(args)
    return print_local_plan(cfg, _root(args), args.remotes_dir, json_output=args.json)


def cmd_local_remotes(args: argparse.Namespace) -> int:
    cfg = _config(args)
    jobs = args.jobs or cfg.default_jobs
    callback = lambda: create_local_remotes(cfg, _root(args), args.remotes_dir, args.apply, args.mirror_sources, seed=args.seed, update_mirrors=args.update_mirrors, jobs=jobs)
    return _mutate(args, cfg, "local remotes", callback)


def cmd_local_init(args: argparse.Namespace) -> int:
    cfg = _config(args)
    jobs = args.jobs or cfg.default_jobs
    callback = lambda: init_local_worktrees(cfg, _root(args), args.remotes_dir, args.apply, args.with_remotes, args.set_origin, jobs=jobs)
    return _mutate(args, cfg, "local init", callback)


def cmd_local_clone(args: argparse.Namespace) -> int:
    cfg = _config(args)
    jobs = args.jobs or cfg.default_jobs
    callback = lambda: clone_local_repositories(cfg, _root(args), args.remotes_dir, args.apply, args.mirror_sources, jobs=jobs)
    return _mutate(args, cfg, "local clone", callback)


def cmd_local_bootstrap(args: argparse.Namespace) -> int:
    cfg = _config(args)
    jobs = args.jobs or cfg.default_jobs
    callback = lambda: bootstrap_local(cfg, _root(args), args.remotes_dir, args.apply, args.mirror_sources, args.set_origin, jobs=jobs)
    return _mutate(args, cfg, "local bootstrap", callback)


def cmd_local_localize(args: argparse.Namespace) -> int:
    cfg = _config(args)
    jobs = args.jobs or cfg.default_jobs
    callback = lambda: localize(cfg, _root(args), args.remotes_dir, args.apply, set_origin=not args.no_set_origin, update_mirrors=args.update_mirrors, jobs=jobs)
    return _mutate(args, cfg, "local localize", callback, require_clean=False)


def cmd_local_backup(args: argparse.Namespace) -> int:
    cfg = _config(args)
    callback = lambda: create_backup(
        cfg,
        _root(args),
        remotes_override=args.remotes_dir,
        output=args.output,
        backups_override=args.backups_dir,
        include_operations=(bool(cfg.local.get("backup_include_operations")) if args.include_operations is None else args.include_operations),
        retention=args.retention,
        apply=args.apply,
        json_output=args.json,
    )
    return _mutate(args, cfg, "local backup", callback, require_clean=False)


def cmd_local_backup_verify(args: argparse.Namespace) -> int:
    return verify_backup(args.archive, json_output=args.json)


def cmd_local_backups(args: argparse.Namespace) -> int:
    root = _root(args)
    cfg = _optional_config(args.config, start=root, profiles=getattr(args, "profile", None), groups=getattr(args, "group", None))
    return list_backups(cfg, root, directory_override=args.backups_dir, json_output=args.json)


def cmd_local_restore(args: argparse.Namespace) -> int:
    root = _root(args)
    cfg = _optional_config(args.config, start=root, profiles=getattr(args, "profile", None), groups=getattr(args, "group", None))
    callback = lambda: restore_backup(
        args.archive,
        root,
        config=cfg,
        remotes_override=args.remotes_dir,
        config_output=args.config_output,
        restore_config=not args.no_config,
        restore_operations=args.restore_operations,
        overwrite=args.overwrite,
        force=args.force,
        apply=args.apply,
        json_output=args.json,
    )
    if not args.apply:
        return callback()
    op_dir = operations_dir(root, cfg.local.get("operations_dir") if cfg else None)
    lock = lock_path(root, cfg.local.get("lock_file") if cfg else None)
    with mutation_context(
        root,
        "local restore",
        list(getattr(args, "_argv", [])),
        op_dir,
        lock,
        force=args.force,
        reason=args.reason,
        operation_id=os.environ.get("RFM_OPERATION_ID"),
    ) as journal:
        code = int(callback())
        journal.complete(code)
        stream = sys.stderr if getattr(args, "json", False) else sys.stdout
        print(f"[OPERATION] {journal.id} status={journal.data['status']} journal={journal.path}", file=stream)
        return code


def cmd_cache_export(args: argparse.Namespace) -> int:
    cfg = _config(args)
    callback = lambda: export_cache(
        cfg,
        _root(args),
        output=args.output,
        cache_override=args.cache_dir,
        remotes_override=args.remotes_dir,
        images=args.image,
        include_images=args.include_images,
        engine=args.engine,
        fetch_missing=args.fetch_missing,
        allow_missing=args.allow_missing,
        retention=args.retention,
        apply=args.apply,
        json_output=args.json,
    )
    return _mutate(args, cfg, "cache export", callback, require_clean=False)


def cmd_cache_verify(args: argparse.Namespace) -> int:
    return verify_cache(args.archive, require_complete=args.require_complete, json_output=args.json)


def cmd_cache_list(args: argparse.Namespace) -> int:
    cfg = _optional_config(
        args.config,
        start=_root(args),
        profiles=getattr(args, "profile", None),
        groups=getattr(args, "group", None),
    )
    return list_caches(cfg, _root(args), args.cache_dir, json_output=args.json)


def cmd_cache_import(args: argparse.Namespace) -> int:
    cfg = _optional_config(
        args.config,
        start=_root(args),
        profiles=getattr(args, "profile", None),
        groups=getattr(args, "group", None),
    )
    callback = lambda: import_cache(
        args.archive,
        _root(args),
        config=cfg,
        remotes_override=args.remotes_dir,
        config_output=args.config_output,
        restore_config=not args.no_config,
        load_images=args.load_images,
        engine=args.engine,
        overwrite=args.overwrite,
        allow_incomplete=args.allow_incomplete,
        apply=args.apply,
        json_output=args.json,
    )
    if cfg is None:
        return callback()
    return _mutate(args, cfg, "cache import", callback, require_clean=False)


def cmd_cache_bootstrap(args: argparse.Namespace) -> int:
    return bootstrap_from_cache(
        args.archive,
        _root(args),
        remotes_override=args.remotes_dir,
        load_images=args.load_images,
        engine=args.engine,
        overwrite=args.overwrite,
        allow_incomplete=args.allow_incomplete,
        jobs=args.jobs or 1,
        apply=args.apply,
        json_output=args.json,
    )


def cmd_git(args: argparse.Namespace) -> int:
    cfg = _config(args)
    jobs = args.jobs or cfg.default_jobs
    callback = lambda: git_foreach(cfg, _root(args), args.git_action, args.apply, include_root=not args.no_root, jobs=jobs)
    if args.git_action == "status":
        return callback()
    return _mutate(args, cfg, f"git {args.git_action}", callback, require_clean=args.git_action == "pull", reject_diverged=True)


def cmd_source_fingerprint(args: argparse.Namespace) -> int:
    cfg = _config(args)
    root = _root(args)
    metadata = build_metadata(cfg, root)
    if not args.write:
        print(json.dumps(metadata, indent=2, ensure_ascii=False))
        return 0
    def write() -> int:
        build_dir = write_metadata(cfg, root, metadata)
        override = write_compose_override(cfg, root, metadata)
        print(f"[OK] wrote {build_dir / 'metadata.json'}")
        print(f"[OK] wrote {build_dir / 'compose.env'}")
        print(f"[OK] wrote {override}")
        return 0
    args.apply = True
    return _mutate(args, cfg, "source fingerprint write", write)


def cmd_compose(args: argparse.Namespace) -> int:
    cfg = _config(args)
    extra = args.extra or []
    if extra and extra[0] == "--":
        extra = extra[1:]
    callback = lambda: run_compose(cfg, _root(args), args.compose_action, extra, args.apply)
    if args.compose_action in {"ps", "logs"}:
        return callback()
    return _mutate(args, cfg, f"compose {args.compose_action}", callback)


def cmd_images_verify(args: argparse.Namespace) -> int:
    cfg = _config(args)
    return verify_images(cfg, _root(args), args.json)


def cmd_docs_validate(args: argparse.Namespace) -> int:
    return validate_links(_root(args))


def _operation_directory(args: argparse.Namespace) -> Path:
    cfg = _config(args)
    return operations_dir(_root(args), cfg.local.get("operations_dir"))


def cmd_ops_list(args: argparse.Namespace) -> int:
    directory = _operation_directory(args)
    rows = []
    for path in list_operation_files(directory):
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append({key: data.get(key) for key in ("id", "command", "status", "started_at", "finished_at", "exit_code", "resume_count")})
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row['id']}  {row['status']:<15}  {row['command']:<24}  started={row['started_at']} exit={row['exit_code']}")
    return 0


def cmd_ops_show(args: argparse.Namespace) -> int:
    journal = load_operation(_operation_directory(args), args.operation_id)
    if args.json:
        print(json.dumps(journal.data, ensure_ascii=False, indent=2))
    else:
        print(f"operation: {journal.id}")
        print(f"status:    {journal.data.get('status')}")
        print(f"command:   {journal.data.get('command')}")
        print(f"argv:      {' '.join(journal.data.get('argv') or [])}")
        print(f"steps:     {len(journal.data.get('steps') or [])}")
        print(f"rollback:  {len(journal.data.get('rollback') or [])}")
        if journal.data.get("error"):
            print(f"error:     {journal.data['error']}")
    return 0


def cmd_ops_resume(args: argparse.Namespace) -> int:
    journal = load_operation(_operation_directory(args), args.operation_id)
    if journal.data.get("status") == "completed" and not args.force:
        raise SafetyError("operation is already completed; use --force --reason to run it again")
    if args.force and not args.reason:
        raise SafetyError("--force requires --reason")
    argv = list(journal.data.get("argv") or [])
    if not argv:
        raise ValueError("operation journal does not contain argv")
    if args.force and "--force" not in argv:
        argv.extend(["--force", "--reason", args.reason])
    previous = os.environ.get("RFM_OPERATION_ID")
    os.environ["RFM_OPERATION_ID"] = args.operation_id
    try:
        return main(argv)
    finally:
        if previous is None:
            os.environ.pop("RFM_OPERATION_ID", None)
        else:
            os.environ["RFM_OPERATION_ID"] = previous


def cmd_ops_rollback(args: argparse.Namespace) -> int:
    cfg = _config(args)
    root = _root(args)
    directory = operations_dir(root, cfg.local.get("operations_dir"))
    journal = load_operation(directory, args.operation_id)
    lock = lock_path(root, cfg.local.get("lock_file"))
    with mutation_context(root, f"ops rollback {args.operation_id}", list(args._argv), directory, lock, force=args.force, reason=args.reason) as rollback_journal:
        failures, messages = journal.rollback(force=args.force)
        for message in messages:
            print(message)
        code = 1 if failures else 0
        rollback_journal.complete(code)
        return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rfm", description="Config-driven manager for large multi-repository/submodule projects.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    config = sub.add_parser("config", help="Validate and migrate repo-fleet configuration.")
    add_common(config); config_sub = config.add_subparsers(dest="config_action", required=True)
    p = config_sub.add_parser("validate", help="Validate JSON Schema, paths, secrets and dependency graph.")
    p.add_argument("--strict", action="store_true", help="Validate file as-is without in-memory legacy migration.")
    p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_config_validate)
    p = config_sub.add_parser("migrate", help="Migrate config to the current schema. Dry-run by default.")
    p.add_argument("--to", default=CURRENT_SCHEMA_VERSION, choices=[CURRENT_SCHEMA_VERSION])
    p.add_argument("--no-backup", action="store_true"); p.add_argument("--apply", action="store_true"); add_safety_flags(p); p.set_defaults(func=cmd_config_migrate)
    p = config_sub.add_parser("render", help="Render the effective config after profiles and group filtering.")
    p.add_argument("--output"); p.set_defaults(func=cmd_config_render)
    p = config_sub.add_parser("profiles", help="List available config profiles.")
    p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_config_profiles)
    p = config_sub.add_parser("groups", help="List available repository groups.")
    p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_config_groups)

    p = sub.add_parser("init-project", help="Create a portable RFM parent project with config, CI and bootstrap lock.")
    p.add_argument("name")
    p.add_argument("--directory", help="Target directory. Default: ./NAME")
    p.add_argument("--branch", default="main")
    p.add_argument("--provider", choices=["local", "github", "gitlab"], default="local")
    p.add_argument("--namespace")
    p.add_argument("--visibility", choices=["private", "internal", "public"], default="private")
    p.add_argument("--description")
    p.add_argument("--owner", default="Project Contributors")
    p.add_argument("--git-init", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init_project)

    scaffold = sub.add_parser("scaffold", help="Generate repositories and services from built-in templates.")
    scaffold_sub = scaffold.add_subparsers(dest="scaffold_action", required=True)
    p = scaffold_sub.add_parser("templates", help="List built-in repository templates.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scaffold_templates)
    p = scaffold_sub.add_parser("repository", help="Add a generated repository to an existing fleet config.")
    p.add_argument("name")
    p.add_argument("--config", help="Path to repo-fleet.json.")
    p.add_argument("--root", default=".")
    p.add_argument("--path", required=True)
    p.add_argument("--template", choices=list(SUPPORTED_REPOSITORY_TEMPLATES), default="generic")
    p.add_argument("--kind", choices=["module", "service", "tooling", "library"], default="module")
    p.add_argument("--description")
    p.add_argument("--branch")
    p.add_argument("--provider")
    p.add_argument("--visibility", choices=["private", "internal", "public"])
    p.add_argument("--tag", action="append")
    p.add_argument("--depends-on", action="append")
    p.add_argument("--owner", default="Project Contributors")
    p.add_argument("--no-update-lock", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_scaffold_repository)

    bootstrap = sub.add_parser("bootstrap", help="Generate or verify the portable bootstrap contract.")
    add_common(bootstrap)
    bootstrap_sub = bootstrap.add_subparsers(dest="bootstrap_action", required=True)
    p = bootstrap_sub.add_parser("lock", help="Generate a deterministic bootstrap lock file.")
    p.add_argument("--output", default=DEFAULT_LOCK_FILE)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_bootstrap_lock)
    p = bootstrap_sub.add_parser("verify", help="Verify config, repository contract and baseline file digests.")
    p.add_argument("--lock-file", default=DEFAULT_LOCK_FILE)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_bootstrap_verify)

    p = sub.add_parser("doctor", help="Check dependencies, configuration and optional provider authentication.")
    add_common(p); p.add_argument("--auth", action="store_true"); p.add_argument("--provider"); p.add_argument("--strict-auth", action="store_true", help="Fail when required scopes cannot be verified."); p.set_defaults(func=cmd_doctor)

    auth = sub.add_parser("auth", help="Provider authentication diagnostics without exposing tokens.")
    add_common(auth); auth_sub = auth.add_subparsers(dest="auth_action", required=True)
    p = auth_sub.add_parser("status"); p.add_argument("--provider"); p.add_argument("--json", action="store_true"); p.add_argument("--verbose", action="store_true"); p.add_argument("--strict-scopes", action="store_true"); p.set_defaults(func=cmd_auth_status)

    p = sub.add_parser("catalog", help="Inspect repositories or the RFM capability/service catalog.")
    add_common(p); p.add_argument("--view", choices=["repositories", "summary", "tree", "gaps", "all"], default="repositories")
    p.add_argument("--format", choices=["text", "json", "markdown"], default="text"); p.add_argument("--json", action="store_true")
    p.add_argument("--output"); p.add_argument("--catalog-file"); p.add_argument("--priority", choices=["P0", "P1", "P2", "P3"])
    p.add_argument("--status", choices=["implemented", "partial", "planned", "missing"]); p.add_argument("--check-evidence", action="store_true"); p.set_defaults(func=cmd_catalog)

    graph = sub.add_parser("graph", help="Repository dependency graph and execution levels.")
    add_common(graph); graph_sub = graph.add_subparsers(dest="graph_action", required=True)
    p = graph_sub.add_parser("show"); p.add_argument("--format", choices=["text", "json", "dot"], default="text"); p.add_argument("--output"); p.set_defaults(func=cmd_graph_show)

    safety = sub.add_parser("safety", help="Inspect dirty and diverged repository state.")
    add_common(safety); safety_sub = safety.add_subparsers(dest="safety_action", required=True)
    p = safety_sub.add_parser("status"); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_safety_status)

    repos = sub.add_parser("repos", help="Repository provider operations.")
    add_common(repos); repos_sub = repos.add_subparsers(dest="repos_action", required=True)
    p = repos_sub.add_parser("audit"); p.add_argument("--provider"); p.add_argument("--namespace"); p.add_argument("--check-remote", action="store_true"); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_repos_audit)
    p = repos_sub.add_parser("create"); p.add_argument("--provider"); p.add_argument("--namespace"); p.add_argument("--visibility", choices=["private", "public"], default="private"); p.add_argument("--apply", action="store_true"); p.add_argument("--strict-scopes", action="store_true"); add_safety_flags(p); p.set_defaults(func=cmd_repos_create)
    p = repos_sub.add_parser("publish"); p.add_argument("--provider", required=True); p.add_argument("--namespace"); p.add_argument("--visibility", choices=["private", "public"], default="private"); p.add_argument("--only", choices=["all", "new", "upstream", "existing"], default="all"); p.add_argument("--remote-name", default="personal"); p.add_argument("--no-create", action="store_true"); p.add_argument("--apply", action="store_true"); p.add_argument("--strict-scopes", action="store_true"); add_safety_flags(p); p.set_defaults(func=cmd_repos_publish)
    p = repos_sub.add_parser("fork", help="Create native GitHub/GitLab forks for upstream repositories."); p.add_argument("--provider", required=True); p.add_argument("--namespace"); p.add_argument("--remote-name", default="personal"); p.add_argument("--apply", action="store_true"); p.add_argument("--strict-scopes", action="store_true"); add_safety_flags(p); p.set_defaults(func=cmd_repos_fork)
    p = repos_sub.add_parser("mirror", help="Push local bare mirrors to provider destinations."); p.add_argument("--provider", required=True); p.add_argument("--namespace"); p.add_argument("--apply", action="store_true"); p.add_argument("--strict-scopes", action="store_true"); add_safety_flags(p); p.set_defaults(func=cmd_repos_mirror)
    p = repos_sub.add_parser("reconcile", help="Compare or repair provider state, branch, visibility, topics and fork lineage."); p.add_argument("--provider", required=True); p.add_argument("--namespace"); p.add_argument("--json", action="store_true"); p.add_argument("--apply", action="store_true"); p.add_argument("--strict-scopes", action="store_true"); add_safety_flags(p); p.set_defaults(func=cmd_repos_reconcile)

    p = sub.add_parser("submodules", help="Submodule operations.")
    add_common(p); subm = p.add_subparsers(dest="submodules_action", required=True)
    sp = subm.add_parser("sync"); sp.add_argument("--provider"); sp.add_argument("--namespace"); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_submodules_sync)

    p = sub.add_parser("local", help="Local-only repository operations; no GitHub/GitLab required.")
    add_common(p); local_sub = p.add_subparsers(dest="local_action", required=True)
    sp = local_sub.add_parser("plan"); sp.add_argument("--remotes-dir"); sp.add_argument("--json", action="store_true"); sp.set_defaults(func=cmd_local_plan)
    sp = local_sub.add_parser("remotes"); sp.add_argument("--remotes-dir"); sp.add_argument("--mirror-sources", action="store_true"); sp.add_argument("--update-mirrors", action="store_true"); sp.add_argument("--seed", action="store_true"); sp.add_argument("--jobs", type=int); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_local_remotes)
    sp = local_sub.add_parser("init"); sp.add_argument("--remotes-dir"); sp.add_argument("--with-remotes", action="store_true"); sp.add_argument("--set-origin", action="store_true"); sp.add_argument("--jobs", type=int); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_local_init)
    sp = local_sub.add_parser("clone"); sp.add_argument("--remotes-dir"); sp.add_argument("--mirror-sources", action="store_true"); sp.add_argument("--jobs", type=int); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_local_clone)
    sp = local_sub.add_parser("bootstrap"); sp.add_argument("--remotes-dir"); sp.add_argument("--mirror-sources", action="store_true"); sp.add_argument("--set-origin", action="store_true"); sp.add_argument("--jobs", type=int); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_local_bootstrap)
    sp = local_sub.add_parser("localize"); sp.add_argument("--remotes-dir"); sp.add_argument("--update-mirrors", action="store_true"); sp.add_argument("--no-set-origin", action="store_true"); sp.add_argument("--jobs", type=int); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_local_localize)
    sp = local_sub.add_parser("backup", help="Create a verified archive of local bare remotes and RFM state."); sp.add_argument("--remotes-dir"); sp.add_argument("--backups-dir"); sp.add_argument("--output"); sp.add_argument("--include-operations", action=argparse.BooleanOptionalAction, default=None); sp.add_argument("--retention", type=int); sp.add_argument("--json", action="store_true"); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_local_backup)
    sp = local_sub.add_parser("verify-backup", help="Verify archive checksums, Git objects and refs."); sp.add_argument("archive"); sp.add_argument("--json", action="store_true"); sp.set_defaults(func=cmd_local_backup_verify)
    sp = local_sub.add_parser("backups", help="List local backup archives."); sp.add_argument("--backups-dir"); sp.add_argument("--json", action="store_true"); sp.set_defaults(func=cmd_local_backups)
    sp = local_sub.add_parser("restore", help="Restore config and local bare remotes from a verified archive."); sp.add_argument("archive"); sp.add_argument("--remotes-dir"); sp.add_argument("--config-output"); sp.add_argument("--no-config", action="store_true"); sp.add_argument("--restore-operations", action="store_true"); sp.add_argument("--overwrite", action="store_true"); sp.add_argument("--json", action="store_true"); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_local_restore)

    cache = sub.add_parser("cache", help="Export, verify and import air-gapped Git and container image caches.")
    add_common(cache); cache_sub = cache.add_subparsers(dest="cache_action", required=True)
    sp = cache_sub.add_parser("export", help="Create a verified offline cache from Git repositories and container images.")
    sp.add_argument("--output"); sp.add_argument("--cache-dir"); sp.add_argument("--remotes-dir"); sp.add_argument("--image", action="append"); sp.add_argument("--include-images", action=argparse.BooleanOptionalAction, default=True); sp.add_argument("--engine", choices=["docker", "podman"]); sp.add_argument("--fetch-missing", action="store_true"); sp.add_argument("--allow-missing", action="store_true"); sp.add_argument("--retention", type=int); sp.add_argument("--json", action="store_true"); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_cache_export)
    sp = cache_sub.add_parser("verify", help="Verify checksums, Git bundles and cache completeness.")
    sp.add_argument("archive"); sp.add_argument("--require-complete", action="store_true"); sp.add_argument("--json", action="store_true"); sp.set_defaults(func=cmd_cache_verify)
    sp = cache_sub.add_parser("list", help="List offline cache archives.")
    sp.add_argument("--cache-dir"); sp.add_argument("--json", action="store_true"); sp.set_defaults(func=cmd_cache_list)
    sp = cache_sub.add_parser("import", help="Import Git bundles into local bare remotes and load image archives.")
    sp.add_argument("archive"); sp.add_argument("--remotes-dir"); sp.add_argument("--config-output"); sp.add_argument("--no-config", action="store_true"); sp.add_argument("--load-images", action=argparse.BooleanOptionalAction, default=True); sp.add_argument("--engine", choices=["docker", "podman"]); sp.add_argument("--overwrite", action="store_true"); sp.add_argument("--allow-incomplete", action="store_true"); sp.add_argument("--json", action="store_true"); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_cache_import)
    sp = cache_sub.add_parser("bootstrap", help="Create a complete workspace from an offline cache without provider access.")
    sp.add_argument("archive"); sp.add_argument("--remotes-dir"); sp.add_argument("--load-images", action=argparse.BooleanOptionalAction, default=True); sp.add_argument("--engine", choices=["docker", "podman"]); sp.add_argument("--overwrite", action="store_true"); sp.add_argument("--allow-incomplete", action="store_true"); sp.add_argument("--jobs", type=int); sp.add_argument("--json", action="store_true"); sp.add_argument("--apply", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_cache_bootstrap)

    p = sub.add_parser("git", help="Run git operations in dependency order across root and submodules.")
    add_common(p); p.add_argument("git_action", choices=["status", "pull", "push"]); p.add_argument("--jobs", type=int); p.add_argument("--apply", action="store_true"); p.add_argument("--no-root", action="store_true"); add_safety_flags(p); p.set_defaults(func=cmd_git)

    p = sub.add_parser("source", help="Source/image metadata operations.")
    add_common(p); source_sub = p.add_subparsers(dest="source_action", required=True)
    sp = source_sub.add_parser("fingerprint"); sp.add_argument("--write", action="store_true"); add_safety_flags(sp); sp.set_defaults(func=cmd_source_fingerprint)

    p = sub.add_parser("compose", help="Run compose operations with generated source metadata.")
    add_common(p); p.add_argument("compose_action", choices=["ps", "up", "down", "build", "pull", "logs"]); p.add_argument("--apply", action="store_true"); add_safety_flags(p); p.add_argument("extra", nargs=argparse.REMAINDER); p.set_defaults(func=cmd_compose)

    p = sub.add_parser("images", help="Verify built image labels against source fingerprints.")
    add_common(p); img_sub = p.add_subparsers(dest="images_action", required=True)
    sp = img_sub.add_parser("verify"); sp.add_argument("--json", action="store_true"); sp.set_defaults(func=cmd_images_verify)

    p = sub.add_parser("ops", help="Inspect, resume and roll back mutation journals.")
    add_common(p); ops_sub = p.add_subparsers(dest="ops_action", required=True)
    sp = ops_sub.add_parser("list"); sp.add_argument("--json", action="store_true"); sp.set_defaults(func=cmd_ops_list)
    sp = ops_sub.add_parser("show"); sp.add_argument("operation_id"); sp.add_argument("--json", action="store_true"); sp.set_defaults(func=cmd_ops_show)
    sp = ops_sub.add_parser("resume"); sp.add_argument("operation_id"); add_safety_flags(sp); sp.set_defaults(func=cmd_ops_resume)
    sp = ops_sub.add_parser("rollback"); sp.add_argument("operation_id"); add_safety_flags(sp); sp.set_defaults(func=cmd_ops_rollback)

    p = sub.add_parser("docs", help="Documentation utilities.")
    add_common(p); docs_sub = p.add_subparsers(dest="docs_action", required=True)
    sp = docs_sub.add_parser("validate-links"); sp.set_defaults(func=cmd_docs_validate)

    p = sub.add_parser("completion", help="Print shell completion script.")
    p.add_argument("shell", choices=["bash", "fish"]); p.set_defaults(func=cmd_completion)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(effective_argv)
    args._argv = effective_argv
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
