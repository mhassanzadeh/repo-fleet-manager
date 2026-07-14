from __future__ import annotations

import io
import json
import os
import re
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, TextIO

from jsonschema import Draft202012Validator

EVENT_SCHEMA_VERSION = "1.0.0"
DEFAULT_LOGS_DIR = ".repo-fleet/logs"
SUPPORTED_FORMATS = ("text", "json", "jsonl")
_SECRET_KEYS = {
    "token", "access_token", "private_token", "password", "passwd", "secret",
    "client_secret", "private_key", "ssh_private_key", "api_key", "apikey",
    "github_token", "gitlab_token", "authorization", "auth", "credential",
}
_SECRET_FLAGS = {
    "--token", "--password", "--passwd", "--secret", "--client-secret",
    "--private-key", "--api-key", "--authorization",
}
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(token|access[_-]?token|private[_-]?token|password|passwd|secret|client[_-]?secret|api[_-]?key|authorization)\s*([:=])\s*([^\s,;]+)"
)
_URL_CREDENTIAL = re.compile(r"(?P<scheme>https?://)(?P<user>[^:/@\s]+):(?P<password>[^@\s]+)@")
_TOKEN_LIKE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|glpat-[A-Za-z0-9_-]{16,})\b")
_CURRENT_SESSION: ContextVar["AuditSession | None"] = ContextVar("rfm_audit_session", default=None)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def redact_text(value: str) -> str:
    text = _URL_CREDENTIAL.sub(lambda match: f"{match.group('scheme')}{match.group('user')}:***@", value)
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}***", text)
    return _TOKEN_LIKE.sub("***", text)


def _is_secret_key(key: str, extra_keys: Iterable[str] = ()) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    custom = {str(item).strip().lower().replace("-", "_") for item in extra_keys}
    return normalized in _SECRET_KEYS or normalized in custom or any(part in normalized for part in ("token", "password", "secret", "private_key", "api_key"))


def redact(value: Any, extra_keys: Iterable[str] = ()) -> Any:
    if isinstance(value, dict):
        return {str(key): ("***" if _is_secret_key(str(key), extra_keys) else redact(item, extra_keys)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, extra_keys) for item in value]
    if isinstance(value, tuple):
        return [redact(item, extra_keys) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_argv(argv: Iterable[str]) -> list[str]:
    result: list[str] = []
    hide_next = False
    for raw in argv:
        item = str(raw)
        if hide_next:
            result.append("***")
            hide_next = False
            continue
        lowered = item.lower()
        if lowered in _SECRET_FLAGS:
            result.append(item)
            hide_next = True
            continue
        if any(lowered.startswith(flag + "=") for flag in _SECRET_FLAGS):
            result.append(item.split("=", 1)[0] + "=***")
            continue
        if "=" in item and _is_secret_key(item.split("=", 1)[0]):
            result.append(item.split("=", 1)[0] + "=***")
            continue
        result.append(redact_text(item))
    return result


def _safe_run_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    if not cleaned:
        raise ValueError("run id must contain a safe character")
    return cleaned


def resolve_logs_dir(root: Path, configured: str | None = None, override: str | None = None) -> Path:
    value = override or configured or DEFAULT_LOGS_DIR
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


@dataclass(slots=True)
class AuditSession:
    command: str
    argv: list[str]
    root: Path
    log_dir: Path
    enabled: bool = True
    run_id: str | None = None
    started_at: str = field(default_factory=utc_now)
    started_monotonic: float = field(default_factory=time.monotonic)
    sequence: int = 0
    operation_id: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    path: Path | None = None
    include_output: bool = True
    redact_keys: tuple[str, ...] = ()
    _token: Any = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        self.run_id = _safe_run_id(self.run_id or f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:10]}")
        if self.enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.path = self.log_dir / f"{self.run_id}.jsonl"
            if not self.path.exists():
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
        self.emit("run.started", level="info", status="running", data={"pid": os.getpid()})

    def __enter__(self) -> "AuditSession":
        self._token = _CURRENT_SESSION.set(self)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._token is not None:
            _CURRENT_SESSION.reset(self._token)
            self._token = None

    def set_operation_id(self, operation_id: str | None) -> None:
        if operation_id and operation_id != self.operation_id:
            self.operation_id = operation_id
            self.emit("operation.correlated", data={"operation_id": operation_id})

    def emit(
        self,
        event_type: str,
        *,
        level: str = "info",
        message: str | None = None,
        status: str | None = None,
        exit_code: int | None = None,
        duration_ms: int | None = None,
        repo: str | None = None,
        service: str | None = None,
        data: Any = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        self.sequence += 1
        event = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "event_id": f"{self.run_id}-{self.sequence:06d}",
            "run_id": self.run_id,
            "sequence": self.sequence,
            "timestamp": utc_now(),
            "type": event_type,
            "level": level,
            "command": self.command,
            "argv": redact_argv(self.argv),
            "root": str(self.root),
            "operation_id": self.operation_id,
            "repo": repo,
            "service": service,
            "status": status,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "message": redact_text(message) if message else None,
            "data": redact(data, self.redact_keys),
        }
        self.events.append(event)
        if persist and self.enabled and self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        return event

    def record_output(self, stdout: str, stderr: str) -> None:
        for stream_name, text in (("stdout", stdout), ("stderr", stderr)):
            cleaned = text.strip()
            if not cleaned:
                continue
            try:
                payload = json.loads(cleaned)
            except json.JSONDecodeError:
                payload = None
            if payload is not None:
                self.emit(
                    "command.output",
                    level="error" if stream_name == "stderr" else "info",
                    data={"stream": stream_name, "payload": payload},
                    persist=self.include_output,
                )
                continue
            for line in text.splitlines():
                if line:
                    self.emit(
                        "command.output",
                        level="error" if stream_name == "stderr" else "info",
                        message=line,
                        data={"stream": stream_name},
                        persist=self.include_output,
                    )

    def complete(self, exit_code: int, *, error: str | None = None) -> dict[str, Any]:
        duration_ms = max(0, int((time.monotonic() - self.started_monotonic) * 1000))
        return self.emit(
            "run.completed",
            level="error" if exit_code else "info",
            status="failed" if exit_code else "succeeded",
            exit_code=exit_code,
            duration_ms=duration_ms,
            message=error,
        )

    def envelope(self, exit_code: int, stdout: str, stderr: str) -> dict[str, Any]:
        payload: Any = None
        cleaned = stdout.strip()
        if cleaned:
            try:
                payload = json.loads(cleaned)
            except json.JSONDecodeError:
                payload = {"lines": [redact_text(line) for line in stdout.splitlines()]}
        return {
            "schema_version": EVENT_SCHEMA_VERSION,
            "run_id": self.run_id,
            "command": self.command,
            "argv": redact_argv(self.argv),
            "root": str(self.root),
            "operation_id": self.operation_id,
            "status": "succeeded" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "duration_ms": max(0, int((time.monotonic() - self.started_monotonic) * 1000)),
            "result": redact(payload, self.redact_keys),
            "stderr": [redact_text(line) for line in stderr.splitlines() if line],
            "audit_log": str(self.path) if self.path else None,
        }


