from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

from .config import ProjectConfig, Provider, Repository
from .localops import local_bare_path, remotes_dir, upstream_source_url
from .operations import note_manual_rollback, track_git_remote
from .shell import command_exists, run, run_interactive, shlex_join


@dataclass(slots=True)
class AuthStatus:
    provider: str
    driver: str
    cli: str
    host: str
    profile: str | None
    expected_user: str | None
    cli_installed: bool
    authenticated: bool
    active_user: str | None
    token_environment: list[str]
    required_scopes: list[str]
    scopes: list[str]
    scopes_known: bool
    missing_scopes: list[str]
    non_interactive: bool
    capabilities: dict[str, bool | str | list[str]]
    detail: str




BUILTIN_PROVIDER_DRIVERS = {"github", "gitlab", "local", "generic"}


def _provider_plugin(provider: Provider, config: ProjectConfig | None = None):
    if provider.driver in BUILTIN_PROVIDER_DRIVERS:
        return None
    from .plugin_api import ProviderPluginV1
    from .plugins import registry_for
    registry = registry_for(config)
    plugin = registry.resolve("provider", provider.driver)
    if plugin is None or not isinstance(plugin, ProviderPluginV1):
        raise RuntimeError(f"provider driver {provider.driver!r} requires an installed compatible plugin")
    return registry, plugin


def execute_provider_plugin(
    provider: Provider,
    operation: str,
    root: Path,
    *,
    config: ProjectConfig | None = None,
    repo: Repository | None = None,
    apply: bool = False,
    options: dict | None = None,
):
    resolved = _provider_plugin(provider, config)
    if resolved is None:
        return None
    registry, plugin = resolved
    from .plugin_api import ProviderRequest
    merged_options = dict(registry.setting(plugin.name))
    merged_options.update(options or {})
    return plugin.execute(ProviderRequest(
        operation=operation, root=root.resolve(), provider=asdict(provider),
        repository=asdict(repo) if repo is not None else None,
        project=dict(config.project) if config is not None else {}, apply=apply, options=merged_options,
    ))


def provider_host(provider: Provider) -> str:
    if provider.host:
        return provider.host
    if provider.driver == "github":
        return "github.com"
    if provider.driver == "gitlab":
        return "gitlab.com"
    return provider.driver or "local"


def source_identifier(value: str) -> str:
    text = value.strip()
    if re.match(r"^[^/@:]+/[^/]+$", text):
        return text.removesuffix(".git")
    if text.startswith("git@") and ":" in text:
        text = text.split(":", 1)[1]
    else:
        parsed = urlparse(text)
        if parsed.scheme:
            text = parsed.path
    return text.strip("/").removesuffix(".git")


def _json_output(cmd: list[str], cwd: Path) -> dict | list | None:
    result = run(cmd, cwd=cwd)
    if result.code != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _token_environment(provider: Provider) -> list[str]:
    if provider.driver == "github":
        names = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")
    elif provider.driver == "gitlab":
        names = ("GITLAB_TOKEN", "GITLAB_ACCESS_TOKEN", "CI_JOB_TOKEN")
    else:
        names = ()
    return [name for name in names if os.environ.get(name)]


def _redact_detail(text: str) -> str:
    redacted = text
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITLAB_TOKEN", "GITLAB_ACCESS_TOKEN", "CI_JOB_TOKEN"):
        value = os.environ.get(name)
        if value:
            redacted = redacted.replace(value, "***REDACTED***")
    redacted = re.sub(r"\b(gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,}|glpat-[A-Za-z0-9_-]{8,})\b", "***REDACTED***", redacted)
    redacted = re.sub(r"(?im)^(authorization|private-token|oauth-token):\s*.*$", r"\1: ***REDACTED***", redacted)
    return redacted


def _github_scopes(cli: str, host: str, root: Path) -> tuple[list[str], bool]:
    result = run([cli, "api", "-i", "user", "--hostname", host], cwd=root)
    if result.code != 0:
        return [], False
    match = re.search(r"(?im)^x-oauth-scopes:\s*(.*)$", result.stdout)
    if not match:
        return [], False
    raw = match.group(1).strip()
    return sorted({item.strip() for item in raw.split(",") if item.strip()}), True


