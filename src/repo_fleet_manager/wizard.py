from __future__ import annotations

import configparser
import copy
import difflib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .schema import CURRENT_SCHEMA_VERSION, validate_or_raise

DEFAULT_SESSION_FILE = ".repo-fleet/wizard/session.json"
DEFAULT_CONFIG_FILE = "repo-fleet.json"
_SECRET_KEY = re.compile(r"(?:token|secret|password|passwd|api[_-]?key|private[_-]?key)", re.IGNORECASE)
_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REPO_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_COMPOSE_NAMES = (
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
)
_SKIP_DIRS = {".git", ".repo-fleet", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}


class WizardError(RuntimeError):
    pass


@dataclass(slots=True)
class ScanResult:
    root: Path
    project_name: str
    default_branch: str
    default_provider: str
    namespace: str
    repositories: list[dict[str, Any]] = field(default_factory=list)
    compose_file: str | None = None
    env_file: str | None = None
    compose_services: list[str] = field(default_factory=list)
    cache_images: list[str] = field(default_factory=list)
    engine: str = "auto"

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "project_name": self.project_name,
            "default_branch": self.default_branch,
            "default_provider": self.default_provider,
            "namespace": self.namespace,
            "repositories": copy.deepcopy(self.repositories),
            "compose_file": self.compose_file,
            "env_file": self.env_file,
            "compose_services": list(self.compose_services),
            "cache_images": list(self.cache_images),
            "engine": self.engine,
        }


@dataclass(slots=True)
class WizardResult:
    config: dict[str, Any]
    output: Path
    session_file: Path
    scan: ScanResult | None
    changed: bool
    backup: Path | None = None
    diff: str = ""


def _run_git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _portable_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    base = root.resolve()
    try:
        relative = resolved.relative_to(base)
    except ValueError as exc:
        raise WizardError(f"path is outside the scanned project: {path}") from exc
    value = relative.as_posix() or "."
    if value.startswith("/") or ".." in Path(value).parts:
        raise WizardError(f"non-portable path detected: {value}")
    return value


def _repo_name(value: str) -> str:
    cleaned = _REPO_NAME.sub("-", value.strip()).strip("-._")
    return cleaned or "repository"


def _provider_from_url(url: str | None) -> tuple[str, str]:
    if not url:
        return "local", ""
    lowered = url.lower()
    provider = "github" if "github" in lowered else "gitlab" if "gitlab" in lowered else "local"
    match = re.search(r"(?:[:/])([^/:]+)/[^/]+?(?:\.git)?$", url)
    return provider, match.group(1) if match else ""


def _read_gitmodules(root: Path) -> list[tuple[str, str, str | None]]:
    path = root / ".gitmodules"
    if not path.exists():
        return []
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error:
        return []
    rows: list[tuple[str, str, str | None]] = []
    for section in parser.sections():
        rel = parser.get(section, "path", fallback="").strip()
        url = parser.get(section, "url", fallback="").strip() or None
        if not rel:
            continue
        name_match = re.match(r'submodule\s+"(.+)"', section)
        name = name_match.group(1) if name_match else Path(rel).name
        rows.append((rel, name, url))
    return rows


def _discover_nested_repositories(root: Path, *, max_depth: int = 4) -> list[Path]:
    found: list[Path] = []
    for current, dirs, _files in os.walk(root):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            continue
        dirs[:] = [name for name in dirs if name not in _SKIP_DIRS and not name.startswith(".")]
        if depth > max_depth:
            dirs[:] = []
            continue
        if current_path != root and (current_path / ".git").exists():
            found.append(current_path)
            dirs[:] = []
    return found


def _find_compose(root: Path) -> Path | None:
    candidates: list[Path] = []
    for name in _COMPOSE_NAMES:
        direct = root / name
        if direct.exists():
            candidates.append(direct)
    for directory in ("infra-compose", "infra", "deploy", "ops"):
        for name in _COMPOSE_NAMES:
            candidate = root / directory / name
            if candidate.exists():
                candidates.append(candidate)
    return candidates[0] if candidates else None


