from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shlex import quote
from typing import Iterable


@dataclass(slots=True)
class RunResult:
    code: int
    stdout: str
    stderr: str


def shlex_join(cmd: Iterable[str]) -> str:
    return " ".join(quote(str(part)) for part in cmd)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> RunResult:
    proc = subprocess.run(
        [str(part) for part in cmd],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = RunResult(proc.returncode, proc.stdout.strip(), proc.stderr.strip())
    if check and result.code != 0:
        raise RuntimeError(f"command failed ({result.code}): {shlex_join(cmd)}\n{result.stderr}")
    return result


def run_interactive(cmd: list[str], cwd: Path | None = None, dry_run: bool = True, description: str | None = None) -> int:
    if dry_run:
        print(f"[DRY-RUN] {shlex_join(cmd)}")
        return 0
    from .operations import record_command_end, record_command_start

    text = description or shlex_join(cmd)
    step = record_command_start(text, [str(part) for part in cmd], cwd)
    print(f"+ {shlex_join(cmd)}")
    code = subprocess.call([str(part) for part in cmd], cwd=str(cwd) if cwd else None)
    record_command_end(step, code)
    return code
