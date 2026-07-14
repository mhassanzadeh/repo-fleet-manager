from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from jsonschema import Draft202012Validator

CURRENT_SCHEMA_VERSION = "1.0.0"
LEGACY_SCHEMA_VERSION = "0.5.0"
SOURCE_SCHEMA_ALIASES = {
    "0.3": "0.3.0",
    "0.3.0": "0.3.0",
    "0.4": "0.4.0",
    "0.4.0": "0.4.0",
    "0.5": "0.5.0",
    "0.5.0": "0.5.0",
    "0.6": "0.6.0",
    "0.6.0": "0.6.0",
    "1.0": CURRENT_SCHEMA_VERSION,
    CURRENT_SCHEMA_VERSION: CURRENT_SCHEMA_VERSION,
}
SENSITIVE_KEYS = {
    "token", "access_token", "private_token", "password", "client_secret",
    "private_key", "ssh_private_key", "api_key", "github_token", "gitlab_token",
}


@dataclass(slots=True)
class ValidationIssue:
    path: str
    message: str
    code: str
    remediation: str | None = None

    def render(self) -> str:
        text = f"{self.path or '$'}: {self.message} [{self.code}]"
        if self.remediation:
            text += f"; remediation: {self.remediation}"
        return text


class ConfigValidationError(ValueError):
    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = list(issues)
        super().__init__("configuration validation failed:\n" + "\n".join(f" - {i.render()}" for i in self.issues))


def schema_path() -> Path:
    return Path(str(files("repo_fleet_manager").joinpath("data/repo-fleet.schema.json")))


def load_schema() -> dict[str, Any]:
    return json.loads(schema_path().read_text(encoding="utf-8"))


def _json_path(parts: Iterable[Any]) -> str:
    text = "$"
    for part in parts:
        if isinstance(part, int):
            text += f"[{part}]"
        else:
            text += f".{part}"
    return text


