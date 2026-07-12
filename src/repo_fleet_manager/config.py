from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Provider:
    name: str
    namespace: str
    url_template: str
    cli: str
    host: str | None = None
    type: str = "remote"

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
    include_roots: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_root(self) -> bool:
        return self.path in {".", ""} or self.kind == "root"

    @property
    def service_name(self) -> str:
        return self.compose_service or Path(self.path).name

    @property
    def source_type(self) -> str:
        """Lifecycle/source category for local materialization.

        Supported values:
        - new: create a new repository/worktree when missing.
        - upstream: mirror/clone from an external Git URL first.
        - existing: import or publish a repository that already exists locally.

        The value is intentionally inferred from legacy fields so older configs keep working.
        """
        raw = self.extra.get("source_type") or self.extra.get("lifecycle") or self.extra.get("repo_state")
        if raw:
            value = str(raw).strip().lower().replace("-", "_")
            aliases = {
                "create": "new",
                "created": "existing",
                "fresh": "new",
                "fork": "upstream",
                "mirror": "upstream",
                "external": "upstream",
                "import": "existing",
                "preexisting": "existing",
                "pre_existing": "existing",
                "local": "existing",
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


@dataclass(slots=True)
class ProjectConfig:
    path: Path
    project: dict[str, Any]
    providers: dict[str, Provider]
    repositories: list[Repository]
    compose: dict[str, Any]
    fingerprint: dict[str, Any]
    local: dict[str, Any]

    @property
    def default_provider_name(self) -> str:
        return str(self.project.get("default_provider") or next(iter(self.providers)))

    @property
    def root_repository(self) -> Repository | None:
        for repo in self.repositories:
            if repo.is_root:
                return repo
        return None

    def provider_for(self, repo: Repository, override: str | None = None, namespace: str | None = None) -> Provider:
        name = override or repo.provider or self.default_provider_name
        if name not in self.providers:
            raise KeyError(f"unknown provider: {name}")
        provider = self.providers[name]
        if namespace:
            return Provider(provider.name, namespace, provider.url_template, provider.cli, provider.host, provider.type)
        return provider

    def submodules(self) -> list[Repository]:
        return [repo for repo in self.repositories if not repo.is_root]

    def services(self) -> list[Repository]:
        return [repo for repo in self.repositories if repo.kind == "service" or repo.host_port is not None]


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
    raise FileNotFoundError("repo-fleet.json not found. Pass --config or copy configs/goftaroo.example.json.")


def load_config(path: str | Path | None = None) -> ProjectConfig:
    config_path = find_config(explicit=str(path)) if path else find_config()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    local_cfg = raw.get("local", {})
    providers = {}
    for name, data in raw.get("providers", {}).items():
        provider_type = str(data.get("type") or data.get("kind") or ("local" if name == "local" else "remote"))
        default_url_template = "file://{root}/{namespace}/{repo}.git" if provider_type == "local" else None
        url_template = data.get("url_template") or default_url_template
        if not url_template:
            raise ValueError(f"provider {name!r} must define url_template")
        namespace = str(data.get("namespace") or data.get("owner") or data.get("group") or "")
        if provider_type == "local" and not namespace:
            namespace = str(local_cfg.get("remotes_dir") or ".repo-fleet/remotes")
        providers[name] = Provider(
            name=name,
            namespace=namespace,
            url_template=str(url_template),
            cli=str(data.get("cli") or ("git" if provider_type == "local" else name)),
            host=data.get("host"),
            type=provider_type,
        )
    if not providers:
        raise ValueError("config must define at least one provider")
    repositories = []
    known_keys = {
        "path", "repo", "kind", "provider", "branch", "host_port", "compose_service",
        "docker_context", "dockerfile", "health_url", "description", "include_roots",
    }
    for item in raw.get("repositories", []):
        known = {k: item.get(k) for k in known_keys if k in item}
        extra = {k: v for k, v in item.items() if k not in known_keys}
        repositories.append(Repository(**known, extra=extra))
    return ProjectConfig(
        path=config_path.resolve(),
        project=raw.get("project", {}),
        providers=providers,
        repositories=repositories,
        compose=raw.get("compose", {}),
        fingerprint=raw.get("fingerprint", {}),
        local=local_cfg,
    )
