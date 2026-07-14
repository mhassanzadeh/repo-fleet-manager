from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

from .config import ProjectConfig, Repository
from .observability import current_session
from .safety import repository_path, repository_safety_state
from .shell import RunResult, command_exists, run
from .supply_chain import load_manifest, manifest_path

POLICY_SCHEMA_VERSION = "1.0.0"
SEVERITIES = ("info", "warning", "error")
SEVERITY_RANK = {name: index for index, name in enumerate(SEVERITIES)}
BUILTIN_RULE_TYPES = (
    "repository.visibility",
    "repository.branch",
    "repository.provider",
    "repository.remote-host",
    "repository.clean",
    "repository.signed-head",
    "supply-chain.registry",
    "supply-chain.requirements",
    "operation.guard",
)


class PolicyError(RuntimeError):
    """Raised when a policy definition or policy evaluation is invalid."""


class PolicyEnforcementError(PolicyError):
    def __init__(self, report: "PolicyReport"):
        self.report = report
        lines = [f"policy enforcement failed: {report.blocking_count} blocking violation(s)"]
        for item in report.violations:
            if item.blocking:
                lines.append(f" - {item.rule_id} [{item.severity}] {item.subject}: {item.message}")
        super().__init__("\n".join(lines))


@dataclass(slots=True)
class PolicyException:
    id: str
    rule_id: str
    reason: str
    approved_by: str
    expires_at: str
    repositories: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    ticket: str | None = None

    @property
    def expires_datetime(self) -> datetime:
        value = self.expires_at.strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @property
    def active(self) -> bool:
        return self.expires_datetime > datetime.now(timezone.utc)

    def matches(self, rule_id: str, *, repository: str | None = None, action: str | None = None) -> bool:
        if self.rule_id not in {rule_id, "*"}:
            return False
        if repository and self.repositories:
            if not any(fnmatch.fnmatch(repository, pattern) for pattern in self.repositories):
                return False
        if action and self.actions:
            if not any(fnmatch.fnmatch(action, pattern) for pattern in self.actions):
                return False
        return True


@dataclass(slots=True)
class PolicyViolation:
    rule_id: str
    rule_type: str
    severity: str
    subject: str
    message: str
    remediation: str | None = None
    repository: str | None = None
    action: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    exception_id: str | None = None
    exception_reason: str | None = None
    blocking: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PolicyReport:
    project: str
    mode: str
    fail_on: str
    generated_at: str
    violations: list[PolicyViolation]
    applied_exceptions: list[dict[str, Any]] = field(default_factory=list)
    expired_exceptions: list[dict[str, Any]] = field(default_factory=list)
    evaluated_rules: int = 0
    operation: str | None = None

    @property
    def blocking_count(self) -> int:
        return sum(1 for item in self.violations if item.blocking)

    @property
    def noncompliant_count(self) -> int:
        return sum(
            1 for item in self.violations
            if item.exception_id is None and SEVERITY_RANK[item.severity] >= SEVERITY_RANK[self.fail_on]
        )

    @property
    def ok(self) -> bool:
        return self.noncompliant_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": POLICY_SCHEMA_VERSION,
            "project": self.project,
            "mode": self.mode,
            "fail_on": self.fail_on,
            "generated_at": self.generated_at,
            "operation": self.operation,
            "ok": self.ok,
            "blocking_count": self.blocking_count,
            "noncompliant_count": self.noncompliant_count,
            "violation_count": len(self.violations),
            "evaluated_rules": self.evaluated_rules,
            "violations": [item.to_dict() for item in self.violations],
            "applied_exceptions": self.applied_exceptions,
            "expired_exceptions": self.expired_exceptions,
        }


