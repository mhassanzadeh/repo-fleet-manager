from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import CURRENT_SCHEMA_VERSION, migrate_config_data, validate_or_raise
from .profiles import resolve_config_data


@dataclass(slots=True)
class Provider:
    name: str
    namespace: str
    url_template: str
    cli: str
    host: str | None = None
    type: str = "remote"
    driver: str = "generic"
    profile: str | None = None
    user: str | None = None
    required_scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.driver == "generic":
            name = self.name.lower()
            cli = self.cli.lower()
            host = (self.host or "").lower()
            if self.type == "local" or name == "local" or self.url_template.startswith("file://"):
                self.driver = "local"
            elif cli == "gh" or name == "github" or "github" in host:
                self.driver = "github"
            elif cli == "glab" or name == "gitlab" or "gitlab" in host:
                self.driver = "gitlab"

    @property
    def is_local(self) -> bool:
        return self.type == "local" or self.name == "local" or self.url_template.startswith("file://")

    def expected_url(self, repo: str, root: str | Path | None = None) -> str:
        root_text = ""
        if root is not None:
            root_text = Path(root).expanduser().resolve().as_posix()
        return self.url_template.format(namespace=self.namespace, repo=repo, host=self.host or "", root=root_text)


@dataclass(slots=True)
class Repository:
    path: str
    repo: str
    kind: str = "module"
    provider: str | None = None
    branch: str = "main"
    host_port: int | None = None
    compose_service: str | None = None
    docker_context: str | None = None
    dockerfile: str | None = None
    health_url: str | None = None
    description: str | None = None
    visibility: str | None = None
    topics: list[str] = field(default_factory=list)
    include_roots: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_root(self) -> bool:
        return self.path in {".", ""} or self.kind == "root"

    @property
    def service_name(self) -> str:
        return self.compose_service or Path(self.path).name

    @property
    def source_type(self) -> str:
        raw = self.extra.get("source_type") or self.extra.get("lifecycle") or self.extra.get("repo_state")
        if raw:
            value = str(raw).strip().lower().replace("-", "_")
            aliases = {
                "create": "new", "created": "existing", "fresh": "new", "fork": "upstream",
                "mirror": "upstream", "external": "upstream", "import": "existing",
                "preexisting": "existing", "pre_existing": "existing", "local": "existing",
            }
            value = aliases.get(value, value)
            if value in {"new", "upstream", "existing"}:
                return value
        upstream_keys = {"mirror_source", "upstream_url", "source_url", "fork_from", "clone_url"}
        existing_keys = {"existing_path", "local_source", "import_from"}
        if any(self.extra.get(key) for key in upstream_keys):
            return "upstream"
        if any(self.extra.get(key) for key in existing_keys):
            return "existing"
        return "new"

    @property
    def remote_mode(self) -> str:
        raw = self.extra.get("remote_mode") or self.extra.get("provider_action") or self.extra.get("publish_mode")
        if raw:
            return str(raw).strip().lower().replace("-", "_")
        if self.source_type == "upstream":
            if self.extra.get("fork_from"):
                return "fork"
            if self.extra.get("mirror") is True or self.extra.get("mirror_source"):
                return "mirror"
        return "create"

    @property
    def upstream(self) -> str | None:
        for key in ("fork_from", "upstream_url", "mirror_source", "source_url", "clone_url"):
            if self.extra.get(key):
                return str(self.extra[key])
        return None


@dataclass(slots=True)
class ProjectConfig:
    path: Path
    schema_version: str
    raw: dict[str, Any]
    migration_changes: list[str]
    project: dict[str, Any]
    providers: dict[str, Provider]
    repositories: list[Repository]
    compose: dict[str, Any]
    runtime: dict[str, Any]
    fingerprint: dict[str, Any]
    local: dict[str, Any]
    active_profiles: tuple[str, ...] = ()
    active_groups: tuple[str, ...] = ()
    resolution_changes: list[str] = field(default_factory=list)

    @property
    def default_provider_name(self) -> str:
        return str(self.project.get("default_provider") or next(iter(self.providers)))

    @property
    def root_repository(self) -> Repository | None:
        for repo in self.repositories:
            if repo.is_root:
                return repo
        return None

    @property
    def default_jobs(self) -> int:
        return max(1, int(self.local.get("default_jobs") or 1))

    def provider_for(self, repo: Repository, override: str | None = None, namespace: str | None = None) -> Provider:
        name = override or repo.provider or self.default_provider_name
        if name not in self.providers:
            raise KeyError(f"unknown provider: {name}")
        provider = self.providers[name]
        if namespace:
            return Provider(
                provider.name, namespace, provider.url_template, provider.cli, provider.host,
                provider.type, provider.driver, provider.profile, provider.user, provider.required_scopes,
            )
        return provider

    def submodules(self) -> list[Repository]:
        return [repo for repo in self.repositories if not repo.is_root]

    def services(self) -> list[Repository]:
        return [repo for repo in self.repositories if repo.kind == "service" or repo.host_port is not None]

    def repository_map(self) -> dict[str, Repository]:
        result: dict[str, Repository] = {}
        for repo in self.repositories:
            result[repo.repo] = repo
            result[repo.path] = repo
        return result