def _gitlab_scopes(cli: str, host: str, root: Path) -> tuple[list[str], bool]:
    payload = _json_output([cli, "api", "personal_access_tokens/self", "--hostname", host], root)
    if not isinstance(payload, dict) or not isinstance(payload.get("scopes"), list):
        return [], False
    return sorted({str(item) for item in payload["scopes"]}), True


def auth_status(provider: Provider, root: Path, config: ProjectConfig | None = None) -> AuthStatus:
    custom = execute_provider_plugin(provider, "auth-status", root, config=config)
    if custom is not None:
        data = dict(custom.data or {})
        return AuthStatus(
            provider=provider.name, driver=provider.driver, cli=str(data.get("cli") or provider.cli),
            host=str(data.get("host") or provider_host(provider)), profile=provider.profile, expected_user=provider.user,
            cli_installed=bool(data.get("cli_installed", True)), authenticated=bool(data.get("authenticated", custom.code == 0)),
            active_user=str(data.get("active_user")) if data.get("active_user") else None,
            token_environment=[str(item) for item in (data.get("token_environment") or [])],
            required_scopes=[str(item) for item in (data.get("required_scopes") or provider.required_scopes)],
            scopes=[str(item) for item in (data.get("scopes") or [])], scopes_known=bool(data.get("scopes_known", False)),
            missing_scopes=[str(item) for item in (data.get("missing_scopes") or [])],
            non_interactive=bool(data.get("non_interactive", os.environ.get("CI") or os.environ.get("RFM_NON_INTERACTIVE"))),
            capabilities=dict(data.get("capabilities") or {}), detail=str(data.get("detail") or custom.message or "plugin auth status"),
        )
    host = provider_host(provider)
    env_names = _token_environment(provider)
    installed = command_exists(provider.cli)
    non_interactive = bool(os.environ.get("CI") or os.environ.get("RFM_NON_INTERACTIVE"))
    required = sorted(set(provider.required_scopes))

    if provider.is_local:
        return AuthStatus(
            provider.name, provider.driver, provider.cli, host, provider.profile, provider.user,
            installed, True, os.environ.get("USER"), env_names, required, [], True, [],
            non_interactive, {"local": True}, "local provider requires no remote authentication",
        )
    if not installed:
        return AuthStatus(
            provider.name, provider.driver, provider.cli, host, provider.profile, provider.user,
            False, False, None, env_names, required, [], False, required,
            non_interactive, {}, f"CLI not installed: {provider.cli}",
        )

    active_user: str | None = None
    scopes: list[str] = []
    scopes_known = False
    if provider.driver == "github":
        status_cmd = [provider.cli, "auth", "status", "--active", "--hostname", host]
        state = run(status_cmd, cwd=root)
        user_result = run([provider.cli, "api", "user", "--hostname", host, "--jq", ".login"], cwd=root)
        active_user = user_result.stdout if user_result.code == 0 else None
        scopes, scopes_known = _github_scopes(provider.cli, host, root)
        capabilities: dict[str, bool | str | list[str]] = {
            "api": user_result.code == 0,
            "repo_read": run([provider.cli, "api", "user/repos", "--hostname", host, "--method", "GET", "-f", "per_page=1", "--silent"], cwd=root).code == 0,
            "fork": state.code == 0,
            "create": state.code == 0,
            "scope_check": "known" if scopes_known else "unknown-for-fine-grained-or-non-oauth-token",
        }
    elif provider.driver == "gitlab":
        status_cmd = [provider.cli, "auth", "status", "--hostname", host]
        state = run(status_cmd, cwd=root)
        user_payload = _json_output([provider.cli, "api", "user", "--hostname", host], root)
        active_user = str(user_payload.get("username")) if isinstance(user_payload, dict) and user_payload.get("username") else None
        scopes, scopes_known = _gitlab_scopes(provider.cli, host, root)
        capabilities = {
            "api": user_payload is not None,
            "repo_read": run([provider.cli, "api", "projects", "--hostname", host, "-F", "membership=true", "-F", "per_page=1"], cwd=root).code == 0,
            "fork": state.code == 0,
            "create": state.code == 0,
            "scope_check": "known" if scopes_known else "unsupported-or-non-personal-token",
        }
    else:
        state = run([provider.cli, "auth", "status"], cwd=root)
        capabilities = {"authenticated": state.code == 0}

    missing = sorted(set(required) - set(scopes)) if scopes_known else []
    authenticated = state.code == 0
    detail = state.stdout or state.stderr or "authentication status returned no output"
    if provider.user and active_user and provider.user != active_user:
        authenticated = False
        detail += f"\nexpected user {provider.user!r}, active user is {active_user!r}"
    if scopes_known and missing:
        authenticated = False
        detail += f"\nmissing required scopes: {', '.join(missing)}"
    capabilities["required_scopes"] = required
    capabilities["detected_scopes"] = scopes
    return AuthStatus(
        provider.name, provider.driver, provider.cli, host, provider.profile, provider.user,
        installed, authenticated, active_user, env_names, required, scopes, scopes_known, missing,
        non_interactive, capabilities, _redact_detail(detail),
    )