def _parse_compose_hints(path: Path | None) -> tuple[list[str], list[str]]:
    if not path or not path.exists():
        return [], []
    text = path.read_text(encoding="utf-8", errors="replace")
    services: list[str] = []
    images: list[str] = []
    in_services = False
    service_indent = 0
    for line in text.splitlines():
        clean = line.split("#", 1)[0].rstrip()
        if not clean:
            continue
        indent = len(line) - len(line.lstrip())
        if re.match(r"^services\s*:\s*$", clean):
            in_services = True
            service_indent = indent
            continue
        if in_services and indent <= service_indent and not clean.lstrip().startswith(("-", "image:")):
            in_services = False
        if in_services:
            match = re.match(r"^\s{2,}([A-Za-z0-9_.-]+)\s*:\s*$", clean)
            if match and match.group(1) not in {"build", "environment", "ports", "volumes", "depends_on", "healthcheck"}:
                services.append(match.group(1))
        image = re.match(r"^\s*image\s*:\s*['\"]?([^'\"\s]+)", clean)
        if image:
            images.append(image.group(1))
    return list(dict.fromkeys(services)), list(dict.fromkeys(images))


def _find_env_file(root: Path, compose_file: Path | None) -> Path | None:
    bases = [compose_file.parent] if compose_file else []
    bases.append(root)
    for base in bases:
        for name in (".env.example", ".env.sample", ".env"):
            candidate = base / name
            if candidate.exists():
                return candidate
    return None


