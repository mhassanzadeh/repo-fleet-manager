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

    def expected_url(self, repo: str) -> str:
        return self.url_template.format(namespace=self.namespace, repo=repo, host=self.host or "")


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


@dataclass(slots=True)
class ProjectConfig:
    path: Path
    project: dict[str, Any]
    providers: dict[str, Provider]
    repositories: list[Repository]
    compose: dict[str, Any]
    fingerprint: dict[str, Any]

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
            return Provider(provider.name, namespace, provider.url_template, provider.cli, provider.host)
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
    providers = {
        name: Provider(
            name=name,
            namespace=str(data.get("namespace") or data.get("owner") or data.get("group") or ""),
            url_template=str(data["url_template"]),
            cli=str(data.get("cli") or name),
            host=data.get("host"),
        )
        for name, data in raw.get("providers", {}).items()
    }
    if not providers:
        raise ValueError("config must define at least one provider")
    repositories = []
    for item in raw.get("repositories", []):
        known = {k: item.get(k) for k in [
            "path", "repo", "kind", "provider", "branch", "host_port", "compose_service",
            "docker_context", "dockerfile", "health_url", "description", "include_roots"
        ] if k in item}
        extra = {k: v for k, v in item.items() if k not in known}
        repositories.append(Repository(**known, extra=extra))
    return ProjectConfig(
        path=config_path.resolve(),
        project=raw.get("project", {}),
        providers=providers,
        repositories=repositories,
        compose=raw.get("compose", {}),
        fingerprint=raw.get("fingerprint", {}),
    )