def auth_report(config: ProjectConfig, root: Path, provider_name: str | None = None) -> list[dict]:
    if provider_name:
        if provider_name not in config.providers:
            raise KeyError(f"unknown provider: {provider_name}")
        providers = [config.providers[provider_name]]
    else:
        providers = list(config.providers.values())
    return [asdict(auth_status(provider, root, config)) for provider in providers]


def require_provider_auth(config: ProjectConfig, root: Path, provider_name: str, strict_scopes: bool = False) -> AuthStatus:
    if provider_name not in config.providers:
        raise KeyError(f"unknown provider: {provider_name}")
    status = auth_status(config.providers[provider_name], root, config)
    if status.driver == "local":
        return status
    problems: list[str] = []
    if not status.cli_installed:
        problems.append(f"CLI is missing: {status.cli}")
    if not status.authenticated:
        problems.append("provider authentication failed")
    if strict_scopes and status.required_scopes and not status.scopes_known:
        problems.append("required token scopes could not be verified")
    if status.missing_scopes:
        problems.append("missing scopes: " + ", ".join(status.missing_scopes))
    if problems:
        raise RuntimeError(
            f"provider preflight failed for {status.provider} ({status.host}): {'; '.join(problems)}\n"
            "Run `rfm auth status --provider " + status.provider + " --verbose` before retrying."
        )
    return status


def fork_command(provider: Provider, upstream: str, destination_repo: str, active_user: str | None = None) -> list[str]:
    source = source_identifier(upstream)
    if provider.driver == "github":
        github_source = source
        host = provider_host(provider)
        if host != "github.com" and not source.startswith(f"{host}/"):
            github_source = f"{host}/{source}"
        cmd = [provider.cli, "repo", "fork", github_source, "--clone=false", "--fork-name", destination_repo]
        if provider.namespace and provider.namespace != active_user:
            cmd.extend(["--org", provider.namespace])
        return cmd
    if provider.driver == "gitlab":
        encoded = quote(source, safe="")
        cmd = [provider.cli, "api", f"projects/{encoded}/fork", "--method", "POST", "-f", f"name={destination_repo}", "-f", f"path={destination_repo}"]
        if provider.namespace:
            cmd.extend(["-f", f"namespace_path={provider.namespace}"])
        if provider.host:
            cmd.extend(["--hostname", provider.host])
        return cmd
    raise ValueError(f"native fork is not supported for provider driver: {provider.driver}")


