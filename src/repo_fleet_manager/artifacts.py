from __future__ import annotations

import json
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import ProjectConfig
from .operations import backup_file, track_created_path
from .plugin_api import ArtifactBackendPluginV1, ArtifactRequest, PluginResult
from .plugins import PluginError, registry_for


class ArtifactError(RuntimeError):
    pass


def artifact_scheme(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme and len(parsed.scheme) > 1:
        return parsed.scheme.lower()
    return "file"


def _local_path(uri: str, root: Path) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        text = unquote(parsed.path)
        path = Path(text)
    elif parsed.scheme:
        raise ArtifactError(f"not a local artifact URI: {uri}")
    else:
        path = Path(uri).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _copy(source: Path, destination: Path, overwrite: bool) -> None:
    if destination.exists():
        if not overwrite:
            raise ArtifactError(f"destination exists; use --overwrite: {destination}")
        backup_file(destination)
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    track_created_path(destination)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def _print_result(result: PluginResult, json_output: bool) -> int:
    if json_output:
        print(json.dumps({"code": result.code, "message": result.message, "data": result.data, "warnings": result.warnings}, ensure_ascii=False, indent=2))
    else:
        if result.message:
            print(result.message)
        if result.data:
            print(json.dumps(result.data, ensure_ascii=False, indent=2))
        for warning in result.warnings:
            print(f"[WARN] {warning}")
    return int(result.code)


def _plugin(config: ProjectConfig | None, scheme: str) -> ArtifactBackendPluginV1:
    plugin = registry_for(config).resolve("artifact-backend", scheme)
    if plugin is None or not isinstance(plugin, ArtifactBackendPluginV1):
        raise PluginError(f"no artifact backend plugin handles URI scheme: {scheme}")
    return plugin


def put_artifact(config: ProjectConfig | None, root: Path, source: str, uri: str, *, overwrite: bool = False, apply: bool = False, json_output: bool = False) -> int:
    root = root.resolve()
    source_path = Path(source).expanduser()
    source_path = source_path.resolve() if source_path.is_absolute() else (root / source_path).resolve()
    if not source_path.exists():
        raise ArtifactError(f"artifact source does not exist: {source_path}")
    scheme = artifact_scheme(uri)
    if scheme == "file":
        destination = _local_path(uri, root)
        if not apply:
            return _print_result(PluginResult(message=f"[DRY-RUN] copy {source_path} -> {destination}", data={"source": str(source_path), "destination": str(destination), "dry_run": True}), json_output)
        _copy(source_path, destination, overwrite)
        return _print_result(PluginResult(message=f"[OK] artifact stored: {destination}", data={"destination": str(destination)}), json_output)
    result = _plugin(config, scheme).execute(ArtifactRequest("put", root, uri, source=source_path, apply=apply, options={"overwrite": overwrite}))
    return _print_result(result, json_output)


def get_artifact(config: ProjectConfig | None, root: Path, uri: str, destination: str, *, overwrite: bool = False, apply: bool = False, json_output: bool = False) -> int:
    root = root.resolve()
    destination_path = Path(destination).expanduser()
    destination_path = destination_path.resolve() if destination_path.is_absolute() else (root / destination_path).resolve()
    scheme = artifact_scheme(uri)
    if scheme == "file":
        source = _local_path(uri, root)
        if not source.exists():
            raise ArtifactError(f"artifact does not exist: {source}")
        if not apply:
            return _print_result(PluginResult(message=f"[DRY-RUN] copy {source} -> {destination_path}", data={"source": str(source), "destination": str(destination_path), "dry_run": True}), json_output)
        _copy(source, destination_path, overwrite)
        return _print_result(PluginResult(message=f"[OK] artifact restored: {destination_path}", data={"destination": str(destination_path)}), json_output)
    result = _plugin(config, scheme).execute(ArtifactRequest("get", root, uri, destination=destination_path, apply=apply, options={"overwrite": overwrite}))
    return _print_result(result, json_output)


def list_artifacts(config: ProjectConfig | None, root: Path, uri: str, *, json_output: bool = False) -> int:
    root = root.resolve()
    scheme = artifact_scheme(uri)
    if scheme == "file":
        target = _local_path(uri, root)
        if target.is_dir():
            rows = [{"name": item.name, "path": str(item), "type": "directory" if item.is_dir() else "file", "size": item.stat().st_size if item.is_file() else None} for item in sorted(target.iterdir())]
        elif target.exists():
            rows = [{"name": target.name, "path": str(target), "type": "file", "size": target.stat().st_size}]
        else:
            rows = []
        if json_output:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                print(f"{row['type']:<9} {str(row['size'] or '-'):>12} {row['path']}")
        return 0
    result = _plugin(config, scheme).execute(ArtifactRequest("list", root, uri))
    return _print_result(result, json_output)


def delete_artifact(config: ProjectConfig | None, root: Path, uri: str, *, apply: bool = False, json_output: bool = False) -> int:
    root = root.resolve()
    scheme = artifact_scheme(uri)
    if scheme == "file":
        target = _local_path(uri, root)
        if not target.exists():
            return _print_result(PluginResult(message=f"[SKIP] artifact does not exist: {target}"), json_output)
        if not apply:
            return _print_result(PluginResult(message=f"[DRY-RUN] delete {target}", data={"target": str(target), "dry_run": True}), json_output)
        backup_file(target)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return _print_result(PluginResult(message=f"[OK] artifact deleted: {target}"), json_output)
    result = _plugin(config, scheme).execute(ArtifactRequest("delete", root, uri, apply=apply))
    return _print_result(result, json_output)
