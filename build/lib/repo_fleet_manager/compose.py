from __future__ import annotations

from pathlib import Path

from .config import ProjectConfig
from .shell import command_exists, run, run_interactive


def detect_compose_bin(preferred: str | None = None) -> list[str]:
    if preferred:
        return preferred.split()
    if command_exists("podman-compose"):
        return ["podman-compose"]
    if command_exists("docker") and run(["docker", "compose", "version"]).code == 0:
        return ["docker", "compose"]
    raise RuntimeError("Neither podman-compose nor docker compose was found.")


def compose_files(config: ProjectConfig, root: Path, with_metadata: bool = True) -> tuple[list[str], str | None]:
    files = [str(root / str(config.compose.get("file", "infra-compose/docker-compose.yml")))]
    env_file = root / str(config.compose.get("env_file", "infra-compose/.env.example"))
    build_dir = root / str(config.project.get("build_dir", ".repo-fleet/build"))
    metadata = build_dir / "docker-compose.source-metadata.yml"
    compose_env = build_dir / "compose.env"
    if with_metadata and metadata.exists():
        files.append(str(metadata))
    if with_metadata and compose_env.exists():
        env_file = compose_env
    return files, str(env_file) if env_file.exists() else None


def compose_cmd(config: ProjectConfig, root: Path, action: str, extra_args: list[str] | None = None, with_metadata: bool = True) -> list[str]:
    cmd = detect_compose_bin(config.compose.get("bin"))
    files, env_file = compose_files(config, root, with_metadata)
    if env_file:
        cmd += ["--env-file", env_file]
    for file in files:
        cmd += ["-f", file]
    cmd += [action]
    if extra_args:
        cmd += extra_args
    return cmd


def run_compose(config: ProjectConfig, root: Path, action: str, extra_args: list[str] | None, apply: bool) -> int:
    changes_state = action in {"up", "down", "restart", "build", "pull"}
    dry_run = changes_state and not apply
    return run_interactive(compose_cmd(config, root, action, extra_args), cwd=root, dry_run=dry_run)