def provider_repo_payload(provider: Provider, repo: Repository, root: Path, config: ProjectConfig | None = None) -> dict | None:
    custom = execute_provider_plugin(provider, "repository-get", root, config=config, repo=repo)
    if custom is not None:
        if custom.code != 0:
            return None
        payload = custom.data.get("repository") if isinstance(custom.data, dict) else None
        return dict(payload) if isinstance(payload, dict) else dict(custom.data) if isinstance(custom.data, dict) else None
    full = f"{provider.namespace}/{repo.repo}"
    if provider.driver == "github":
        cmd = [provider.cli, "api", f"repos/{full}"]
        if provider.host:
            cmd.extend(["--hostname", provider.host])
        payload = _json_output(cmd, root)
        return payload if isinstance(payload, dict) else None
    if provider.driver == "gitlab":
        encoded = quote(full, safe="")
        cmd = [provider.cli, "api", f"projects/{encoded}"]
        if provider.host:
            cmd.extend(["--hostname", provider.host])
        payload = _json_output(cmd, root)
        return payload if isinstance(payload, dict) else None
    return None


def _provider_remote_url(provider: Provider, upstream: str) -> str:
    if "://" in upstream or upstream.startswith("git@"):
        return upstream
    return f"https://{provider_host(provider)}/{source_identifier(upstream)}.git"


def fork_repositories(
    config: ProjectConfig,
    root: Path,
    provider_override: str,
    namespace: str | None,
    apply: bool,
    only: str = "upstream",
    remote_name: str = "personal",
) -> int:
    failed = False
    selected = [repo for repo in config.repositories if repo.source_type == only and repo.remote_mode == "fork"]
    if not selected:
        print("[INFO] no repositories match source_type=upstream remote_mode=fork")
        return 0
    for repo in selected:
        provider = config.provider_for(repo, provider_override, namespace)
        upstream = upstream_source_url(repo)
        if not upstream:
            print(f"[WARN] {repo.path}: fork mode requires fork_from/upstream_url")
            failed = True
            continue
        print(f"[FORK] {source_identifier(upstream)} -> {provider.namespace}/{repo.repo}")
        if provider.driver not in BUILTIN_PROVIDER_DRIVERS:
            result = execute_provider_plugin(
                provider, "fork", root, config=config, repo=repo, apply=apply,
                options={"upstream": upstream, "remote_name": remote_name},
            )
            if result is None:
                raise RuntimeError(f"provider plugin unavailable: {provider.driver}")
            if result.message:
                print(result.message)
            if result.code != 0:
                failed = True
                continue
        else:
            status = auth_status(provider, root, config)
            cmd = fork_command(provider, upstream, repo.repo, active_user=status.active_user)
            if not command_exists(provider.cli):
                print(f"[WARN] CLI missing: {provider.cli}")
                print(f"[DRY-RUN] {shlex_join(cmd)}")
                failed = failed or apply
                continue
            existing = provider_repo_payload(provider, repo, root, config)
            if existing:
                print(f"[SKIP] provider repository already exists: {provider.namespace}/{repo.repo}")
            else:
                code = run_interactive(cmd, cwd=root, dry_run=not apply, description=f"fork {repo.repo} on {provider.name}")
                if code != 0:
                    failed = True
                    continue
                if apply:
                    note_manual_rollback(f"delete provider fork {provider.namespace}/{repo.repo} manually if rollback is required")
                    # GitLab fork creation is asynchronous. Poll briefly so subsequent remote setup is less racy.
                    if provider.driver == "gitlab":
                        for _ in range(10):
                            payload = provider_repo_payload(provider, repo, root, config)
                            if payload and payload.get("import_status") in {None, "none", "finished"}:
                                break
                            time.sleep(1)
        worktree = root if repo.is_root else root / repo.path
        if worktree.exists() and run(["git", "rev-parse", "--is-inside-work-tree"], cwd=worktree).code == 0:
            expected = provider.expected_url(repo.repo, root=root)
            old = run(["git", "remote", "get-url", remote_name], cwd=worktree)
            previous = old.stdout if old.code == 0 else None
            if apply:
                track_git_remote(worktree, remote_name, previous)
            set_cmd = ["git", "remote", "set-url" if previous else "add", remote_name, expected]
            code = run_interactive(set_cmd, cwd=worktree, dry_run=not apply)
            failed = failed or code != 0
            upstream_name = "upstream"
            source_url = _provider_remote_url(provider, upstream)
            old_up = run(["git", "remote", "get-url", upstream_name], cwd=worktree)
            previous_up = old_up.stdout if old_up.code == 0 else None
            if apply:
                track_git_remote(worktree, upstream_name, previous_up)
            up_cmd = ["git", "remote", "set-url" if previous_up else "add", upstream_name, source_url]
            code = run_interactive(up_cmd, cwd=worktree, dry_run=not apply)
            failed = failed or code != 0
    return 1 if failed else 0