def find_config(start: Path | None = None, explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_absolute() else Path.cwd() / path
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        for name in ("repo-fleet.json", "repo-fleet.config.json"):
            candidate = directory / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError("repo-fleet.json not found. Pass --config or copy configs/repo-fleet.example.json.")


def load_raw_config(path: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    config_path = find_config(explicit=str(path)) if path else find_config()
    return config_path.resolve(), json.loads(config_path.read_text(encoding="utf-8"))


def load_config(
    path: str | Path | None = None,
    *,
    profiles: str | list[str] | tuple[str, ...] | None = None,
    groups: str | list[str] | tuple[str, ...] | None = None,
) -> ProjectConfig:
    config_path, raw = load_raw_config(path)
    migrated, changes = migrate_config_data(raw)
    validate_or_raise(migrated)
    resolved, active_profiles, active_groups, resolution_changes = resolve_config_data(
        migrated, profiles=profiles, groups=groups
    )
    validate_or_raise(resolved)
    local_cfg = resolved.get("local", {})
    providers: dict[str, Provider] = {}
    for name, data in resolved.get("providers", {}).items():
        provider_type = str(data.get("type") or data.get("kind") or ("local" if name == "local" else "remote"))
        default_url_template = "file://{root}/{namespace}/{repo}.git" if provider_type == "local" else None
        url_template = data.get("url_template") or default_url_template
        if not url_template:
            raise ValueError(f"provider {name!r} must define url_template")
        namespace = str(data.get("namespace") or data.get("owner") or data.get("group") or "")
        if provider_type == "local" and not namespace:
            namespace = str(local_cfg.get("remotes_dir") or ".repo-fleet/remotes")
        cli = str(data.get("cli") or ("git" if provider_type == "local" else name))
        driver = str(data.get("driver") or (
            "local" if provider_type == "local" else
            "github" if cli == "gh" or str(data.get("host") or "").lower().endswith("github.com") or name == "github" else
            "gitlab" if cli == "glab" or "gitlab" in str(data.get("host") or "").lower() or name == "gitlab" else
            "generic"
        ))
        providers[name] = Provider(
            name=name,
            namespace=namespace,
            url_template=str(url_template),
            cli=cli,
            host=data.get("host"),
            type=provider_type,
            driver=driver,
            profile=data.get("profile"),
            user=data.get("user"),
            required_scopes=tuple(str(item) for item in (data.get("required_scopes") or [])),
        )
    repositories: list[Repository] = []
    known_keys = {
        "path", "repo", "kind", "provider", "branch", "host_port", "compose_service",
        "docker_context", "dockerfile", "health_url", "description", "visibility", "topics", "include_roots", "depends_on", "tags",
    }
    for item in resolved.get("repositories", []):
        known = {k: item.get(k) for k in known_keys if k in item}
        extra = {k: v for k, v in item.items() if k not in known_keys}
        repositories.append(Repository(**known, extra=extra))
    return ProjectConfig(
        path=config_path,
        schema_version=str(resolved.get("schema_version") or CURRENT_SCHEMA_VERSION),
        raw=resolved,
        migration_changes=changes,
        project=resolved.get("project", {}),
        providers=providers,
        repositories=repositories,
        compose=resolved.get("compose", {}),
        runtime=resolved.get("runtime", {}),
        fingerprint=resolved.get("fingerprint", {}),
        local=local_cfg,
        active_profiles=active_profiles,
        active_groups=active_groups,
        resolution_changes=resolution_changes,
    )