def scan_project(path: str | Path) -> ScanResult:
    root = Path(path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise WizardError(f"scan path is not a directory: {root}")

    project_name = _repo_name(root.name)
    branch = _run_git(root, "branch", "--show-current") or "main"
    remote = _run_git(root, "remote", "get-url", "origin")
    provider, namespace = _provider_from_url(remote)
    repositories: list[dict[str, Any]] = []

    if (root / ".git").exists():
        repositories.append({
            "path": ".",
            "repo": project_name,
            "kind": "root",
            "provider": provider,
            "branch": branch,
            "source_type": "existing",
            "depends_on": [],
            "tags": ["root", "orchestration"],
        })

    known_paths = {row[0] for row in _read_gitmodules(root)}
    for rel, name, url in _read_gitmodules(root):
        repo_root = root / rel
        repo_provider, _ = _provider_from_url(url)
        repo_branch = _run_git(repo_root, "branch", "--show-current") or branch
        entry: dict[str, Any] = {
            "path": Path(rel).as_posix(),
            "repo": _repo_name(name),
            "kind": "module",
            "provider": repo_provider if repo_provider != "local" else provider,
            "branch": repo_branch,
            "source_type": "existing",
            "existing_path": Path(rel).as_posix(),
            "depends_on": [],
            "tags": ["module"],
        }
        if (repo_root / "Dockerfile").exists():
            entry.update({"kind": "service", "docker_context": Path(rel).as_posix(), "dockerfile": f"{Path(rel).as_posix()}/Dockerfile"})
            entry["tags"] = ["service", "runtime"]
        repositories.append(entry)

    for repo_root in _discover_nested_repositories(root):
        rel = _portable_path(repo_root, root)
        if rel in known_paths:
            continue
        repo_provider, _ = _provider_from_url(_run_git(repo_root, "remote", "get-url", "origin"))
        repo_branch = _run_git(repo_root, "branch", "--show-current") or branch
        entry = {
            "path": rel,
            "repo": _repo_name(repo_root.name),
            "kind": "module",
            "provider": repo_provider if repo_provider != "local" else provider,
            "branch": repo_branch,
            "source_type": "existing",
            "existing_path": rel,
            "depends_on": [],
            "tags": ["module"],
        }
        if (repo_root / "Dockerfile").exists():
            entry.update({"kind": "service", "docker_context": rel, "dockerfile": f"{rel}/Dockerfile"})
            entry["tags"] = ["service", "runtime"]
        repositories.append(entry)

    if not repositories:
        repositories.append({
            "path": ".",
            "repo": project_name,
            "kind": "root",
            "provider": "local",
            "branch": branch,
            "source_type": "existing",
            "depends_on": [],
            "tags": ["root", "orchestration"],
        })
        provider = "local"

    compose_file = _find_compose(root)
    services, images = _parse_compose_hints(compose_file)
    env_file = _find_env_file(root, compose_file)
    engine = "podman" if shutil.which("podman") else "docker" if shutil.which("docker") else "auto"
    return ScanResult(
        root=root,
        project_name=project_name,
        default_branch=branch,
        default_provider=provider,
        namespace=namespace,
        repositories=repositories,
        compose_file=_portable_path(compose_file, root) if compose_file else None,
        env_file=_portable_path(env_file, root) if env_file else None,
        compose_services=services,
        cache_images=images,
        engine=engine,
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _reject_secrets(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if _SECRET_KEY.search(str(key)) and item not in (None, "", [], {}):
                raise WizardError(f"secret-like value is not allowed in wizard answers: {child}")
            _reject_secrets(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secrets(item, f"{path}[{index}]")


def load_answers(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser()
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WizardError(f"cannot read wizard answers {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise WizardError("wizard answers must be a JSON object")
    _reject_secrets(data)
    return data


def _provider_config(name: str, namespace: str) -> dict[str, Any]:
    if name == "github":
        return {"type": "remote", "driver": "github", "namespace": namespace, "host": "github.com", "cli": "gh", "url_template": "git@github.com:{namespace}/{repo}.git", "required_scopes": []}
    if name == "gitlab":
        return {"type": "remote", "driver": "gitlab", "namespace": namespace, "host": "gitlab.com", "cli": "glab", "url_template": "git@gitlab.com:{namespace}/{repo}.git", "required_scopes": []}
    return {"type": "local", "driver": "local", "namespace": ".repo-fleet/remotes", "cli": "git", "url_template": "file://{root}/{namespace}/{repo}.git", "required_scopes": []}


def _base_config(scan: ScanResult | None, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if existing:
        return copy.deepcopy(existing)
    project_name = scan.project_name if scan else "my-platform"
    branch = scan.default_branch if scan else "main"
    provider = scan.default_provider if scan else "local"
    namespace = scan.namespace if scan else ""
    repositories = copy.deepcopy(scan.repositories) if scan else [{
        "path": ".", "repo": project_name, "kind": "root", "provider": provider,
        "branch": branch, "source_type": "existing", "depends_on": [], "tags": ["root", "orchestration"],
    }]
    providers = {"local": _provider_config("local", "")}
    if provider != "local":
        providers[provider] = _provider_config(provider, namespace)
    result: dict[str, Any] = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "project": {"name": project_name, "default_provider": provider, "default_branch": branch, "build_dir": ".repo-fleet/build"},
        "providers": providers,
        "repositories": repositories,
        "local": {
            "remotes_dir": ".repo-fleet/remotes", "workspace_mode": "submodules", "operations_dir": ".repo-fleet/operations",
            "lock_file": ".repo-fleet/lock", "default_jobs": 2, "backups_dir": ".repo-fleet/backups",
            "backup_retention": 5, "backup_include_operations": False, "cache_dir": ".repo-fleet/cache", "cache_retention": 3,
        },
        "observability": {"logs_dir": ".repo-fleet/logs", "audit_enabled": True, "retention_days": 30, "include_output": True},
        "fingerprint": {"algorithm": "sha256", "short_length": 16},
    }
    if scan and scan.compose_file:
        result["compose"] = {
            "file": scan.compose_file,
            "project_name": project_name,
            "engine": scan.engine,
            "cache_images": scan.cache_images,
        }
        if scan.env_file:
            result["compose"]["env_file"] = scan.env_file
        if scan.compose_services:
            result["runtime"] = {
                "timeout_seconds": 120,
                "interval_seconds": 2,
                "log_tail": 80,
                "default_running_is_ready": True,
                "services": {name: {"required": True, "depends_on": []} for name in scan.compose_services},
            }
    return result


def _advanced_defaults(config: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(config)
    project = result["project"]
    default = project.get("default_provider", "local")
    result.setdefault("observability", {"logs_dir": ".repo-fleet/logs", "audit_enabled": True, "retention_days": 30, "include_output": True})
    result.setdefault("profiles", {})
    result["profiles"].setdefault("developer", {"project": {"default_provider": "local"}, "local": {"default_jobs": 2}})
    result["profiles"].setdefault("ci", {"extends": "developer", "project": {"default_provider": default}, "local": {"default_jobs": 4}})
    result["profiles"].setdefault("production", {"project": {"default_provider": default}, "local": {"default_jobs": 8}})
    tags = sorted({tag for repo in result.get("repositories", []) for tag in repo.get("tags", [])})
    groups = result.setdefault("groups", {})
    for tag in tags:
        if tag not in {"root", "orchestration", "module"}:
            groups.setdefault(tag, {"tags": [tag], "include_dependencies": True})
    return result


class _PromptSession:
    def __init__(self, path: Path, initial: dict[str, Any] | None = None, input_fn: Callable[[str], str] = input):
        self.path = path
        self.answers = copy.deepcopy(initial or {})
        self.input_fn = input_fn

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"format": 1, "answers": self.answers}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def ask(self, key: str, label: str, default: str = "") -> str:
        if key in self.answers:
            return str(self.answers[key])
        suffix = f" [{default}]" if default else ""
        value = self.input_fn(f"{label}{suffix}: ").strip() or default
        self.answers[key] = value
        self.save()
        return value

    def confirm(self, key: str, label: str, default: bool = True) -> bool:
        if key in self.answers:
            return bool(self.answers[key])
        marker = "Y/n" if default else "y/N"
        value = self.input_fn(f"{label} [{marker}]: ").strip().lower()
        answer = default if not value else value in {"y", "yes", "1", "true"}
        self.answers[key] = answer
        self.save()
        return answer


def load_session(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WizardError(f"cannot resume wizard session {path}: {exc}") from exc
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        raise WizardError(f"invalid wizard session: {path}")
    _reject_secrets(answers)
    return answers


def _interactive_overrides(config: dict[str, Any], scan: ScanResult | None, session: _PromptSession, *, advanced: bool) -> dict[str, Any]:
    project = config.setdefault("project", {})
    project["name"] = _repo_name(session.ask("project_name", "Project name", str(project.get("name", "my-platform"))))
    project["default_branch"] = session.ask("default_branch", "Default branch", str(project.get("default_branch", "main")))
    providers = config.setdefault("providers", {})
    previous_provider = str(project.get("default_provider", "local"))
    allowed_providers = sorted(set(providers) | {"local", "github", "gitlab"})
    provider = session.ask("default_provider", f"Default provider ({'/'.join(allowed_providers)})", previous_provider).lower()
    if provider not in allowed_providers:
        raise WizardError(f"unsupported provider: {provider}; expected one of {', '.join(allowed_providers)}")
    namespace = ""
    provider_driver = str((providers.get(provider) or {}).get("driver", provider))
    if provider != "local":
        current = (providers.get(provider) or {}).get("namespace", scan.namespace if scan else "")
        namespace = session.ask("namespace", f"{provider} namespace", str(current or ""))
    project["default_provider"] = provider
    providers["local"] = _provider_config("local", "")
    if provider in {"github", "gitlab"}:
        providers[provider] = _provider_config(provider, namespace)
    elif provider != "local" and namespace:
        providers[provider]["namespace"] = namespace
    for repo in config.get("repositories", []):
        if repo.get("provider") in {None, previous_provider}:
            repo["provider"] = provider
        repo.setdefault("branch", project["default_branch"])
    engine_default = str((config.get("compose") or {}).get("engine", scan.engine if scan else "auto"))
    engine = session.ask("compose_engine", "Container engine (auto/docker/podman)", engine_default).lower()
    if engine not in {"auto", "docker", "podman"}:
        raise WizardError(f"unsupported container engine: {engine}")
    if config.get("compose") or engine != "auto":
        config.setdefault("compose", {})["engine"] = engine
    if advanced:
        config = _advanced_defaults(config)
        jobs = session.ask("default_jobs", "Default parallel jobs", str(config["local"].get("default_jobs", 2)))
        try:
            config["local"]["default_jobs"] = int(jobs)
        except ValueError as exc:
            raise WizardError("default jobs must be an integer") from exc
        if config.get("compose"):
            runtime = config.setdefault("runtime", {})
            runtime.setdefault("timeout_seconds", 120)
            runtime.setdefault("interval_seconds", 2)
            runtime.setdefault("log_tail", 80)
            runtime.setdefault("default_running_is_ready", True)
            runtime.setdefault("services", {})
            for service in (scan.compose_services if scan else []):
                runtime["services"].setdefault(service, {"required": True, "depends_on": []})
    return config


def _normalize_answers(answers: dict[str, Any]) -> dict[str, Any]:
    if "config" in answers:
        config = answers["config"]
        if not isinstance(config, dict):
            raise WizardError("answers.config must be an object")
        return copy.deepcopy(config)
    allowed_top = {"schema_version", "project", "providers", "repositories", "local", "compose", "runtime", "observability", "fingerprint", "profiles", "groups"}
    if any(key in allowed_top for key in answers):
        return {key: copy.deepcopy(value) for key, value in answers.items() if key in allowed_top}
    return {}


def _validate_portable_paths(config: dict[str, Any]) -> None:
    values: list[tuple[str, Any]] = []
    project = config.get("project") or {}
    values.append(("$.project.build_dir", project.get("build_dir")))
    local = config.get("local") or {}
    for key in ("remotes_dir", "operations_dir", "lock_file", "backups_dir", "cache_dir"):
        values.append((f"$.local.{key}", local.get(key)))
    observability = config.get("observability") or {}
    values.append(("$.observability.logs_dir", observability.get("logs_dir")))
    compose = config.get("compose") or {}
    for key in ("file", "env_file"):
        values.append((f"$.compose.{key}", compose.get(key)))
    for index, repo in enumerate(config.get("repositories") or []):
        for key in ("path", "existing_path", "local_source", "import_from", "docker_context", "dockerfile"):
            values.append((f"$.repositories[{index}].{key}", repo.get(key)))
        for item_index, value in enumerate(repo.get("include_roots") or []):
            values.append((f"$.repositories[{index}].include_roots[{item_index}]", value))
    for path, value in values:
        if value in (None, ""):
            continue
        candidate = Path(str(value)).expanduser()
        if candidate.is_absolute() or ".." in candidate.parts:
            raise WizardError(f"wizard configuration paths must be portable and relative: {path}={value!r}")


def _config_text(config: dict[str, Any]) -> str:
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def _diff(old: str, new: str, path: Path) -> str:
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=f"{path}.before", tofile=str(path)))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def run_wizard(
    *,
    output: str | Path,
    config_path: str | Path | None = None,
    scan_path: str | Path | None = None,
    answers: dict[str, Any] | None = None,
    quick: bool = False,
    advanced: bool = False,
    non_interactive: bool = False,
    resume: bool = False,
    session_file: str | Path = DEFAULT_SESSION_FILE,
    apply: bool = False,
    force: bool = False,
    no_backup: bool = False,
    input_fn: Callable[[str], str] = input,
) -> WizardResult:
    if quick and advanced:
        raise WizardError("--quick and --advanced cannot be used together")
    output_path = Path(output).expanduser().resolve()
    session_path = Path(session_file).expanduser()
    if not session_path.is_absolute():
        session_path = output_path.parent / session_path
    existing_path = Path(config_path).expanduser().resolve() if config_path else (output_path if output_path.exists() else None)
    existing: dict[str, Any] | None = None
    old_text = ""
    if existing_path and existing_path.exists():
        old_text = existing_path.read_text(encoding="utf-8")
        try:
            existing = json.loads(old_text)
        except json.JSONDecodeError as exc:
            raise WizardError(f"existing config is invalid JSON: {existing_path}: {exc}") from exc
        if not isinstance(existing, dict):
            raise WizardError("existing config root must be an object")

    scan = scan_project(scan_path) if scan_path else None
    config = _base_config(scan, existing)
    supplied = copy.deepcopy(answers or {})
    if resume:
        supplied = _deep_merge(load_session(session_path), supplied)
    _reject_secrets(supplied)
    explicit_config = _normalize_answers(supplied)
    if explicit_config:
        config = _deep_merge(config, explicit_config)

    if advanced:
        config = _advanced_defaults(config)
    if not non_interactive:
        session = _PromptSession(session_path, supplied.get("wizard") if isinstance(supplied.get("wizard"), dict) else supplied, input_fn=input_fn)
        try:
            config = _interactive_overrides(config, scan, session, advanced=advanced)
        except (KeyboardInterrupt, EOFError):
            session.save()
            raise WizardError(f"wizard interrupted; resume with --resume (session: {session_path})")
    elif not (answers or scan or existing):
        raise WizardError("non-interactive wizard requires --answers, --scan or an existing --config")

    config["schema_version"] = CURRENT_SCHEMA_VERSION
    _reject_secrets(config)
    _validate_portable_paths(config)
    validate_or_raise(config)
    new_text = _config_text(config)
    changed = new_text != old_text
    diff = _diff(old_text, new_text, output_path) if changed else ""
    backup: Path | None = None
    if apply and changed:
        if output_path.exists() and not force:
            backup = output_path.with_name(output_path.name + ".bak")
            if backup.exists():
                index = 1
                while output_path.with_name(output_path.name + f".bak.{index}").exists():
                    index += 1
                backup = output_path.with_name(output_path.name + f".bak.{index}")
            if not no_backup:
                shutil.copy2(output_path, backup)
            else:
                backup = None
        _atomic_write(output_path, new_text)
        session_path.unlink(missing_ok=True)
    return WizardResult(config=config, output=output_path, session_file=session_path, scan=scan, changed=changed, backup=backup, diff=diff)


def reset_session(path: str | Path, *, root: str | Path = ".") -> Path:
    target = Path(path).expanduser()
    if not target.is_absolute():
        target = Path(root).expanduser().resolve() / target
    target.unlink(missing_ok=True)
    return target


def scan_summary(scan: ScanResult | None) -> dict[str, Any]:
    if scan is None:
        return {}
    return {
        "root": str(scan.root),
        "repositories": len(scan.repositories),
        "compose_file": scan.compose_file,
        "compose_services": scan.compose_services,
        "cache_images": scan.cache_images,
        "engine": scan.engine,
    }
