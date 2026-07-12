from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import uuid
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .shell import run, shlex_join

_CURRENT_OPERATION: ContextVar["OperationJournal | None"] = ContextVar("rfm_current_operation", default=None)
_ACTIVE_OPERATION: "OperationJournal | None" = None
_ACTIVE_OPERATION_LOCK = threading.RLock()


class SafetyError(RuntimeError):
    pass


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def runtime_dir(root: Path) -> Path:
    return root / ".repo-fleet"


def operations_dir(root: Path, configured: str | None = None) -> Path:
    value = configured or ".repo-fleet/operations"
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def lock_path(root: Path, configured: str | None = None) -> Path:
    value = configured or ".repo-fleet/lock"
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass(slots=True)
class WorkspaceLock:
    root: Path
    command: str
    path: Path
    force: bool = False
    reason: str | None = None
    acquired: bool = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "started_at": utc_now(),
            "command": self.command,
            "reason": self.reason,
        }
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            existing: dict[str, Any] = {}
            try:
                existing = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                existing = {"raw": self.path.read_text(encoding="utf-8", errors="replace") if self.path.exists() else ""}
            same_host = existing.get("host") == socket.gethostname()
            stale = same_host and isinstance(existing.get("pid"), int) and not _pid_alive(existing["pid"])
            if not (self.force and self.reason):
                state = "stale" if stale else "active or unknown"
                raise SafetyError(
                    f"workspace lock exists ({state}): {self.path}\n"
                    f"holder: {json.dumps(existing, ensure_ascii=False)}\n"
                    "Use --force --reason '<why>' only after confirming no other RFM process is running."
                )
            self.path.unlink(missing_ok=True)
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        self.acquired = True

    def release(self) -> None:
        if self.acquired:
            try:
                current = json.loads(self.path.read_text(encoding="utf-8"))
                if current.get("pid") == os.getpid() and current.get("host") == socket.gethostname():
                    self.path.unlink(missing_ok=True)
            except Exception:
                self.path.unlink(missing_ok=True)
            self.acquired = False

    def __enter__(self) -> "WorkspaceLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.release()


