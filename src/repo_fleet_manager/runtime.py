from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .compose import compose_cmd, detect_compose_bin
from .config import ProjectConfig, Repository
from .shell import RunResult, run, run_interactive, shlex_join


class RuntimeErrorDetail(RuntimeError):
    """Raised when runtime discovery or readiness cannot be completed safely."""


@dataclass(slots=True)
class ProbeResult:
    probe_type: str
    ok: bool
    detail: str
    latency_ms: int = 0


@dataclass(slots=True)
class RuntimeService:
    name: str
    required: bool = True
    depends_on: tuple[str, ...] = ()
    timeout_seconds: float | None = None
    probe: dict[str, Any] | None = None
    remediation: str | None = None


@dataclass(slots=True)
class ServiceStatus:
    name: str
    required: bool
    depends_on: tuple[str, ...]
    container_id: str | None
    state: str
    running: bool
    ready: bool
    readiness_source: str
    health: str | None = None
    exit_code: int | None = None
    reason: str | None = None
    probe: ProbeResult | None = None
    remediation: str | None = None
    logs: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["depends_on"] = list(self.depends_on)
        return payload


@dataclass(slots=True)
class RuntimeReport:
    ready: bool
    engine: str
    compose_bin: list[str]
    services: list[ServiceStatus]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "engine": self.engine,
            "compose_bin": self.compose_bin,
            "generated_at": self.generated_at,
            "errors": self.errors,
            "services": [item.to_dict() for item in self.services],
        }


def _runtime_config(config: ProjectConfig) -> dict[str, Any]:
    return config.runtime or {}


def _engine_name(config: ProjectConfig, compose_bin: list[str]) -> str:
    configured = str(config.compose.get("engine") or "auto").lower()
    if configured in {"docker", "podman"}:
        return configured
    command = Path(compose_bin[0]).name.lower()
    if "podman" in command:
        return "podman"
    return "docker"


def _parse_json(text: str) -> Any:
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows


def _compose_model(config: ProjectConfig, root: Path, runner: Callable[..., RunResult] = run) -> dict[str, Any]:
    result = runner(compose_cmd(config, root, "config", ["--format", "json"], with_metadata=False), cwd=root)
    if result.code != 0:
        return {}
    try:
        parsed = _parse_json(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _compose_service_names(config: ProjectConfig, root: Path, runner: Callable[..., RunResult] = run) -> list[str]:
    model = _compose_model(config, root, runner)
    services = model.get("services") if isinstance(model, dict) else None
    if isinstance(services, dict):
        return list(services)
    result = runner(compose_cmd(config, root, "config", ["--services"], with_metadata=False), cwd=root)
    if result.code != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _compose_dependencies(model: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    services = model.get("services") if isinstance(model, dict) else None
    if not isinstance(services, dict):
        return result
    for name, raw in services.items():
        if not isinstance(raw, dict):
            continue
        depends = raw.get("depends_on") or []
        if isinstance(depends, dict):
            values = list(depends)
        elif isinstance(depends, list):
            values = [str(item) for item in depends]
        else:
            values = []
        result[str(name)] = tuple(values)
    return result


def _repository_service_map(config: ProjectConfig) -> tuple[dict[str, str], dict[str, Repository]]:
    selector_to_service: dict[str, str] = {}
    service_to_repo: dict[str, Repository] = {}
    for repo in config.repositories:
        if repo.is_root:
            continue
        service = repo.service_name
        selector_to_service[repo.repo] = service
        selector_to_service[repo.path] = service
        service_to_repo.setdefault(service, repo)
    return selector_to_service, service_to_repo


def discover_runtime_services(
    config: ProjectConfig,
    root: Path,
    selected: Iterable[str] | None = None,
    runner: Callable[..., RunResult] = run,
) -> list[RuntimeService]:
    runtime_cfg = _runtime_config(config)
    explicit = runtime_cfg.get("services") or {}
    if not isinstance(explicit, dict):
        raise RuntimeErrorDetail("runtime.services must be an object keyed by Compose service name")

    model = _compose_model(config, root, runner)
    compose_names = list((model.get("services") or {}).keys()) if isinstance(model.get("services"), dict) else []
    if not compose_names:
        compose_names = _compose_service_names(config, root, runner)
    compose_deps = _compose_dependencies(model)
    selector_to_service, service_to_repo = _repository_service_map(config)

    names: list[str] = []
    seen: set[str] = set()
    for name in [*compose_names, *service_to_repo, *explicit]:
        text = str(name)
        if text and text not in seen:
            names.append(text)
            seen.add(text)

    requested = {str(item) for item in selected or [] if str(item)}
    unknown = sorted(requested - set(names))
    if unknown:
        raise RuntimeErrorDetail("unknown runtime service(s): " + ", ".join(unknown))

    specs: list[RuntimeService] = []
    known_names = set(seen)
    for name in names:
        raw = explicit.get(name) or {}
        if not isinstance(raw, dict):
            raise RuntimeErrorDetail(f"runtime.services.{name} must be an object")
        repo = service_to_repo.get(name)
        dependencies: list[str] = []
        if "depends_on" in raw:
            dependencies = [str(item) for item in raw.get("depends_on") or []]
        elif name in compose_deps:
            dependencies = list(compose_deps[name])
        elif repo:
            dependencies = [selector_to_service.get(str(item), str(item)) for item in repo.depends_on]
        dependencies = [item for item in dependencies if item in known_names and item != name]

        probe = raw.get("probe")
        if probe is None and repo and repo.health_url:
            probe = {"type": "http", "url": repo.health_url}
        elif probe is None and repo and repo.host_port:
            probe = {"type": "tcp", "host": "127.0.0.1", "port": repo.host_port}

        specs.append(RuntimeService(
            name=name,
            required=bool(raw.get("required", True)),
            depends_on=tuple(dict.fromkeys(dependencies)),
            timeout_seconds=float(raw["timeout_seconds"]) if raw.get("timeout_seconds") is not None else None,
            probe=dict(probe) if isinstance(probe, dict) else None,
            remediation=str(raw["remediation"]) if raw.get("remediation") else None,
        ))
    if requested:
        by_name = {item.name: item for item in specs}
        included = set(requested)
        queue = list(requested)
        while queue:
            current = by_name[queue.pop(0)]
            for dependency in current.depends_on:
                if dependency in by_name and dependency not in included:
                    included.add(dependency)
                    queue.append(dependency)
        specs = [item for item in specs if item.name in included]
    return specs


def runtime_levels(services: Iterable[RuntimeService]) -> list[list[RuntimeService]]:
    selected = list(services)
    names = {item.name for item in selected}
    by_name = {item.name: item for item in selected}
    remaining = {item.name: {dep for dep in item.depends_on if dep in names} for item in selected}
    done: set[str] = set()
    levels: list[list[RuntimeService]] = []
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if deps <= done)
        if not ready:
            raise RuntimeErrorDetail("runtime dependency cycle among: " + ", ".join(sorted(remaining)))
        levels.append([by_name[name] for name in ready])
        done.update(ready)
        for name in ready:
            remaining.pop(name, None)
    return levels


def _container_id(config: ProjectConfig, root: Path, service: str, runner: Callable[..., RunResult]) -> str | None:
    result = runner(compose_cmd(config, root, "ps", ["-q", service], with_metadata=False), cwd=root)
    if result.code != 0:
        return None
    values = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return values[0] if values else None


def _inspect_container(engine: str, container_id: str, runner: Callable[..., RunResult]) -> dict[str, Any]:
    result = runner([engine, "inspect", container_id])
    if result.code != 0:
        return {}
    try:
        data = _parse_json(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {}
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return {}


def _http_probe(probe: dict[str, Any]) -> ProbeResult:
    url = str(probe.get("url") or "")
    if not url:
        return ProbeResult("http", False, "missing probe.url")
    timeout = float(probe.get("timeout_seconds") or 2)
    expected = {int(item) for item in (probe.get("expected_status") or [200, 204])}
    method = str(probe.get("method") or "GET").upper()
    headers = {str(key): str(value) for key, value in (probe.get("headers") or {}).items()}
    started = time.monotonic()
    try:
        request = urllib.request.Request(url, method=method, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - user-controlled local readiness URL
            status = int(response.status)
        latency = int((time.monotonic() - started) * 1000)
        return ProbeResult("http", status in expected, f"HTTP {status} from {url}", latency)
    except urllib.error.HTTPError as exc:
        latency = int((time.monotonic() - started) * 1000)
        return ProbeResult("http", int(exc.code) in expected, f"HTTP {exc.code} from {url}", latency)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        latency = int((time.monotonic() - started) * 1000)
        return ProbeResult("http", False, f"{url}: {exc}", latency)


def _tcp_probe(probe: dict[str, Any]) -> ProbeResult:
    host = str(probe.get("host") or "127.0.0.1")
    port = probe.get("port")
    if port is None:
        return ProbeResult("tcp", False, "missing probe.port")
    timeout = float(probe.get("timeout_seconds") or 2)
    started = time.monotonic()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            pass
        latency = int((time.monotonic() - started) * 1000)
        return ProbeResult("tcp", True, f"connected to {host}:{int(port)}", latency)
    except OSError as exc:
        latency = int((time.monotonic() - started) * 1000)
        return ProbeResult("tcp", False, f"{host}:{int(port)}: {exc}", latency)


def _command_probe(probe: dict[str, Any], root: Path, runner: Callable[..., RunResult]) -> ProbeResult:
    command = probe.get("command")
    if not isinstance(command, list) or not command:
        return ProbeResult("command", False, "probe.command must be a non-empty array")
    started = time.monotonic()
    result = runner([str(item) for item in command], cwd=root)
    latency = int((time.monotonic() - started) * 1000)
    detail = result.stdout or result.stderr or f"exit={result.code}"
    return ProbeResult("command", result.code == 0, detail[:500], latency)


def execute_probe(
    probe: dict[str, Any] | None,
    root: Path,
    runner: Callable[..., RunResult] = run,
) -> ProbeResult | None:
    if not probe:
        return None
    probe_type = str(probe.get("type") or "").lower()
    if probe_type == "http":
        return _http_probe(probe)
    if probe_type == "tcp":
        return _tcp_probe(probe)
    if probe_type == "command":
        return _command_probe(probe, root, runner)
    return ProbeResult(probe_type or "unknown", False, f"unsupported probe type: {probe_type or '-'}")


def _default_remediation(name: str, state: str, health: str | None, probe: ProbeResult | None) -> str:
    if state == "missing":
        return f"Start the service with: rfm runtime up --service {name} --apply"
    if not state == "running":
        return f"Inspect logs and restart: rfm compose logs -- {name}"
    if health == "unhealthy":
        return f"Inspect the container health log and run: rfm runtime doctor --service {name} --logs"
    if probe and not probe.ok:
        return f"Verify the configured {probe.probe_type} readiness probe for service {name}"
    return f"Add a Compose healthcheck or runtime.services.{name}.probe configuration"


def inspect_service(
    config: ProjectConfig,
    root: Path,
    spec: RuntimeService,
    *,
    engine: str,
    runner: Callable[..., RunResult] = run,
) -> ServiceStatus:
    container_id = _container_id(config, root, spec.name, runner)
    if not container_id:
        remediation = spec.remediation or _default_remediation(spec.name, "missing", None, None)
        return ServiceStatus(
            name=spec.name, required=spec.required, depends_on=spec.depends_on,
            container_id=None, state="missing", running=False, ready=False,
            readiness_source="container", reason="Compose service has no container", remediation=remediation,
        )

    inspected = _inspect_container(engine, container_id, runner)
    state_data = inspected.get("State") if isinstance(inspected, dict) else {}
    if not isinstance(state_data, dict):
        state_data = {}
    state = str(state_data.get("Status") or ("running" if state_data.get("Running") else "unknown")).lower()
    running = bool(state_data.get("Running", state == "running"))
    health_data = state_data.get("Health") if isinstance(state_data.get("Health"), dict) else {}
    health = str(health_data.get("Status")) if health_data and health_data.get("Status") else None
    exit_code = state_data.get("ExitCode")
    try:
        exit_code = int(exit_code) if exit_code is not None else None
    except (TypeError, ValueError):
        exit_code = None

    probe_result = execute_probe(spec.probe, root, runner) if running else None
    runtime_cfg = _runtime_config(config)
    running_fallback = bool(runtime_cfg.get("default_running_is_ready", True))
    if not running:
        ready = False
        source = "container"
        reason = f"container state is {state}"
    elif probe_result is not None:
        ready = probe_result.ok
        source = f"probe:{probe_result.probe_type}"
        reason = None if ready else probe_result.detail
    elif health is not None:
        ready = health == "healthy"
        source = "compose-health"
        reason = None if ready else f"container health is {health}"
    else:
        ready = running_fallback
        source = "running-fallback" if running_fallback else "unverified"
        reason = None if ready else "service is running but has no healthcheck or readiness probe"

    remediation = spec.remediation or (None if ready else _default_remediation(spec.name, state, health, probe_result))
    return ServiceStatus(
        name=spec.name, required=spec.required, depends_on=spec.depends_on,
        container_id=container_id, state=state, running=running, ready=ready,
        readiness_source=source, health=health, exit_code=exit_code, reason=reason,
        probe=probe_result, remediation=remediation,
    )


def runtime_status(
    config: ProjectConfig,
    root: Path,
    selected: Iterable[str] | None = None,
    *,
    runner: Callable[..., RunResult] = run,
) -> RuntimeReport:
    compose_bin = detect_compose_bin(config.compose.get("bin"))
    engine = _engine_name(config, compose_bin)
    services = discover_runtime_services(config, root, selected, runner)
    statuses = [inspect_service(config, root, item, engine=engine, runner=runner) for item in services]
    ready = all(item.ready for item in statuses if item.required)
    return RuntimeReport(ready=ready, engine=engine, compose_bin=compose_bin, services=statuses)


def _service_logs(
    config: ProjectConfig,
    root: Path,
    service: str,
    tail: int,
    runner: Callable[..., RunResult],
) -> str:
    result = runner(compose_cmd(config, root, "logs", ["--no-color", "--tail", str(max(1, tail)), service], with_metadata=False), cwd=root)
    text = result.stdout or result.stderr
    return text[-12000:]


def runtime_doctor(
    config: ProjectConfig,
    root: Path,
    selected: Iterable[str] | None = None,
    *,
    include_logs: bool = False,
    tail: int | None = None,
    runner: Callable[..., RunResult] = run,
) -> RuntimeReport:
    report = runtime_status(config, root, selected, runner=runner)
    log_tail = int(tail or _runtime_config(config).get("log_tail") or 80)
    for status in report.services:
        if status.required and not status.ready:
            report.errors.append(f"{status.name}: {status.reason or 'not ready'}")
            if include_logs:
                status.logs = _service_logs(config, root, status.name, log_tail, runner)
    return report


def wait_runtime(
    config: ProjectConfig,
    root: Path,
    selected: Iterable[str] | None = None,
    *,
    timeout_seconds: float | None = None,
    interval_seconds: float | None = None,
    include_logs: bool = False,
    tail: int | None = None,
    runner: Callable[..., RunResult] = run,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> RuntimeReport:
    runtime_cfg = _runtime_config(config)
    timeout = float(timeout_seconds if timeout_seconds is not None else runtime_cfg.get("timeout_seconds") or 120)
    interval = float(interval_seconds if interval_seconds is not None else runtime_cfg.get("interval_seconds") or 2)
    started = monotonic_fn()
    last: RuntimeReport | None = None
    while True:
        last = runtime_status(config, root, selected, runner=runner)
        if last.ready:
            return last
        elapsed = monotonic_fn() - started
        if elapsed >= timeout:
            return runtime_doctor(config, root, selected, include_logs=include_logs, tail=tail, runner=runner)
        sleep_fn(max(0.05, interval))


def ordered_runtime_up(
    config: ProjectConfig,
    root: Path,
    selected: Iterable[str] | None = None,
    *,
    apply: bool = False,
    timeout_seconds: float | None = None,
    interval_seconds: float | None = None,
    include_logs: bool = True,
    tail: int | None = None,
    runner: Callable[..., RunResult] = run,
    interactive_runner: Callable[..., int] = run_interactive,
) -> RuntimeReport:
    compose_bin = detect_compose_bin(config.compose.get("bin"))
    engine = _engine_name(config, compose_bin)
    services = discover_runtime_services(config, root, selected, runner)
    levels = runtime_levels(services)
    if not apply:
        for index, level in enumerate(levels):
            names = [item.name for item in level]
            command = compose_cmd(config, root, "up", ["-d", *names], with_metadata=True)
            print(f"[PLAN] runtime level {index}: {', '.join(names)}")
            print(f"[DRY-RUN] {shlex_join(command)}")
        statuses = [
            ServiceStatus(
                name=item.name, required=item.required, depends_on=item.depends_on,
                container_id=None, state="planned", running=False, ready=False,
                readiness_source="planned", reason="dry-run; no containers were started",
            )
            for level in levels for item in level
        ]
        return RuntimeReport(ready=False, engine=engine, compose_bin=compose_bin, services=statuses)

    for index, level in enumerate(levels):
        names = [item.name for item in level]
        command = compose_cmd(config, root, "up", ["-d", *names], with_metadata=True)
        code = interactive_runner(command, cwd=root, dry_run=False, description=f"runtime up level {index}: {', '.join(names)}")
        if code != 0:
            report = runtime_doctor(config, root, names, include_logs=include_logs, tail=tail, runner=runner)
            report.errors.insert(0, f"compose up failed for runtime level {index} with exit code {code}")
            report.ready = False
            return report
        report = wait_runtime(
            config, root, names,
            timeout_seconds=max(
                [item.timeout_seconds for item in level if item.timeout_seconds is not None]
                or [timeout_seconds if timeout_seconds is not None else float(_runtime_config(config).get("timeout_seconds") or 120)]
            ),
            interval_seconds=interval_seconds,
            include_logs=include_logs,
            tail=tail,
            runner=runner,
        )
        if not report.ready:
            report.errors.insert(0, f"runtime level {index} did not become ready")
            return report
    return runtime_status(config, root, selected, runner=runner)