RULE_HELP: dict[str, dict[str, str]] = {
    "repository.visibility": {
        "description": "Require repository visibility to match an allowed set.",
        "remediation": "Set repository.visibility or the project default visibility to an allowed value.",
    },
    "repository.branch": {
        "description": "Restrict configured and active branches.",
        "remediation": "Switch to an allowed branch or update the configured branch after review.",
    },
    "repository.provider": {
        "description": "Restrict repositories to approved provider profiles.",
        "remediation": "Select an approved provider in the repository entry.",
    },
    "repository.remote-host": {
        "description": "Restrict Git remote URLs to approved hosts.",
        "remediation": "Replace the remote URL with an approved host or add an explicit exception.",
    },
    "repository.clean": {
        "description": "Require clean repository worktrees.",
        "remediation": "Commit or stash local changes before continuing.",
    },
    "repository.signed-head": {
        "description": "Require the current HEAD commit to have an acceptable Git signature status.",
        "remediation": "Sign the commit with an approved key and create a new signed commit.",
    },
    "supply-chain.registry": {
        "description": "Restrict container images to approved registries.",
        "remediation": "Use an image from an approved registry or document an expiring exception.",
    },
    "supply-chain.requirements": {
        "description": "Require immutable provenance, SBOM, scan, signature, or attestation controls.",
        "remediation": "Run the supply-chain workflow and satisfy the configured trust requirements.",
    },
    "operation.guard": {
        "description": "Block or require justification for selected mutation operations.",
        "remediation": "Use an allowed operation, provide --reason, or create an approved expiring exception.",
    },
}


def policy_report_schema_path() -> Path:
    return Path(str(files("repo_fleet_manager").joinpath("data/rfm-policy-report.schema.json")))


def load_policy_report_schema() -> dict[str, Any]:
    return json.loads(policy_report_schema_path().read_text(encoding="utf-8"))