def mirror_repositories(
    config: ProjectConfig,
    root: Path,
    provider_override: str,
    namespace: str | None,
    apply: bool,
) -> int:
    failed = False
    for repo in [item for item in config.repositories if item.source_type == "upstream" and item.remote_mode == "mirror"]:
        provider = config.provider_for(repo, provider_override, namespace)
        destination = provider.expected_url(repo.repo, root=root)
        bare = local_bare_path(repo, remotes_dir(config, root))
        if not bare.exists():
            print(f"[WARN] {repo.repo}: local mirror missing; run `rfm local remotes --mirror-sources --apply`")
            failed = True
            continue
        cmd = ["git", f"--git-dir={bare}", "push", "--mirror", destination]
        code = run_interactive(cmd, cwd=root, dry_run=not apply, description=f"mirror {repo.repo} to {provider.name}")
        if code == 0 and apply:
            note_manual_rollback(
                f"provider mirror {provider.namespace}/{repo.repo} changed remote refs; restore from a verified backup or previous mirror manually"
            )
        failed = failed or code != 0
    return 1 if failed else 0


def _payload_topics(provider: Provider, payload: dict) -> list[str]:
    if provider.driver == "github":
        return sorted(str(item) for item in (payload.get("topics") or []))
    return sorted(str(item) for item in (payload.get("topics") or payload.get("tag_list") or []))


def _repair_command(provider: Provider, repo: Repository, payload: dict) -> list[str] | None:
    full = f"{provider.namespace}/{repo.repo}"
    expected_visibility = repo.visibility
    expected_topics = sorted(set(repo.topics))
    current_topics = _payload_topics(provider, payload)
    if provider.driver == "github":
        host = provider_host(provider)
        github_full = full if host == "github.com" else f"{host}/{full}"
        cmd = [provider.cli, "repo", "edit", github_full]
        if payload.get("default_branch") != repo.branch:
            cmd.extend(["--default-branch", repo.branch])
        if expected_visibility and payload.get("visibility", "").lower() != expected_visibility.lower():
            cmd.extend(["--visibility", expected_visibility, "--accept-visibility-change-consequences"])
        for topic in sorted(set(current_topics) - set(expected_topics)):
            cmd.extend(["--remove-topic", topic])
        for topic in sorted(set(expected_topics) - set(current_topics)):
            cmd.extend(["--add-topic", topic])
        return cmd if len(cmd) > 4 else None
    if provider.driver == "gitlab":
        encoded = quote(full, safe="")
        cmd = [provider.cli, "api", f"projects/{encoded}", "--method", "PUT"]
        if payload.get("default_branch") != repo.branch:
            cmd.extend(["-f", f"default_branch={repo.branch}"])
        if expected_visibility and payload.get("visibility") != expected_visibility:
            cmd.extend(["-f", f"visibility={expected_visibility}"])
        if expected_topics != current_topics:
            for topic in expected_topics:
                cmd.extend(["-f", f"topics[]={topic}"])
            if not expected_topics:
                cmd.extend(["-f", "topics="])
        if provider.host:
            cmd.extend(["--hostname", provider.host])
        return cmd if len(cmd) > 5 else None
    return None