class OperationJournal:
    def __init__(self, root: Path, command: str, argv: list[str], directory: Path, operation_id: str | None = None, reason: str | None = None):
        self._lock = threading.RLock()
        self.root = root.resolve()
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.id = operation_id or f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        self.path = self.directory / f"{self.id}.json"
        self.backup_dir = self.directory / self.id / "backups"
        attempt = {"started_at": utc_now(), "finished_at": None, "status": "running", "reason": reason}
        if operation_id and self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            for step in self.data.get("steps", []):
                if step.get("status") == "running":
                    step["status"] = "interrupted"
                    step["finished_at"] = utc_now()
            self.data["resume_count"] = int(self.data.get("resume_count", 0)) + 1
            self.data["status"] = "running"
            self.data["updated_at"] = utc_now()
            self.data["finished_at"] = None
            self.data["exit_code"] = None
            self.data["error"] = None
            self.data.setdefault("attempts", []).append(attempt)
        else:
            self.data = {
                "schema_version": "1.0.0",
                "id": self.id,
                "command": command,
                "argv": argv,
                "root": str(self.root),
                "status": "running",
                "started_at": utc_now(),
                "updated_at": utc_now(),
                "finished_at": None,
                "reason": reason,
                "resume_count": 0,
                "attempts": [attempt],
                "steps": [],
                "rollback": [],
                "error": None,
            }
        self.save()

    def save(self) -> None:
        with self._lock:
            self.data["updated_at"] = utc_now()
            temp = self.path.with_suffix(f".{threading.get_ident()}.tmp")
            temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temp.replace(self.path)

    def begin_step(self, description: str, command: list[str] | None = None, cwd: Path | None = None) -> int:
        with self._lock:
            step = {
                "id": len(self.data["steps"]) + 1,
                "description": description,
                "command": command,
                "cwd": str(cwd.resolve()) if cwd else None,
                "status": "running",
                "started_at": utc_now(),
                "finished_at": None,
                "code": None,
            }
            self.data["steps"].append(step)
            self.save()
            return len(self.data["steps"]) - 1

    def end_step(self, index: int, code: int, detail: str | None = None) -> None:
        with self._lock:
            step = self.data["steps"][index]
            step["status"] = "completed" if code == 0 else "failed"
            step["code"] = code
            step["finished_at"] = utc_now()
            if detail:
                step["detail"] = detail
            self.save()

    def add_rollback(self, action: dict[str, Any]) -> None:
        with self._lock:
            identity = {k: v for k, v in action.items() if k not in {"status", "error", "completed_at"}}
            for existing in self.data["rollback"]:
                existing_identity = {k: v for k, v in existing.items() if k not in {"status", "error", "completed_at"}}
                if existing_identity == identity:
                    return
            self.data["rollback"].append(action)
            self.save()

    def track_created_path(self, path: Path) -> None:
        resolved = path.resolve()
        self.add_rollback({"type": "remove_path", "path": str(resolved), "status": "pending"})

    def backup_file(self, path: Path) -> None:
        resolved = path.resolve()
        existed = resolved.exists()
        backup_path: Path | None = None
        if existed:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = self.backup_dir / f"{len(self.data['rollback']) + 1}-{resolved.name}"
            shutil.copy2(resolved, backup_path)
        self.add_rollback({
            "type": "restore_file",
            "path": str(resolved),
            "existed": existed,
            "backup": str(backup_path) if backup_path else None,
            "status": "pending",
        })

    def track_git_remote(self, worktree: Path, name: str, previous_url: str | None) -> None:
        self.add_rollback({
            "type": "git_remote",
            "worktree": str(worktree.resolve()),
            "name": name,
            "previous_url": previous_url,
            "status": "pending",
        })

    def track_git_head(self, worktree: Path) -> None:
        resolved = worktree.resolve()
        result = run(["git", "rev-parse", "--verify", "HEAD"], cwd=resolved)
        if result.code != 0 or not result.stdout:
            return
        branch_result = run(["git", "branch", "--show-current"], cwd=resolved)
        self.add_rollback({
            "type": "git_head",
            "worktree": str(resolved),
            "head": result.stdout.strip(),
            "branch": branch_result.stdout.strip() if branch_result.code == 0 and branch_result.stdout else None,
            "status": "pending",
        })

    def note_manual_rollback(self, note: str) -> None:
        self.add_rollback({"type": "manual", "note": note, "status": "pending"})

    def _finish_attempt(self, status: str) -> None:
        attempts = self.data.setdefault("attempts", [])
        if attempts:
            attempts[-1]["status"] = status
            attempts[-1]["finished_at"] = utc_now()

    def complete(self, code: int = 0) -> None:
        status = "completed" if code == 0 else "failed"
        self.data["status"] = status
        self.data["exit_code"] = code
        self.data["finished_at"] = utc_now()
        self._finish_attempt(status)
        self.save()

    def fail(self, error: BaseException) -> None:
        self.data["status"] = "failed"
        self.data["error"] = f"{type(error).__name__}: {error}"
        self.data["finished_at"] = utc_now()
        self._finish_attempt("failed")
        self.save()

    def rollback(self, force: bool = False) -> tuple[int, list[str]]:
        messages: list[str] = []
        failures = 0
        rollback_actions = list(reversed(self.data.get("rollback", [])))
        # Restore repository history before restoring individual files. This avoids
        # checkout/reset conflicts when a rollback also has file backups.
        rollback_actions.sort(key=lambda item: 0 if item.get("type") == "git_head" else 1)
        for action in rollback_actions:
            if action.get("status") == "completed":
                continue
            kind = action.get("type")
            try:
                if kind == "remove_path":
                    path = Path(action["path"]).resolve()
                    if not _is_within(path, self.root) and not force:
                        raise SafetyError(f"refusing to remove path outside workspace without --force: {path}")
                    if path.is_dir() and not path.is_symlink():
                        shutil.rmtree(path)
                    else:
                        path.unlink(missing_ok=True)
                    messages.append(f"removed {path}")
                elif kind == "restore_file":
                    path = Path(action["path"])
                    if action.get("existed"):
                        backup = Path(action["backup"])
                        path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup, path)
                        messages.append(f"restored {path}")
                    else:
                        path.unlink(missing_ok=True)
                        messages.append(f"removed generated file {path}")
                elif kind == "git_remote":
                    worktree = Path(action["worktree"])
                    name = action["name"]
                    previous = action.get("previous_url")
                    if previous:
                        result = run(["git", "remote", "set-url", name, previous], cwd=worktree)
                    else:
                        result = run(["git", "remote", "remove", name], cwd=worktree)
                    if result.code != 0:
                        raise RuntimeError(result.stderr or result.stdout)
                    messages.append(f"restored remote {name} in {worktree}")
                elif kind == "git_head":
                    worktree = Path(action["worktree"])
                    head = str(action["head"])
                    branch = action.get("branch")
                    if branch:
                        checkout = run(["git", "checkout", "-B", str(branch), head], cwd=worktree)
                        if checkout.code != 0:
                            raise RuntimeError(checkout.stderr or checkout.stdout)
                    result = run(["git", "reset", "--hard", head], cwd=worktree)
                    if result.code != 0:
                        raise RuntimeError(result.stderr or result.stdout)
                    messages.append(f"restored Git HEAD {head[:12]} in {worktree}")
                elif kind == "command":
                    cmd = [str(item) for item in action.get("command", [])]
                    cwd = Path(action["cwd"]) if action.get("cwd") else self.root
                    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
                    messages.append(f"ran rollback command: {shlex_join(cmd)}")
                elif kind == "manual":
                    raise RuntimeError(f"manual action required: {action.get('note')}")
                else:
                    raise RuntimeError(f"unknown rollback action: {kind}")
                action["status"] = "completed"
                action["completed_at"] = utc_now()
            except Exception as exc:  # noqa: BLE001
                failures += 1
                action["status"] = "failed"
                action["error"] = str(exc)
                messages.append(f"FAILED {kind}: {exc}")
            self.save()
        self.data["status"] = "rolled_back" if failures == 0 else "rollback_failed"
        self.data["rolled_back_at"] = utc_now()
        self.save()
        return failures, messages


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def current_operation() -> OperationJournal | None:
    return _CURRENT_OPERATION.get() or _ACTIVE_OPERATION