class RedactingTee(io.TextIOBase):
    def __init__(self, original: TextIO, buffer: io.StringIO):
        self.original = original
        self.buffer = buffer

    def writable(self) -> bool:
        return True

    def write(self, value: str) -> int:
        clean = redact_text(value)
        self.original.write(clean)
        self.buffer.write(clean)
        return len(value)

    def flush(self) -> None:
        self.original.flush()


def current_session() -> AuditSession | None:
    return _CURRENT_SESSION.get()


def correlate_operation(operation_id: str | None) -> None:
    session = current_session()
    if session is not None:
        session.set_operation_id(operation_id)


def load_event_schema(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        from importlib.resources import files
        path = Path(str(files("repo_fleet_manager").joinpath("data/rfm-event.schema.json")))
    return json.loads(path.read_text(encoding="utf-8"))


def verify_log(path: Path, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    source = path.expanduser().resolve()
    validator = Draft202012Validator(schema or load_event_schema())
    errors: list[str] = []
    events = 0
    run_ids: set[str] = set()
    previous_sequence = 0
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {"path": str(source), "valid": False, "events": 0, "run_ids": [], "errors": [str(exc)]}
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {index}: invalid JSON: {exc}")
            continue
        events += 1
        run_ids.add(str(event.get("run_id") or ""))
        for error in validator.iter_errors(event):
            errors.append(f"line {index}: {error.json_path}: {error.message}")
        sequence = event.get("sequence")
        if isinstance(sequence, int):
            if sequence <= previous_sequence:
                errors.append(f"line {index}: non-increasing sequence {sequence}")
            previous_sequence = sequence
    if len(run_ids) > 1:
        errors.append("log contains multiple run_id values")
    if not events:
        errors.append("log contains no events")
    return {"path": str(source), "valid": not errors, "events": events, "run_ids": sorted(run_ids), "errors": errors}


def list_logs(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
        first: dict[str, Any] = {}
        last: dict[str, Any] = {}
        count = 0
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if not first:
                        first = event
                    last = event
                    count += 1
        except (OSError, json.JSONDecodeError):
            pass
        rows.append({
            "run_id": path.stem,
            "path": str(path),
            "events": count,
            "command": first.get("command"),
            "started_at": first.get("timestamp"),
            "status": last.get("status"),
            "exit_code": last.get("exit_code"),
            "duration_ms": last.get("duration_ms"),
            "size_bytes": path.stat().st_size,
        })
    return rows


def purge_logs(directory: Path, retention_days: int, *, apply: bool) -> list[str]:
    cutoff = time.time() - max(1, retention_days) * 86400
    selected = [path for path in directory.glob("*.jsonl") if path.stat().st_mtime < cutoff] if directory.exists() else []
    if apply:
        for path in selected:
            path.unlink(missing_ok=True)
    return [str(path) for path in selected]
