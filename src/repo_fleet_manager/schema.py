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


def migrate_config_data(data: dict[str, Any], target: str = CURRENT_SCHEMA_VERSION) -> tuple[dict[str, Any], list[str]]:
    if target != CURRENT_SCHEMA_VERSION:
        raise ValueError(f"unsupported target schema version: {target}")
    migrated = copy.deepcopy(data)
    changes: list[str] = []
    version = str(migrated.get("schema_version") or LEGACY_SCHEMA_VERSION)
    if version not in {LEGACY_SCHEMA_VERSION, CURRENT_SCHEMA_VERSION, "0.4.0", "0.3.0"}:
        raise ValueError(f"unsupported source schema version: {version}")

    if migrated.get("schema_version") != CURRENT_SCHEMA_VERSION:
        migrated["schema_version"] = CURRENT_SCHEMA_VERSION
        changes.append(f"schema_version: {version} -> {CURRENT_SCHEMA_VERSION}")

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

    for name, provider in (migrated.get("providers") or {}).items():
        if "type" not in provider:
            provider["type"] = "local" if name == "local" else "remote"
            changes.append(f"providers.{name}.type added")
        if "driver" not in provider:
            cli = str(provider.get("cli") or "")
            host = str(provider.get("host") or "").lower()
            if provider.get("type") == "local" or name == "local":
                driver = "local"
            elif cli == "gh" or name == "github" or host.endswith("github.com"):
                driver = "github"
            elif cli == "glab" or name == "gitlab" or "gitlab" in host:
                driver = "gitlab"
            else:
                driver = "generic"
            provider["driver"] = driver
            changes.append(f"providers.{name}.driver inferred as {driver}")
        if "required_scopes" not in provider:
            provider["required_scopes"] = []
            changes.append(f"providers.{name}.required_scopes added")

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
