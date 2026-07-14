from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from shlex import quote
from typing import Iterable, TextIO


@dataclass(slots=True)
class RunResult:
    code: int
    stdout: str
    stderr: str


def shlex_join(cmd: Iterable[str]) -> str:
    return " ".join(quote(str(part)) for part in cmd)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _audit_session():
    try:
        from .observability import current_session
        return current_session()
    except Exception:  # noqa: BLE001
        return None


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> RunResult:
    command = [str(part) for part in cmd]
    session = _audit_session()
    started = time.monotonic()
    if session is not None:
        session.emit("process.started", data={"command": command, "cwd": str(cwd.resolve()) if cwd else None})
    proc = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = RunResult(proc.returncode, proc.stdout.strip(), proc.stderr.strip())
    if session is not None:
        session.emit(
            "process.completed",
            level="error" if result.code else "info",
            exit_code=result.code,
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
            data={
                "command": command,
                "cwd": str(cwd.resolve()) if cwd else None,
                "stdout": result.stdout or None,
                "stderr": result.stderr or None,
            },
        )
    if check and result.code != 0:
        raise RuntimeError(f"command failed ({result.code}): {shlex_join(cmd)}\n{result.stderr}")
    return result


def _pump(stream: TextIO, target: TextIO, collected: list[str]) -> None:
    for line in iter(stream.readline, ""):
        collected.append(line)
        target.write(line)
        target.flush()
    stream.close()


def run_interactive(cmd: list[str], cwd: Path | None = None, dry_run: bool = True, description: str | None = None) -> int:
    if dry_run:
        print(f"[DRY-RUN] {shlex_join(cmd)}")
        return 0
    from .operations import record_command_end, record_command_start

    command = [str(part) for part in cmd]
    text = description or shlex_join(cmd)
    step = record_command_start(text, command, cwd)
    print(f"+ {shlex_join(cmd)}")
    session = _audit_session()
    started = time.monotonic()
    if session is not None:
        session.emit("process.started", data={"command": command, "cwd": str(cwd.resolve()) if cwd else None, "interactive": True})
        proc = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        assert proc.stdout is not None and proc.stderr is not None
        threads = [
            threading.Thread(target=_pump, args=(proc.stdout, sys.stdout, stdout_lines), daemon=True),
            threading.Thread(target=_pump, args=(proc.stderr, sys.stderr, stderr_lines), daemon=True),
        ]
        for thread in threads:
            thread.start()
        code = proc.wait()
        for thread in threads:
            thread.join()
        session.emit(
            "process.completed",
            level="error" if code else "info",
            exit_code=code,
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
            data={
                "command": command,
                "cwd": str(cwd.resolve()) if cwd else None,
                "interactive": True,
                "stdout": "".join(stdout_lines).strip() or None,
                "stderr": "".join(stderr_lines).strip() or None,
            },
        )
    else:
        code = subprocess.call(command, cwd=str(cwd) if cwd else None)
    record_command_end(step, code)
    return code