def reconcile_repositories(
    config: ProjectConfig,
    root: Path,
    provider_override: str,
    namespace: str | None,
    json_output: bool = False,
    apply: bool = False,
) -> int:
    rows: list[dict] = []
    for repo in config.repositories:
        provider = config.provider_for(repo, provider_override, namespace)
        if provider.driver not in BUILTIN_PROVIDER_DRIVERS:
            result = execute_provider_plugin(provider, "reconcile", root, config=config, repo=repo, apply=apply)
            if result is None:
                raise RuntimeError(f"provider plugin unavailable: {provider.driver}")
            row = dict(result.data or {})
            row.setdefault("repo", repo.repo); row.setdefault("path", repo.path); row.setdefault("provider", provider.name)
            row.setdefault("driver", provider.driver); row.setdefault("destination", f"{provider.namespace}/{repo.repo}")
            row.setdefault("issues", [] if result.code == 0 else [result.message or "plugin-reconcile-failed"]); rows.append(row)
            continue
        payload = provider_repo_payload(provider, repo, root, config) if command_exists(provider.cli) else None
        upstream = source_identifier(repo.upstream) if repo.upstream else None
        row = {
            "repo": repo.repo,
            "path": repo.path,
            "provider": provider.name,
            "driver": provider.driver,
            "destination": f"{provider.namespace}/{repo.repo}",
            "exists": payload is not None,
            "source_type": repo.source_type,
            "remote_mode": repo.remote_mode,
            "configured_upstream": upstream,
            "remote_default_branch": payload.get("default_branch") if payload else None,
            "expected_default_branch": repo.branch,
            "remote_visibility": (payload.get("visibility") or "").lower() if payload else None,
            "expected_visibility": repo.visibility,
            "remote_topics": _payload_topics(provider, payload) if payload else [],
            "expected_topics": sorted(set(repo.topics)),
            "is_fork": bool(payload.get("fork")) if payload and provider.driver == "github" else bool(payload.get("forked_from_project")) if payload else None,
            "remote_upstream": (
                payload.get("parent", {}).get("full_name") if payload and provider.driver == "github" else
                payload.get("forked_from_project", {}).get("path_with_namespace") if payload else None
            ),
            "repair_attempted": False,
            "repair_code": None,
        }
        issues: list[str] = []
        if not row["exists"]:
            issues.append("remote-missing-or-auth-failed")
        if repo.remote_mode == "fork" and row["exists"] and not row["is_fork"]:
            issues.append("expected-fork-relationship")
        if repo.remote_mode == "fork" and upstream and row["remote_upstream"] and upstream != row["remote_upstream"]:
            issues.append("fork-parent-mismatch")
        if row["remote_default_branch"] and row["remote_default_branch"] != repo.branch:
            issues.append("default-branch-mismatch")
        if repo.visibility and row["remote_visibility"] and row["remote_visibility"] != repo.visibility:
            issues.append("visibility-mismatch")
        if repo.topics and row["remote_topics"] != sorted(set(repo.topics)):
            issues.append("topics-mismatch")
        if apply and payload:
            cmd = _repair_command(provider, repo, payload)
            if cmd:
                row["repair_attempted"] = True
                row["repair_code"] = run_interactive(cmd, cwd=root, dry_run=False, description=f"reconcile {repo.repo} on {provider.name}")
                if row["repair_code"] == 0:
                    note_manual_rollback(
                        f"restore provider metadata for {provider.namespace}/{repo.repo} manually from the pre-reconcile payload if rollback is required"
                    )
                    issues = [item for item in issues if item in {"expected-fork-relationship", "fork-parent-mismatch"}]
        row["issues"] = issues
        rows.append(row)
    if json_output:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            mark = "OK" if not row["issues"] else "WARN"
            print(f"[{mark}] {row['destination']} mode={row['remote_mode']} exists={row['exists']} branch={row['remote_default_branch'] or '-'}")
            print(f"      visibility={row['remote_visibility'] or '-'} topics={','.join(row['remote_topics']) or '-'}")
            if row["configured_upstream"]:
                print(f"      upstream configured={row['configured_upstream']} remote={row['remote_upstream'] or '-'}")
            if row["repair_attempted"]:
                print(f"      repair_code={row['repair_code']}")
            if row["issues"]:
                print(f"      issues={','.join(row['issues'])}")
    return 2 if any(row["issues"] for row in rows) else 0