def record_command_start(description: str, command: list[str], cwd: Path | None) -> int | None:
    operation = current_operation()
    return operation.begin_step(description, command, cwd) if operation else None


def record_command_end(index: int | None, code: int, detail: str | None = None) -> None:
    operation = current_operation()
    if operation is not None and index is not None:
        operation.end_step(index, code, detail)


def track_created_path(path: Path) -> None:
    operation = current_operation()
    if operation:
        operation.track_created_path(path)


def backup_file(path: Path) -> None:
    operation = current_operation()
    if operation:
        operation.backup_file(path)


def track_git_remote(worktree: Path, name: str, previous_url: str | None) -> None:
    operation = current_operation()
    if operation:
        operation.track_git_remote(worktree, name, previous_url)


def track_git_head(worktree: Path) -> None:
    operation = current_operation()
    if operation:
        operation.track_git_head(worktree)


def note_manual_rollback(note: str) -> None:
    operation = current_operation()
    if operation:
        operation.note_manual_rollback(note)


@contextmanager
def mutation_context(
    root: Path,
    command: str,
    argv: list[str],
    operations_path: Path,
    lock_file: Path,
    force: bool = False,
    reason: str | None = None,
    operation_id: str | None = None,
) -> Iterator[OperationJournal]:
    if force and not (reason and reason.strip()):
        raise SafetyError("--force requires a non-empty --reason")
    global _ACTIVE_OPERATION
    with WorkspaceLock(root, command, lock_file, force=force, reason=reason):
        journal = OperationJournal(root, command, argv, operations_path, operation_id=operation_id, reason=reason)
        token = _CURRENT_OPERATION.set(journal)
        with _ACTIVE_OPERATION_LOCK:
            previous_active = _ACTIVE_OPERATION
            _ACTIVE_OPERATION = journal
        try:
            yield journal
        except BaseException as exc:
            journal.fail(exc)
            raise
        finally:
            with _ACTIVE_OPERATION_LOCK:
                _ACTIVE_OPERATION = previous_active
            _CURRENT_OPERATION.reset(token)


def list_operation_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def load_operation(directory: Path, operation_id: str) -> OperationJournal:
    path = directory / f"{operation_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"operation not found: {operation_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    root = Path(data["root"])
    journal = object.__new__(OperationJournal)
    journal._lock = threading.RLock()
    journal.root = root
    journal.directory = directory
    journal.id = operation_id
    journal.path = path
    journal.backup_dir = directory / operation_id / "backups"
    journal.data = data
    return journal