def validate_policy_report(payload: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(load_policy_report_schema())
    return [f"{error.json_path}: {error.message}" for error in sorted(validator.iter_errors(payload), key=lambda item: (list(item.absolute_path), item.message))]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _policy_config(config: ProjectConfig) -> dict[str, Any]:
    return config.policy or {}


def policy_enabled(config: ProjectConfig) -> bool:
    raw = _policy_config(config)
    return bool(raw.get("enabled", bool(raw.get("rules") or raw.get("rego"))))


def _rule_rows(config: ProjectConfig) -> list[dict[str, Any]]:
    raw = _policy_config(config).get("rules") or []
    if not isinstance(raw, list):
        raise PolicyError("policy.rules must be an array")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise PolicyError(f"policy.rules[{index}] must be an object")
        rule_id = str(item.get("id") or "").strip()
        rule_type = str(item.get("type") or "").strip()
        if not rule_id:
            raise PolicyError(f"policy.rules[{index}].id is required")
        if rule_id in seen:
            raise PolicyError(f"duplicate policy rule id: {rule_id}")
        if rule_type not in BUILTIN_RULE_TYPES:
            raise PolicyError(f"unsupported built-in policy rule type: {rule_type}")
        seen.add(rule_id)
        rows.append(item)
    return rows


def _exception_rows(config: ProjectConfig) -> list[PolicyException]:
    raw = _policy_config(config).get("exceptions") or []
    if not isinstance(raw, list):
        raise PolicyError("policy.exceptions must be an array")
    rows: list[PolicyException] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise PolicyError(f"policy.exceptions[{index}] must be an object")
        try:
            row = PolicyException(
                id=str(item["id"]),
                rule_id=str(item["rule_id"]),
                reason=str(item["reason"]),
                approved_by=str(item["approved_by"]),
                expires_at=str(item["expires_at"]),
                repositories=tuple(str(value) for value in (item.get("repositories") or [])),
                actions=tuple(str(value) for value in (item.get("actions") or [])),
                ticket=str(item["ticket"]) if item.get("ticket") else None,
            )
            row.expires_datetime
        except (KeyError, TypeError, ValueError) as exc:
            raise PolicyError(f"invalid policy exception at index {index}: {exc}") from exc
        rows.append(row)
    return rows


def _repo_matches(repo: Repository, selectors: dict[str, Any]) -> bool:
    repositories = [str(item) for item in (selectors.get("repositories") or [])]
    tags = {str(item) for item in (selectors.get("tags") or [])}
    kinds = {str(item) for item in (selectors.get("kinds") or [])}
    providers = {str(item) for item in (selectors.get("providers") or [])}
    if repositories and not any(fnmatch.fnmatch(repo.repo, item) or fnmatch.fnmatch(repo.path, item) for item in repositories):
        return False
    if tags and not tags.intersection(repo.tags):
        return False
    if kinds and repo.kind not in kinds:
        return False
    if providers and str(repo.provider or "") not in providers:
        return False
    return True


def _selected_repositories(config: ProjectConfig, rule: dict[str, Any]) -> list[Repository]:
    selectors = rule.get("selectors") or {}
    if not isinstance(selectors, dict):
        raise PolicyError(f"policy rule {rule.get('id')} selectors must be an object")
    return [repo for repo in config.repositories if _repo_matches(repo, selectors)]


def _severity(rule: dict[str, Any]) -> str:
    value = str(rule.get("severity") or "error").lower()
    if value not in SEVERITIES:
        raise PolicyError(f"policy rule {rule.get('id')} has invalid severity: {value}")
    return value


def _violation(rule: dict[str, Any], subject: str, message: str, *, repository: str | None = None, action: str | None = None, data: dict[str, Any] | None = None) -> PolicyViolation:
    rule_type = str(rule.get("type"))
    remediation = str(rule.get("remediation") or RULE_HELP.get(rule_type, {}).get("remediation") or "") or None
    return PolicyViolation(
        rule_id=str(rule.get("id")),
        rule_type=rule_type,
        severity=_severity(rule),
        subject=subject,
        message=message,
        remediation=remediation,
        repository=repository,
        action=action,
        data=data or {},
    )


def _remote_hosts(path: Path, runner: Callable[..., RunResult]) -> list[str]:
    result = runner(["git", "config", "--get-regexp", r"^remote\..*\.url$"], cwd=path)
    if result.code != 0:
        return []
    hosts: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        url = parts[1].strip()
        host = ""
        if "://" in url:
            host = urlparse(url).hostname or ""
        else:
            match = re.match(r"(?:[^@]+@)?([^:]+):", url)
            host = match.group(1) if match else "local"
        if host and host not in hosts:
            hosts.append(host.lower())
    return hosts


def _registry(reference: str) -> str:
    value = reference.split("@", 1)[0]
    first = value.split("/", 1)[0]
    if "." in first or ":" in first or first == "localhost":
        return first.lower()
    return "docker.io"


def _manifest_service_map(config: ProjectConfig, root: Path) -> dict[str, dict[str, Any]]:
    path = manifest_path(config, root)
    if not path.exists():
        return {}
    try:
        payload = load_manifest(config, root)
    except Exception:  # noqa: BLE001
        return {}
    return {str(item.get("service")): item for item in (payload.get("services") or []) if isinstance(item, dict)}


def _configured_images(config: ProjectConfig) -> dict[str, str]:
    result: dict[str, str] = {}
    supply_services = (config.supply_chain or {}).get("services") or {}
    if isinstance(supply_services, dict):
        for name, item in supply_services.items():
            if isinstance(item, dict) and item.get("image"):
                result[str(name)] = str(item["image"])
    for repo in config.services():
        image = repo.extra.get("image")
        if image:
            result.setdefault(repo.service_name, str(image))
    return result


def _evaluate_rule(rule: dict[str, Any], config: ProjectConfig, root: Path, *, operation: str | None, reason: str | None, force: bool, runner: Callable[..., RunResult]) -> list[PolicyViolation]:
    if not bool(rule.get("enabled", True)):
        return []
    params = rule.get("parameters") or {}
    if not isinstance(params, dict):
        raise PolicyError(f"policy rule {rule.get('id')} parameters must be an object")
    rule_type = str(rule.get("type"))
    violations: list[PolicyViolation] = []

    if rule_type == "repository.visibility":
        allowed = {str(item) for item in (params.get("allowed") or ["private"])}
        default = str(config.project.get("visibility") or config.project.get("default_visibility") or "unspecified")
        for repo in _selected_repositories(config, rule):
            value = str(repo.visibility or default)
            if value not in allowed:
                violations.append(_violation(rule, repo.repo, f"visibility {value!r} is not allowed; expected one of {sorted(allowed)}", repository=repo.repo, data={"actual": value, "allowed": sorted(allowed)}))

    elif rule_type == "repository.branch":
        allowed = [str(item) for item in (params.get("allowed") or [])]
        forbidden = [str(item) for item in (params.get("forbidden") or [])]
        require_config_match = bool(params.get("require_config_match", False))
        for repo in _selected_repositories(config, rule):
            state = repository_safety_state(repo, root)
            actual = state.branch or repo.branch
            if allowed and not any(fnmatch.fnmatch(actual, pattern) for pattern in allowed):
                violations.append(_violation(rule, repo.repo, f"branch {actual!r} is not in the allowed set", repository=repo.repo, data={"actual": actual, "allowed": allowed}))
            if forbidden and any(fnmatch.fnmatch(actual, pattern) for pattern in forbidden):
                violations.append(_violation(rule, repo.repo, f"branch {actual!r} matches a forbidden pattern", repository=repo.repo, data={"actual": actual, "forbidden": forbidden}))
            if require_config_match and state.worktree and state.branch_mismatch:
                violations.append(_violation(rule, repo.repo, f"active branch {state.branch!r} does not match configured branch {repo.branch!r}", repository=repo.repo))

    elif rule_type == "repository.provider":
        allowed = {str(item) for item in (params.get("allowed") or [])}
        for repo in _selected_repositories(config, rule):
            provider = str(repo.provider or config.default_provider_name)
            if allowed and provider not in allowed:
                violations.append(_violation(rule, repo.repo, f"provider {provider!r} is not approved", repository=repo.repo, data={"actual": provider, "allowed": sorted(allowed)}))

    elif rule_type == "repository.remote-host":
        allowed = [str(item).lower() for item in (params.get("allowed_hosts") or [])]
        require_remote = bool(params.get("require_remote", True))
        for repo in _selected_repositories(config, rule):
            path = repository_path(repo, root)
            hosts = _remote_hosts(path, runner) if path.exists() else []
            if require_remote and not hosts:
                violations.append(_violation(rule, repo.repo, "no Git remote URL was found", repository=repo.repo))
                continue
            rejected = [host for host in hosts if allowed and not any(fnmatch.fnmatch(host, pattern) for pattern in allowed)]
            if rejected:
                violations.append(_violation(rule, repo.repo, f"remote host(s) are not approved: {', '.join(rejected)}", repository=repo.repo, data={"hosts": hosts, "allowed_hosts": allowed}))

    elif rule_type == "repository.clean":
        for repo in _selected_repositories(config, rule):
            state = repository_safety_state(repo, root)
            if state.worktree and state.dirty:
                violations.append(_violation(rule, repo.repo, "worktree contains uncommitted changes", repository=repo.repo, data={"path": state.path}))

    elif rule_type == "repository.signed-head":
        accepted = {str(item) for item in (params.get("accepted_statuses") or ["G", "U"])}
        require_worktree = bool(params.get("require_worktree", True))
        for repo in _selected_repositories(config, rule):
            path = repository_path(repo, root)
            if not path.exists() or runner(["git", "rev-parse", "--is-inside-work-tree"], cwd=path).code != 0:
                if require_worktree:
                    violations.append(_violation(rule, repo.repo, "repository worktree is unavailable for signature verification", repository=repo.repo))
                continue
            result = runner(["git", "log", "-1", "--format=%G?"], cwd=path)
            status = result.stdout.strip() if result.code == 0 else "N"
            if status not in accepted:
                violations.append(_violation(rule, repo.repo, f"HEAD signature status {status!r} is not accepted", repository=repo.repo, data={"status": status, "accepted": sorted(accepted)}))

    elif rule_type == "supply-chain.registry":
        allowed = [str(item).lower() for item in (params.get("allowed_registries") or [])]
        manifest = _manifest_service_map(config, root)
        images = _configured_images(config)
        for service, item in manifest.items():
            value = item.get("resolved_reference") or item.get("image")
            if value:
                images[service] = str(value)
        for service, image in sorted(images.items()):
            registry = _registry(image)
            if allowed and not any(fnmatch.fnmatch(registry, pattern) for pattern in allowed):
                violations.append(_violation(rule, service, f"registry {registry!r} is not approved", repository=service, data={"image": image, "registry": registry, "allowed_registries": allowed}))

    elif rule_type == "supply-chain.requirements":
        cfg = config.supply_chain or {}
        manifest = _manifest_service_map(config, root)
        requirements = {
            "require_immutable_digest": bool(params.get("require_immutable_digest", False)),
            "require_source_label": bool(params.get("require_source_label", False)),
            "require_sbom": bool(params.get("require_sbom", False)),
            "require_scan": bool(params.get("require_scan", False)),
            "require_signature": bool(params.get("require_signature", False)),
            "require_attestation": bool(params.get("require_attestation", False)),
        }
        for key, required in requirements.items():
            if required and not bool(cfg.get(key, False)):
                violations.append(_violation(rule, "supply_chain", f"configuration does not enable {key}", data={"requirement": key}))
        if bool(params.get("require_manifest", True)) and not manifest:
            violations.append(_violation(rule, "supply_chain", "provenance manifest is missing or invalid", data={"manifest": str(manifest_path(config, root))}))
        for service, item in manifest.items():
            if requirements["require_immutable_digest"] and not bool(item.get("immutable") and item.get("digest")):
                violations.append(_violation(rule, service, "immutable image digest is missing", repository=service))
            if requirements["require_source_label"] and not bool(item.get("source_match")):
                violations.append(_violation(rule, service, "source provenance does not match", repository=service))
            if requirements["require_sbom"] and not isinstance(item.get("sbom"), dict):
                violations.append(_violation(rule, service, "SBOM metadata is missing", repository=service))
            if requirements["require_scan"] and not bool((item.get("scan") or {}).get("passed")):
                violations.append(_violation(rule, service, "vulnerability scan is missing or failed", repository=service))

    elif rule_type == "operation.guard":
        if not operation:
            return []
        actions = [str(item) for item in (params.get("actions") or ["*"])]
        if not any(fnmatch.fnmatch(operation, pattern) for pattern in actions):
            return []
        denied = bool(params.get("deny", False))
        require_reason = bool(params.get("require_reason", True))
        require_force = bool(params.get("require_force", False))
        if denied:
            violations.append(_violation(rule, operation, f"operation {operation!r} is denied by policy", action=operation))
        if require_reason and not (reason and reason.strip()):
            violations.append(_violation(rule, operation, f"operation {operation!r} requires an explicit --reason", action=operation))
        if require_force and not force:
            violations.append(_violation(rule, operation, f"operation {operation!r} requires --force and --reason", action=operation))

    return violations


def _opa_violations(config: ProjectConfig, root: Path, facts: dict[str, Any], runner: Callable[..., RunResult]) -> list[PolicyViolation]:
    rego = (_policy_config(config).get("rego") or {})
    if not isinstance(rego, dict) or not bool(rego.get("enabled", False)):
        return []
    executable = str(rego.get("executable") or "opa")
    if not command_exists(executable):
        raise PolicyError(f"OPA/Rego policy is enabled but {executable!r} is not installed")
    policy_path = Path(str(rego.get("policy_path") or "policy"))
    if not policy_path.is_absolute():
        policy_path = (root / policy_path).resolve()
    if not policy_path.exists():
        raise PolicyError(f"OPA/Rego policy path does not exist: {policy_path}")
    query = str(rego.get("query") or "data.rfm.deny")
    command = [executable, "eval", "--format", "json", "--data", str(policy_path), "--stdin-input", query]
    result = runner(command, cwd=root, input_text=json.dumps(facts)) if _runner_accepts_input(runner) else _opa_run(command, root, facts)
    if result.code != 0:
        raise PolicyError(result.stderr or result.stdout or "OPA evaluation failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PolicyError(f"OPA returned invalid JSON: {exc}") from exc
    values: list[Any] = []
    for row in payload.get("result") or []:
        for expression in row.get("expressions") or []:
            value = expression.get("value")
            if isinstance(value, list):
                values.extend(value)
            elif value not in (None, False):
                values.append(value)
    violations: list[PolicyViolation] = []
    for index, value in enumerate(values, start=1):
        if isinstance(value, str):
            item = {"message": value}
        elif isinstance(value, dict):
            item = value
        else:
            item = {"message": json.dumps(value, ensure_ascii=False)}
        severity = str(item.get("severity") or "error").lower()
        if severity not in SEVERITIES:
            severity = "error"
        violations.append(PolicyViolation(
            rule_id=str(item.get("rule_id") or item.get("id") or f"rego-{index}"),
            rule_type="rego",
            severity=severity,
            subject=str(item.get("subject") or item.get("repository") or item.get("action") or "rego"),
            message=str(item.get("message") or "Rego policy denied the input"),
            remediation=str(item.get("remediation")) if item.get("remediation") else None,
            repository=str(item.get("repository")) if item.get("repository") else None,
            action=str(item.get("action")) if item.get("action") else None,
            data={key: value for key, value in item.items() if key not in {"rule_id", "id", "severity", "subject", "message", "remediation", "repository", "action"}},
        ))
    return violations


def _runner_accepts_input(runner: Callable[..., RunResult]) -> bool:
    return False


def _opa_run(command: list[str], root: Path, facts: dict[str, Any]) -> RunResult:
    import subprocess
    proc = subprocess.run(command, cwd=str(root), input=json.dumps(facts), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return RunResult(proc.returncode, proc.stdout.strip(), proc.stderr.strip())


def policy_input(config: ProjectConfig, root: Path, *, operation: str | None = None, reason: str | None = None, force: bool = False, runner: Callable[..., RunResult] = run) -> dict[str, Any]:
    repositories: list[dict[str, Any]] = []
    for repo in config.repositories:
        state = repository_safety_state(repo, root)
        path = repository_path(repo, root)
        repositories.append({
            "repo": repo.repo,
            "path": repo.path,
            "kind": repo.kind,
            "provider": repo.provider or config.default_provider_name,
            "visibility": repo.visibility or config.project.get("visibility") or config.project.get("default_visibility"),
            "configured_branch": repo.branch,
            "active_branch": state.branch,
            "dirty": state.dirty,
            "detached": state.detached,
            "remote_hosts": _remote_hosts(path, runner) if path.exists() else [],
            "tags": list(repo.tags),
        })
    manifest = _manifest_service_map(config, root)
    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "project": config.project,
        "repositories": repositories,
        "supply_chain": {"config": config.supply_chain, "services": list(manifest.values())},
        "operation": {"name": operation, "reason": reason, "force": force} if operation else None,
    }


def evaluate_policy(
    config: ProjectConfig,
    root: Path,
    *,
    mode: str | None = None,
    fail_on: str | None = None,
    selected_rules: Iterable[str] | None = None,
    selected_repositories: Iterable[str] | None = None,
    operation: str | None = None,
    reason: str | None = None,
    force: bool = False,
    runner: Callable[..., RunResult] = run,
) -> PolicyReport:
    cfg = _policy_config(config)
    active_mode = str(mode or cfg.get("mode") or "check").lower()
    if active_mode not in {"check", "enforce"}:
        raise PolicyError(f"invalid policy mode: {active_mode}")
    threshold = str(fail_on or cfg.get("fail_on") or "error").lower()
    if threshold not in SEVERITIES:
        raise PolicyError(f"invalid policy fail_on severity: {threshold}")
    requested_rules = {str(item) for item in selected_rules or []}
    requested_repos = {str(item) for item in selected_repositories or []}
    rules = [rule for rule in _rule_rows(config) if not requested_rules or str(rule.get("id")) in requested_rules]
    if requested_rules:
        unknown = requested_rules - {str(rule.get("id")) for rule in rules}
        if unknown:
            raise PolicyError("unknown policy rule(s): " + ", ".join(sorted(unknown)))
    violations: list[PolicyViolation] = []
    for rule in rules:
        rows = _evaluate_rule(rule, config, root, operation=operation, reason=reason, force=force, runner=runner)
        if requested_repos:
            rows = [item for item in rows if item.repository in requested_repos or item.subject in requested_repos]
        violations.extend(rows)
    facts = policy_input(config, root, operation=operation, reason=reason, force=force, runner=runner)
    rego_rows = _opa_violations(config, root, facts, runner)
    if requested_repos:
        rego_rows = [item for item in rego_rows if item.repository in requested_repos or item.subject in requested_repos]
    violations.extend(rego_rows)

    exceptions = _exception_rows(config)
    applied: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    for exception in exceptions:
        payload = {
            "id": exception.id,
            "rule_id": exception.rule_id,
            "reason": exception.reason,
            "approved_by": exception.approved_by,
            "expires_at": exception.expires_at,
            "ticket": exception.ticket,
            "repositories": list(exception.repositories),
            "actions": list(exception.actions),
        }
        if not exception.active:
            expired.append(payload)
            continue
        matched = False
        for item in violations:
            if item.exception_id:
                continue
            if exception.matches(item.rule_id, repository=item.repository, action=item.action):
                item.exception_id = exception.id
                item.exception_reason = exception.reason
                matched = True
        if matched:
            applied.append(payload)

    for item in violations:
        item.blocking = (
            item.exception_id is None
            and active_mode == "enforce"
            and SEVERITY_RANK[item.severity] >= SEVERITY_RANK[threshold]
        )
    report = PolicyReport(
        project=str(config.project.get("name") or root.name),
        mode=active_mode,
        fail_on=threshold,
        generated_at=_utc_now(),
        operation=operation,
        violations=violations,
        applied_exceptions=applied,
        expired_exceptions=expired,
        evaluated_rules=len(rules) + (1 if (_policy_config(config).get("rego") or {}).get("enabled") else 0),
    )
    session = current_session()
    if session is not None:
        session.emit(
            "policy.evaluated",
            level="error" if report.blocking_count else "info",
            status="failed" if report.blocking_count else "succeeded",
            data=report.to_dict(),
        )
    return report


def enforce_operation_policy(config: ProjectConfig, root: Path, operation: str, *, reason: str | None, force: bool, runner: Callable[..., RunResult] = run) -> PolicyReport | None:
    if not policy_enabled(config):
        return None
    mode = str(_policy_config(config).get("mode") or "check").lower()
    if mode != "enforce":
        return evaluate_policy(config, root, mode="check", operation=operation, reason=reason, force=force, runner=runner)
    report = evaluate_policy(config, root, mode="enforce", operation=operation, reason=reason, force=force, runner=runner)
    if report.blocking_count:
        raise PolicyEnforcementError(report)
    return report


def explain_rule(config: ProjectConfig, rule_id: str) -> dict[str, Any]:
    for rule in _rule_rows(config):
        if str(rule.get("id")) == rule_id:
            rule_type = str(rule.get("type"))
            exceptions = [
                {
                    "id": item.id,
                    "reason": item.reason,
                    "approved_by": item.approved_by,
                    "expires_at": item.expires_at,
                    "active": item.active,
                    "repositories": list(item.repositories),
                    "actions": list(item.actions),
                    "ticket": item.ticket,
                }
                for item in _exception_rows(config)
                if item.rule_id in {rule_id, "*"}
            ]
            return {
                "schema_version": POLICY_SCHEMA_VERSION,
                "rule": rule,
                "description": str(rule.get("description") or RULE_HELP.get(rule_type, {}).get("description") or ""),
                "default_remediation": RULE_HELP.get(rule_type, {}).get("remediation"),
                "exceptions": exceptions,
            }
    raise PolicyError(f"unknown policy rule: {rule_id}")


def list_policy_exceptions(config: ProjectConfig) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "rule_id": item.rule_id,
            "reason": item.reason,
            "approved_by": item.approved_by,
            "expires_at": item.expires_at,
            "active": item.active,
            "repositories": list(item.repositories),
            "actions": list(item.actions),
            "ticket": item.ticket,
        }
        for item in _exception_rows(config)
    ]


def print_policy_report(report: PolicyReport, *, json_output: bool = False) -> int:
    if json_output:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if report.ok else 2
    marker = "PASS" if report.ok else "FAIL"
    print(f"Policy: {marker} mode={report.mode} fail_on={report.fail_on} rules={report.evaluated_rules} violations={len(report.violations)} noncompliant={report.noncompliant_count} blocking={report.blocking_count}")
    for item in report.violations:
        if item.exception_id:
            status = "EXCEPTED"
        elif item.blocking:
            status = "BLOCK"
        else:
            status = item.severity.upper()
        print(f" - [{status:<9}] {item.rule_id} {item.subject}: {item.message}")
        if item.exception_id:
            print(f"     exception={item.exception_id} reason={item.exception_reason}")
        elif item.remediation:
            print(f"     remediation: {item.remediation}")
    for item in report.expired_exceptions:
        print(f" - [EXPIRED  ] exception {item['id']} rule={item['rule_id']} expired={item['expires_at']}")
    return 0 if report.ok else 2