def _walk_sensitive(value: Any, path: tuple[Any, ...] = ()) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS:
                issues.append(ValidationIssue(_json_path((*path, key)), "secrets and tokens must not be stored in repo-fleet.json", "secret-in-config"))
            issues.extend(_walk_sensitive(item, (*path, key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            issues.extend(_walk_sensitive(item, (*path, index)))
    return issues


def _repo_identity(item: dict[str, Any]) -> str:
    return str(item.get("repo") or item.get("path") or "")


def _normalize_dependency(dep: str, by_name: dict[str, dict[str, Any]], by_path: dict[str, dict[str, Any]]) -> str | None:
    if dep in by_name:
        return _repo_identity(by_name[dep])
    if dep in by_path:
        return _repo_identity(by_path[dep])
    return None


def _dependency_issues(repositories: list[dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    by_name = {str(item.get("repo")): item for item in repositories if item.get("repo")}
    by_path = {str(item.get("path")): item for item in repositories if item.get("path")}
    graph: dict[str, list[str]] = {}
    for index, item in enumerate(repositories):
        name = _repo_identity(item)
        graph[name] = []
        for dep in item.get("depends_on") or []:
            resolved = _normalize_dependency(str(dep), by_name, by_path)
            if not resolved:
                issues.append(ValidationIssue(f"$.repositories[{index}].depends_on", f"unknown dependency: {dep}", "unknown-dependency"))
                continue
            if resolved == name:
                issues.append(ValidationIssue(f"$.repositories[{index}].depends_on", "repository cannot depend on itself", "self-dependency"))
                continue
            graph[name].append(resolved)

    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> None:
        marker = state.get(node, 0)
        if marker == 2:
            return
        if marker == 1:
            try:
                start = stack.index(node)
                cycle = stack[start:] + [node]
            except ValueError:
                cycle = stack + [node]
            issues.append(ValidationIssue("$.repositories", "dependency cycle: " + " -> ".join(cycle), "dependency-cycle"))
            return
        state[node] = 1
        stack.append(node)
        for dep in graph.get(node, []):
            visit(dep)
        stack.pop()
        state[node] = 2

    for node in graph:
        visit(node)
    return issues




def _profile_and_group_issues(data: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    profiles = data.get("profiles") or {}
    graph: dict[str, list[str]] = {}
    for name, raw in profiles.items():
        extends = raw.get("extends") if isinstance(raw, dict) else None
        if extends is None:
            parents: list[str] = []
        elif isinstance(extends, str):
            parents = [part.strip() for part in extends.split(",") if part.strip()]
        else:
            parents = [str(item) for item in extends]
        graph[str(name)] = parents
        for parent in parents:
            if parent not in profiles:
                issues.append(ValidationIssue(
                    f"$.profiles.{name}.extends",
                    f"unknown parent profile: {parent}",
                    "unknown-profile",
                ))

    state: dict[str, int] = {}
    stack: list[str] = []
    def visit(name: str) -> None:
        marker = state.get(name, 0)
        if marker == 2:
            return
        if marker == 1:
            try:
                start = stack.index(name)
                cycle = stack[start:] + [name]
            except ValueError:
                cycle = stack + [name]
            issues.append(ValidationIssue(
                "$.profiles",
                "profile inheritance cycle: " + " -> ".join(cycle),
                "profile-cycle",
            ))
            return
        state[name] = 1
        stack.append(name)
        for parent in graph.get(name, []):
            if parent in graph:
                visit(parent)
        stack.pop()
        state[name] = 2
    for name in graph:
        visit(name)

    repositories = data.get("repositories") or []
    selectors = {str(item.get("repo")) for item in repositories if item.get("repo")}
    selectors.update(str(item.get("path")) for item in repositories if item.get("path") is not None)
    known_tags = {str(tag) for item in repositories for tag in (item.get("tags") or [])}
    for profile in profiles.values():
        if not isinstance(profile, dict):
            continue
        for selector, overlay in (profile.get("repositories") or {}).items():
            selectors.add(str(selector))
            if not isinstance(overlay, dict):
                continue
            if overlay.get("repo"):
                selectors.add(str(overlay["repo"]))
            if overlay.get("path") is not None:
                selectors.add(str(overlay["path"]))
            known_tags.update(str(tag) for tag in (overlay.get("tags") or []))
    for name, raw in (data.get("groups") or {}).items():
        if isinstance(raw, list):
            group_repositories = raw
            group_tags: list[str] = []
        elif isinstance(raw, dict):
            group_repositories = raw.get("repositories") or []
            group_tags = raw.get("tags") or []
        else:
            continue
        for selector in group_repositories:
            if str(selector) not in selectors:
                issues.append(ValidationIssue(
                    f"$.groups.{name}.repositories",
                    f"unknown repository selector: {selector}",
                    "unknown-group-repository",
                ))
        for tag in group_tags:
            if str(tag) not in known_tags:
                issues.append(ValidationIssue(
                    f"$.groups.{name}.tags",
                    f"tag does not match any repository: {tag}",
                    "unknown-group-tag",
                ))
    return issues



def _runtime_issues(data: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    runtime = data.get("runtime") or {}
    services = runtime.get("services") or {} if isinstance(runtime, dict) else {}
    if not isinstance(services, dict):
        return issues
    graph: dict[str, list[str]] = {}
    for name, raw in services.items():
        dependencies = [str(item) for item in (raw.get("depends_on") or [])] if isinstance(raw, dict) else []
        graph[str(name)] = dependencies
        for dependency in dependencies:
            if dependency == name:
                issues.append(ValidationIssue(
                    f"$.runtime.services.{name}.depends_on",
                    "runtime service cannot depend on itself",
                    "runtime-self-dependency",
                ))
            elif dependency not in services:
                issues.append(ValidationIssue(
                    f"$.runtime.services.{name}.depends_on",
                    f"unknown runtime service dependency: {dependency}",
                    "unknown-runtime-dependency",
                ))

    state: dict[str, int] = {}
    stack: list[str] = []
    def visit(name: str) -> None:
        marker = state.get(name, 0)
        if marker == 2:
            return
        if marker == 1:
            try:
                start = stack.index(name)
                cycle = stack[start:] + [name]
            except ValueError:
                cycle = stack + [name]
            issues.append(ValidationIssue(
                "$.runtime.services",
                "runtime dependency cycle: " + " -> ".join(cycle),
                "runtime-dependency-cycle",
            ))
            return
        state[name] = 1
        stack.append(name)
        for dependency in graph.get(name, []):
            if dependency in graph:
                visit(dependency)
        stack.pop()
        state[name] = 2
    for name in graph:
        visit(name)
    return issues



def _supply_chain_issues(data: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    config = data.get("supply_chain") or {}
    if not isinstance(config, dict):
        return issues
    services = config.get("services") or {}
    service_enforcement = any(
        isinstance(value, dict) and (value.get("require_signature") or value.get("require_attestation"))
        for value in services.values()
    ) if isinstance(services, dict) else False
    signature_required = bool(config.get("require_signature"))
    attestation_required = bool(config.get("require_attestation"))
    if signature_required or attestation_required or service_enforcement:
        cosign = config.get("cosign") or {}
        key = cosign.get("key") if isinstance(cosign, dict) else None
        identity = cosign.get("certificate_identity") if isinstance(cosign, dict) else None
        issuer = cosign.get("certificate_oidc_issuer") if isinstance(cosign, dict) else None
        if not key and not (identity and issuer):
            issues.append(ValidationIssue(
                "$.supply_chain.cosign",
                "signature or attestation enforcement requires a public key/KMS URI or certificate identity and OIDC issuer",
                "missing-cosign-trust-policy",
                "configure cosign.key or both certificate_identity and certificate_oidc_issuer",
            ))
    return issues

def semantic_issues(data: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    providers = data.get("providers") or {}
    default_provider = (data.get("project") or {}).get("default_provider")
    if default_provider and default_provider not in providers:
        issues.append(ValidationIssue("$.project.default_provider", f"provider is not defined: {default_provider}", "unknown-provider"))

    repositories = data.get("repositories") or []
    seen_paths: dict[str, int] = {}
    seen_repos: dict[str, int] = {}
    root_count = 0
    normalized_paths: list[tuple[int, str]] = []
    for index, item in enumerate(repositories):
        path = str(item.get("path") or "")
        repo = str(item.get("repo") or "")
        provider = item.get("provider")
        if provider and provider not in providers:
            issues.append(ValidationIssue(f"$.repositories[{index}].provider", f"provider is not defined: {provider}", "unknown-provider"))
        if path in {"", "."} or item.get("kind") == "root":
            root_count += 1
        else:
            pure = PurePosixPath(path.replace("\\", "/"))
            if pure.is_absolute() or ".." in pure.parts:
                issues.append(ValidationIssue(f"$.repositories[{index}].path", "path must be relative and cannot escape the workspace", "unsafe-path"))
            normalized = str(pure)
            normalized_paths.append((index, normalized))
        if path in seen_paths:
            issues.append(ValidationIssue(f"$.repositories[{index}].path", f"duplicate path also used at repositories[{seen_paths[path]}]", "duplicate-path"))
        seen_paths[path] = index
        if repo in seen_repos:
            issues.append(ValidationIssue(f"$.repositories[{index}].repo", f"duplicate repository name also used at repositories[{seen_repos[repo]}]", "duplicate-repo"))
        seen_repos[repo] = index

    if root_count > 1:
        issues.append(ValidationIssue("$.repositories", "only one root repository can be declared", "multiple-roots"))

    for i, (index_a, path_a) in enumerate(normalized_paths):
        parts_a = PurePosixPath(path_a).parts
        for index_b, path_b in normalized_paths[i + 1:]:
            parts_b = PurePosixPath(path_b).parts
            if parts_a == parts_b:
                continue
            if parts_a == parts_b[: len(parts_a)] or parts_b == parts_a[: len(parts_b)]:
                issues.append(ValidationIssue(
                    "$.repositories",
                    f"nested repository paths collide: repositories[{index_a}]={path_a} and repositories[{index_b}]={path_b}",
                    "nested-path-collision",
                ))

    issues.extend(_dependency_issues(repositories))
    issues.extend(_profile_and_group_issues(data))
    issues.extend(_runtime_issues(data))
    issues.extend(_supply_chain_issues(data))
    issues.extend(_walk_sensitive(data))
    return issues


def _schema_issue(error: Any) -> ValidationIssue:
    path = _json_path(error.absolute_path)
    remediation: str | None = None
    code = f"schema-{error.validator}" if error.validator else "schema"
    if error.validator == "additionalProperties":
        remediation = "fix the field name, move custom data under metadata, or prefix extension fields with x-"
    elif error.validator == "required":
        remediation = "add the required field shown in the error"
    elif error.validator == "const" and path == "$.schema_version":
        remediation = f"run `rfm config migrate --apply` to write schema_version {CURRENT_SCHEMA_VERSION}"
    elif error.validator == "enum":
        remediation = "use one of the allowed values listed in the error"
    elif error.validator in {"pattern", "minLength", "minimum", "maximum"}:
        remediation = "correct the value at this JSON path"
    elif error.validator in {"anyOf", "oneOf", "allOf"}:
        remediation = "provide the lifecycle/source fields required by the selected source_type or remote_mode"
    return ValidationIssue(path, error.message, code, remediation)


def validate_config_data(data: dict[str, Any]) -> list[ValidationIssue]:
    validator = Draft202012Validator(load_schema())
    issues = [
        _schema_issue(error)
        for error in sorted(validator.iter_errors(data), key=lambda item: (list(item.absolute_path), str(item.message)))
    ]
    issues.extend(semantic_issues(data))
    return issues


def validate_or_raise(data: dict[str, Any]) -> None:
    issues = validate_config_data(data)
    if issues:
        raise ConfigValidationError(issues)


def _pop_alias(mapping: dict[str, Any], aliases: tuple[str, ...]) -> tuple[str | None, Any]:
    for key in aliases:
        if key in mapping:
            return key, mapping.pop(key)
    return None, None


def _repository_list(value: Any, source_key: str, changes: list[str]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        result = [copy.deepcopy(item) for item in value if isinstance(item, dict)]
        if len(result) != len(value):
            changes.append(f"{source_key}: ignored non-object repository entries")
        return result
    if isinstance(value, dict):
        result: list[dict[str, Any]] = []
        for key, raw in value.items():
            if isinstance(raw, dict):
                item = copy.deepcopy(raw)
            elif isinstance(raw, str):
                item = {"upstream_url": raw}
            else:
                changes.append(f"{source_key}.{key}: ignored unsupported repository entry")
                continue
            item.setdefault("repo", str(key))
            item.setdefault("path", "." if str(key) in {"root", "."} else str(key))
            result.append(item)
        changes.append(f"{source_key}: object map converted to repository list")
        return result
    return []


def _migrate_repository_aliases(migrated: dict[str, Any], changes: list[str]) -> None:
    repositories = migrated.get("repositories")
    legacy_keys = ("repos", "modules", "services", "projects")
    if repositories is None:
        key, value = _pop_alias(migrated, legacy_keys)
        if key is not None:
            migrated["repositories"] = _repository_list(value, key, changes)
            changes.append(f"{key} renamed to repositories")
    else:
        merged = _repository_list(repositories, "repositories", changes)
        for key in legacy_keys:
            if key not in migrated:
                continue
            extra = _repository_list(migrated.pop(key), key, changes)
            existing = {(str(item.get("path")), str(item.get("repo"))) for item in merged}
            for item in extra:
                identity = (str(item.get("path")), str(item.get("repo")))
                if identity not in existing:
                    merged.append(item)
                    existing.add(identity)
            changes.append(f"{key} merged into repositories")
        migrated["repositories"] = merged

    for index, repo in enumerate(migrated.get("repositories") or []):
        if not isinstance(repo, dict):
            continue
        alias_map = {
            "repo": ("name", "repository", "repo_name"),
            "path": ("directory", "dir", "local_path", "workspace_path"),
            "branch": ("default_branch",),
            "provider": ("provider_name",),
            "source_type": ("lifecycle", "repo_state"),
            "remote_mode": ("provider_action", "publish_mode"),
            "upstream_url": ("upstream", "source"),
        }
        for destination, aliases in alias_map.items():
            if destination in repo:
                for alias in aliases:
                    if alias in repo:
                        repo.pop(alias)
                        changes.append(f"repositories[{index}].{alias} removed; {destination} already exists")
                continue
            alias, value = _pop_alias(repo, aliases)
            if alias is not None:
                repo[destination] = value
                changes.append(f"repositories[{index}].{alias} renamed to {destination}")


def _migrate_project_aliases(migrated: dict[str, Any], changes: list[str]) -> None:
    raw_project = migrated.get("project")
    if isinstance(raw_project, str):
        project: dict[str, Any] = {"name": raw_project}
        migrated["project"] = project
        changes.append("project string converted to project.name")
    elif isinstance(raw_project, dict):
        project = raw_project
    else:
        project = {}
        migrated["project"] = project
        if raw_project is not None:
            changes.append("invalid project value replaced with an object")

    aliases = {
        "name": ("project_name", "name"),
        "default_provider": ("default_provider",),
        "default_branch": ("default_branch",),
        "env_prefix": ("env_prefix",),
        "build_dir": ("build_dir",),
        "description": ("description",),
    }
    for destination, source_names in aliases.items():
        if destination in project:
            for source_name in source_names:
                if source_name in migrated:
                    migrated.pop(source_name)
                    changes.append(f"top-level {source_name} removed; project.{destination} already exists")
            continue
        source_name, value = _pop_alias(migrated, source_names)
        if source_name is not None:
            project[destination] = value
            changes.append(f"top-level {source_name} moved to project.{destination}")

    repositories = migrated.get("repositories") or []
    if not project.get("name"):
        root = next(
            (
                item for item in repositories
                if isinstance(item, dict) and (item.get("path") in {None, "", "."} or item.get("kind") == "root")
            ),
            None,
        )
        candidate = (root or (repositories[0] if repositories else {})).get("repo") if isinstance(root or (repositories[0] if repositories else {}), dict) else None
        if candidate:
            project["name"] = str(candidate)
            changes.append("project.name inferred from repository catalog")

    providers = migrated.get("providers") or {}
    if not project.get("default_provider") and isinstance(providers, dict) and providers:
        project["default_provider"] = next((name for name in providers if name != "local"), next(iter(providers)))
        changes.append(f"project.default_provider inferred as {project['default_provider']}")
    if not project.get("default_branch"):
        project["default_branch"] = "main"
        changes.append("project.default_branch added as main")


def _migrate_provider_aliases(migrated: dict[str, Any], changes: list[str]) -> None:
    providers = migrated.setdefault("providers", {})
    if not isinstance(providers, dict):
        return
    for name, raw_provider in list(providers.items()):
        if isinstance(raw_provider, str):
            provider: dict[str, Any] = {"url_template": raw_provider}
            providers[name] = provider
            changes.append(f"providers.{name}: string converted to provider object")
        elif isinstance(raw_provider, dict):
            provider = raw_provider
        else:
            continue

        old_type = str(provider.get("type") or "").strip().lower()
        old_kind = str(provider.get("kind") or "").strip().lower()
        inferred_driver = str(provider.get("driver") or "").strip().lower()
        if not inferred_driver and old_type in {"github", "gitlab", "generic", "local"}:
            inferred_driver = old_type
        if not inferred_driver and old_kind in {"github", "gitlab", "generic", "local"}:
            inferred_driver = old_kind
        cli = str(provider.get("cli") or "").strip().lower()
        host = str(provider.get("host") or "").strip().lower()
        if not inferred_driver:
            if name == "local" or old_type == "local":
                inferred_driver = "local"
            elif cli == "gh" or name == "github" or "github" in host:
                inferred_driver = "github"
            elif cli == "glab" or name == "gitlab" or "gitlab" in host:
                inferred_driver = "gitlab"
            else:
                inferred_driver = "generic"

        desired_type = "local" if inferred_driver == "local" or name == "local" else "remote"
        if provider.get("type") != desired_type:
            provider["type"] = desired_type
            changes.append(f"providers.{name}.type normalized to {desired_type}")
        if provider.get("driver") != inferred_driver:
            provider["driver"] = inferred_driver
            changes.append(f"providers.{name}.driver normalized to {inferred_driver}")

        if "namespace" not in provider:
            alias, value = _pop_alias(provider, ("owner", "group"))
            if alias is not None:
                provider["namespace"] = value
                changes.append(f"providers.{name}.{alias} renamed to namespace")

        if not provider.get("host") and inferred_driver in {"github", "gitlab"}:
            provider["host"] = "github.com" if inferred_driver == "github" else "gitlab.com"
            changes.append(f"providers.{name}.host added")
        if not provider.get("cli"):
            provider["cli"] = {"github": "gh", "gitlab": "glab", "local": "git"}.get(inferred_driver, "git")
            changes.append(f"providers.{name}.cli added")
        if not provider.get("url_template"):
            if desired_type == "local":
                provider["url_template"] = "file://{root}/{namespace}/{repo}.git"
            elif inferred_driver in {"github", "gitlab"}:
                provider["url_template"] = "git@{host}:{namespace}/{repo}.git"
            changes.append(f"providers.{name}.url_template added")
        if "required_scopes" not in provider:
            provider["required_scopes"] = []
            changes.append(f"providers.{name}.required_scopes added")


def migrate_config_data(data: dict[str, Any], target: str = CURRENT_SCHEMA_VERSION) -> tuple[dict[str, Any], list[str]]:
    if target != CURRENT_SCHEMA_VERSION:
        raise ValueError(f"unsupported target schema version: {target}")
    migrated = copy.deepcopy(data)
    changes: list[str] = []
    raw_version = str(migrated.get("schema_version") or LEGACY_SCHEMA_VERSION)
    version = SOURCE_SCHEMA_ALIASES.get(raw_version)
    if version is None:
        raise ValueError(f"unsupported source schema version: {raw_version}")

    _migrate_repository_aliases(migrated, changes)
    _migrate_provider_aliases(migrated, changes)
    _migrate_project_aliases(migrated, changes)

    if migrated.get("schema_version") != CURRENT_SCHEMA_VERSION:
        migrated["schema_version"] = CURRENT_SCHEMA_VERSION
        changes.append(f"schema_version: {raw_version} -> {CURRENT_SCHEMA_VERSION}")

    local = migrated.setdefault("local", {})
    if "operations_dir" not in local:
        local["operations_dir"] = ".repo-fleet/operations"
        changes.append("local.operations_dir added")
    if "lock_file" not in local:
        local["lock_file"] = ".repo-fleet/lock"
        changes.append("local.lock_file added")
    if "default_jobs" not in local:
        local["default_jobs"] = 1
        changes.append("local.default_jobs added")

    for index, repo in enumerate(migrated.get("repositories") or []):
        if "depends_on" not in repo:
            repo["depends_on"] = []
            changes.append(f"repositories[{index}].depends_on added")
        if "source_type" not in repo:
            if any(repo.get(key) for key in ("upstream_url", "source_url", "mirror_source", "fork_from", "clone_url")):
                value = "upstream"
            elif any(repo.get(key) for key in ("existing_path", "local_source", "import_from")):
                value = "existing"
            else:
                value = "new"
            repo["source_type"] = value
            changes.append(f"repositories[{index}].source_type inferred as {value}")
        if "remote_mode" not in repo:
            if repo.get("fork_from"):
                value = "fork"
            elif repo.get("mirror") is True or repo.get("mirror_source"):
                value = "mirror"
            else:
                value = "create"
            repo["remote_mode"] = value
            changes.append(f"repositories[{index}].remote_mode inferred as {value}")

    validate_or_raise(migrated)
    return migrated, changes

def load_and_migrate(path: Path) -> tuple[dict[str, Any], list[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return migrate_config_data(raw)


def write_migrated_config(path: Path, data: dict[str, Any], backup: bool = True) -> Path | None:
    backup_path: Path | None = None
    if backup and path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        counter = 1
        while backup_path.exists():
            backup_path = path.with_suffix(path.suffix + f".bak.{counter}")
            counter += 1
        backup_path.write_bytes(path.read_bytes())
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return backup_path
