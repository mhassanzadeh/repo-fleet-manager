from __future__ import annotations

import json
from pathlib import Path

from .config import ProjectConfig
from .shell import command_exists, run


def detect_container_cli(preferred: str | None = None) -> str:
    if preferred:
        return preferred
    if command_exists("podman"):
        return "podman"
    if command_exists("docker"):
        return "docker"
    raise RuntimeError("Neither podman nor docker was found.")


def inspect_label(engine: str, object_type: str, object_name: str, label: str) -> str:
    template = '{{ index .Config.Labels "' + label + '" }}'
    result = run([engine, object_type, "inspect", object_name, "--format", template])
    return result.stdout if result.code == 0 else ""


def candidate_image_names(config: ProjectConfig, service_name: str, repo_name: str) -> list[str]:
    compose_project = str(config.compose.get("project_name") or Path.cwd().name)
    return [
        f"localhost/{compose_project}_{service_name}:latest",
        f"{compose_project}_{service_name}:latest",
        f"{compose_project}-{service_name}:latest",
        f"{repo_name}:latest",
        f"localhost/{repo_name}:latest",
    ]


def verify_images(config: ProjectConfig, root: Path, json_output: bool = False) -> int:
    build_dir = root / str(config.project.get("build_dir", ".repo-fleet/build"))
    metadata_path = build_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError("missing metadata.json; run `rfm source fingerprint --write` first")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    engine = detect_container_cli(config.compose.get("container_cli"))
    rows = []
    failed = False
    for service in metadata["services"]:
        expected = service["source_digest"]
        image_digest = ""
        image_name = ""
        for candidate in candidate_image_names(config, service["name"], service["repo"]):
            image_digest = inspect_label(engine, "image", candidate, "io.repo-fleet.source-digest")
            if image_digest:
                image_name = candidate
                break
        ok = image_digest == expected
        failed = failed or not ok
        rows.append({"service": service["name"], "expected": expected, "image": image_name or None, "image_digest": image_digest or None, "ok": ok})
    if json_output:
        print(json.dumps({"engine": engine, "rows": rows, "ok": not failed}, indent=2, ensure_ascii=False))
    else:
        print(f"engine: {engine}")
        print("SERVICE                         EXPECTED          IMAGE DIGEST      STATUS")
        print("-" * 86)
        for row in rows:
            status = "OK" if row["ok"] else "MISMATCH/MISSING"
            print(f"{row['service']:<31} {row['expected']:<17} {row['image_digest'] or '-':<17} {status}")
    return 1 if failed else 0
