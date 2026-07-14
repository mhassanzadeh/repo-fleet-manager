from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

from jsonschema import Draft202012Validator

from . import __version__
from .compose import compose_cmd
from .config import ProjectConfig, Repository
from .fingerprint import build_metadata
from .images import candidate_image_names
from .shell import RunResult, command_exists, run, shlex_join

PROVENANCE_SCHEMA_VERSION = "1.0.0"
SEVERITIES = ("unknown", "negligible", "low", "medium", "high", "critical")
SEVERITY_RANK = {name: index for index, name in enumerate(SEVERITIES)}
_DIGEST_RE = re.compile(r"sha256:[0-9a-fA-F]{64}")


class SupplyChainError(RuntimeError):
    """Raised when provenance cannot be established safely."""


@dataclass(slots=True)
class ImageResolution:
    service: str
    repo: str | None
    image: str | None
    resolved_reference: str | None
    digest: str | None
    immutable: bool
    resolution_source: str
    source_digest: str | None
    source_git_head: str | None
    image_source_digest: str | None
    image_build_sha: str | None
    source_match: bool
    errors: list[str] = field(default_factory=list)
    sbom: dict[str, Any] | None = None
    scan: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SupplyChainReport:
    project: str
    engine: str | None
    generated_at: str
    services: list[ImageResolution]
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and all(not item.errors for item in self.services)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "tool_version": __version__,
            "project": self.project,
            "engine": self.engine,
            "generated_at": self.generated_at,
            "ok": self.ok,
            "errors": list(self.errors),
            "services": [item.to_dict() for item in self.services],
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._") or "service"


def _supply_config(config: ProjectConfig) -> dict[str, Any]:
    return config.supply_chain or {}


def output_dir(config: ProjectConfig, root: Path, override: str | None = None) -> Path:
    configured = override or _supply_config(config).get("output_dir") or ".repo-fleet/supply-chain"
    path = Path(str(configured)).expanduser()
    return path if path.is_absolute() else root / path


def manifest_path(config: ProjectConfig, root: Path, override: str | None = None) -> Path:
    return output_dir(config, root, override) / "provenance.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _load_provenance_schema() -> dict[str, Any]:
    path = Path(str(files("repo_fleet_manager").joinpath("data/rfm-provenance.schema.json")))
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_manifest(payload: dict[str, Any]) -> None:
    errors = sorted(Draft202012Validator(_load_provenance_schema()).iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(
            f"$.{'.'.join(str(part) for part in error.path)}: {error.message}" if error.path else f"$: {error.message}"
            for error in errors[:8]
        )
        raise SupplyChainError(f"invalid provenance manifest: {details}")


def load_manifest(config: ProjectConfig, root: Path, override: str | None = None) -> dict[str, Any]:
    path = manifest_path(config, root, override)
    if not path.exists():
        raise FileNotFoundError(f"missing provenance manifest: {path}; run `rfm supply-chain resolve --apply`")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SupplyChainError(f"invalid provenance manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SupplyChainError("provenance manifest must be a JSON object")
    _validate_manifest(payload)
    return payload


def _compose_model(config: ProjectConfig, root: Path, runner: Callable[..., RunResult]) -> dict[str, Any]:
    result = runner(compose_cmd(config, root, "config", ["--format", "json"], with_metadata=False), cwd=root)
    if result.code != 0 or not result.stdout.strip():
        return {}
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _service_repo_map(config: ProjectConfig) -> dict[str, Repository]:
    result: dict[str, Repository] = {}
    for repo in config.services():
        result.setdefault(repo.service_name, repo)
    return result


def _source_map(config: ProjectConfig, root: Path) -> dict[str, dict[str, Any]]:
    metadata = build_metadata(config, root)
    return {str(item["name"]): item for item in metadata.get("services", [])}


def _configured_services(config: ProjectConfig) -> dict[str, dict[str, Any]]:
    raw = _supply_config(config).get("services") or {}
    if not isinstance(raw, dict):
        raise SupplyChainError("supply_chain.services must be an object keyed by service name")
    result: dict[str, dict[str, Any]] = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise SupplyChainError(f"supply_chain.services.{name} must be an object")
        result[str(name)] = value
    return result


def _detect_engine(config: ProjectConfig, preferred: str | None) -> str | None:
    if preferred and preferred != "auto":
        return preferred
    configured = str(_supply_config(config).get("engine") or config.compose.get("engine") or "auto").lower()
    if configured in {"docker", "podman"}:
        return configured
    if command_exists("podman"):
        return "podman"
    if command_exists("docker"):
        return "docker"
    return None


def _extract_digest(value: str | None) -> str | None:
    if not value:
        return None
    match = _DIGEST_RE.search(value)
    return match.group(0).lower() if match else None


def _base_image_name(reference: str) -> str:
    return reference.split("@", 1)[0]


def _immutable_reference(reference: str | None, digest: str | None) -> str | None:
    if not reference or not digest:
        return None
    return f"{_base_image_name(reference)}@{digest}"


def _inspect_repo_digests(engine: str, image: str, runner: Callable[..., RunResult]) -> list[str]:
    result = runner([engine, "image", "inspect", image, "--format", "{{json .RepoDigests}}"])
    if result.code != 0 or not result.stdout.strip():
        return []
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        value = [result.stdout.strip()]
    if isinstance(value, list):
        return [str(item) for item in value if _extract_digest(str(item))]
    return []


def _inspect_label(engine: str | None, image: str | None, label: str, runner: Callable[..., RunResult]) -> str | None:
    if not engine or not image:
        return None
    template = '{{ index .Config.Labels "' + label + '" }}'
    result = runner([engine, "image", "inspect", image, "--format", template])
    value = result.stdout.strip() if result.code == 0 else ""
    return value or None


def _skopeo_digest(image: str, runner: Callable[..., RunResult]) -> str | None:
    if not command_exists("skopeo"):
        return None
    result = runner(["skopeo", "inspect", f"docker://{image}"])
    if result.code != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return _extract_digest(str(payload.get("Digest") or "")) if isinstance(payload, dict) else None


def _select_services(all_names: Iterable[str], selected: Iterable[str] | None) -> list[str]:
    names = list(dict.fromkeys(str(item) for item in all_names if str(item)))
    requested = {str(item) for item in selected or [] if str(item)}
    unknown = sorted(requested - set(names))
    if unknown:
        raise SupplyChainError("unknown supply-chain service(s): " + ", ".join(unknown))
    return [name for name in names if not requested or name in requested]


def resolve_supply_chain(
    config: ProjectConfig,
    root: Path,
    *,
    selected: Iterable[str] | None = None,
    engine: str | None = None,
    output_override: str | None = None,
    write: bool = False,
    runner: Callable[..., RunResult] = run,
) -> SupplyChainReport:
    cfg = _supply_config(config)
    service_cfg = _configured_services(config)
    repo_map = _service_repo_map(config)
    source_map = _source_map(config, root)
    compose_model = _compose_model(config, root, runner)
    compose_services = compose_model.get("services") if isinstance(compose_model.get("services"), dict) else {}
    names = _select_services([*compose_services, *repo_map, *service_cfg, *source_map], selected)
    active_engine = _detect_engine(config, engine)
    require_digest = bool(cfg.get("require_immutable_digest", True))
    require_source_label = bool(cfg.get("require_source_label", True))
    resolver = str(cfg.get("digest_resolver") or "auto").lower()
    rows: list[ImageResolution] = []

    for name in names:
        raw = service_cfg.get(name, {})
        repo = repo_map.get(name)
        source = source_map.get(name, {})
        compose_raw = compose_services.get(name) if isinstance(compose_services, dict) else None
        compose_image = compose_raw.get("image") if isinstance(compose_raw, dict) else None
        image_value = raw.get("image") or compose_image or (repo.extra.get("image") if repo else None)
        image = str(image_value) if image_value else None
        expected_digest = _extract_digest(str(raw.get("expected_digest") or ""))
        errors: list[str] = []
        resolution_source = "none"
        digest = _extract_digest(image)
        resolved_reference = image if digest else None

        candidates: list[str] = []
        if image:
            candidates.append(image)
        if repo:
            candidates.extend(candidate_image_names(config, name, repo.repo))
        candidates = list(dict.fromkeys(candidates))

        if not digest and expected_digest:
            digest = expected_digest
            resolved_reference = _immutable_reference(image, digest)
            resolution_source = "config"
        if not digest and resolver in {"auto", "engine"} and active_engine:
            for candidate in candidates:
                repo_digests = _inspect_repo_digests(active_engine, candidate, runner)
                if repo_digests:
                    resolved_reference = repo_digests[0]
                    digest = _extract_digest(resolved_reference)
                    image = image or candidate
                    resolution_source = f"{active_engine}-inspect"
                    break
        if not digest and resolver in {"auto", "skopeo"} and image:
            digest = _skopeo_digest(image, runner)
            if digest:
                resolved_reference = _immutable_reference(image, digest)
                resolution_source = "skopeo"
        if digest and resolution_source == "none":
            resolved_reference = _immutable_reference(image, digest) if image else None
            resolution_source = "reference"

        inspect_target = image or resolved_reference
        image_source_digest = _inspect_label(active_engine, inspect_target, "io.repo-fleet.source-digest", runner)
        image_build_sha = _inspect_label(active_engine, inspect_target, "io.repo-fleet.build-sha", runner)
        source_digest = str(source.get("source_digest") or "") or None
        source_git_head = str(source.get("git_head") or "") or None
        source_match = bool(source_digest and image_source_digest and source_digest == image_source_digest)
        if not source_digest:
            errors.append("source fingerprint is unavailable")
        if require_digest and not digest:
            errors.append("immutable registry digest could not be resolved")
        if require_source_label and not image_source_digest:
            errors.append("image source-digest label is missing")
        elif require_source_label and not source_match:
            errors.append("image source-digest label does not match current source fingerprint")
        rows.append(ImageResolution(
            service=name,
            repo=repo.repo if repo else None,
            image=image,
            resolved_reference=resolved_reference,
            digest=digest,
            immutable=bool(digest and resolved_reference and "@sha256:" in resolved_reference),
            resolution_source=resolution_source,
            source_digest=source_digest,
            source_git_head=source_git_head,
            image_source_digest=image_source_digest,
            image_build_sha=image_build_sha,
            source_match=source_match,
            errors=errors,
        ))

    report = SupplyChainReport(
        project=str(config.project.get("name") or root.name),
        engine=active_engine,
        generated_at=_utc_now(),
        services=rows,
        errors=[] if rows else ["no services were discovered"],
    )
    if write:
        _write_json(manifest_path(config, root, output_override), report.to_dict())
    return report


def _service_rows(payload: dict[str, Any], selected: Iterable[str] | None = None) -> list[dict[str, Any]]:
    rows = [item for item in payload.get("services", []) if isinstance(item, dict)]
    requested = {str(item) for item in selected or [] if str(item)}
    known = {str(item.get("service")) for item in rows}
    unknown = sorted(requested - known)
    if unknown:
        raise SupplyChainError("unknown manifest service(s): " + ", ".join(unknown))
    return [item for item in rows if not requested or str(item.get("service")) in requested]


def generate_sboms(
    config: ProjectConfig,
    root: Path,
    *,
    selected: Iterable[str] | None = None,
    sbom_format: str | None = None,
    output_override: str | None = None,
    allow_mutable: bool = False,
    apply: bool = False,
    json_output: bool = False,
    runner: Callable[..., RunResult] = run,
) -> int:
    payload = load_manifest(config, root, output_override)
    fmt = str(sbom_format or _supply_config(config).get("sbom_format") or "cyclonedx-json")
    rows = _service_rows(payload, selected)
    commands: list[list[str]] = []
    failures: list[str] = []
    out_dir = output_dir(config, root, output_override)
    for item in rows:
        target = str(item.get("resolved_reference") or item.get("image") or "")
        if not target:
            failures.append(f"{item.get('service')}: image reference is unavailable")
            continue
        if "@sha256:" not in target and not allow_mutable:
            failures.append(f"{item.get('service')}: immutable image reference is required")
            continue
        command = ["syft", target, "-o", fmt]
        commands.append(command)
        if not apply:
            continue
        if not command_exists("syft"):
            failures.append("syft is not installed")
            break
        result = runner(command, cwd=root)
        if result.code != 0:
            failures.append(f"{item.get('service')}: syft failed: {result.stderr or result.stdout}")
            continue
        suffix = "cdx.json" if fmt == "cyclonedx-json" else "spdx.json" if fmt == "spdx-json" else "sbom.json"
        relative = Path("sbom") / f"{_safe_name(str(item.get('service')))}.{suffix}"
        path = out_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.stdout.rstrip() + "\n", encoding="utf-8")
        item["sbom"] = {
            "format": fmt,
            "path": relative.as_posix(),
            "sha256": _sha256(path),
            "generated_at": _utc_now(),
            "target": target,
        }
    if apply:
        payload["generated_at"] = _utc_now()
        payload["ok"] = not failures and all(not item.get("errors") for item in payload.get("services", []))
        _write_json(manifest_path(config, root, output_override), payload)
    result_payload = {"applied": apply, "format": fmt, "commands": [shlex_join(cmd) for cmd in commands], "failures": failures}
    if json_output:
        print(json.dumps(result_payload, ensure_ascii=False, indent=2))
    else:
        for command in commands:
            print(("+ " if apply else "[DRY-RUN] ") + shlex_join(command))
        for failure in failures:
            print(f"[ERROR] {failure}")
        if apply and not failures:
            print(f"[OK] SBOM files written under {out_dir / 'sbom'}")
    return 0 if not failures else 2


def _severity_counts(grype_payload: dict[str, Any]) -> dict[str, int]:
    counts = {name: 0 for name in SEVERITIES}
    for match in grype_payload.get("matches") or []:
        if not isinstance(match, dict):
            continue
        vulnerability = match.get("vulnerability") or {}
        severity = str(vulnerability.get("severity") or "unknown").strip().lower()
        counts[severity if severity in counts else "unknown"] += 1
    return counts


def _threshold_failed(counts: dict[str, int], threshold: str) -> bool:
    rank = SEVERITY_RANK[threshold]
    return any(count and SEVERITY_RANK.get(name, 0) >= rank for name, count in counts.items())


def scan_sboms(
    config: ProjectConfig,
    root: Path,
    *,
    selected: Iterable[str] | None = None,
    threshold: str | None = None,
    output_override: str | None = None,
    apply: bool = False,
    json_output: bool = False,
    runner: Callable[..., RunResult] = run,
) -> int:
    payload = load_manifest(config, root, output_override)
    limit = str(threshold or _supply_config(config).get("vulnerability_threshold") or "high").lower()
    if limit not in SEVERITY_RANK:
        raise SupplyChainError(f"unsupported vulnerability threshold: {limit}")
    out_dir = output_dir(config, root, output_override)
    rows = _service_rows(payload, selected)
    commands: list[list[str]] = []
    failures: list[str] = []
    policy_failures: list[str] = []
    for item in rows:
        sbom = item.get("sbom") or {}
        relative = sbom.get("path") if isinstance(sbom, dict) else None
        if not relative:
            failures.append(f"{item.get('service')}: SBOM is missing")
            continue
        try:
            sbom_path = _safe_artifact_path(out_dir, relative)
        except SupplyChainError as exc:
            failures.append(f"{item.get('service')}: {exc}")
            continue
        if not sbom_path.exists():
            failures.append(f"{item.get('service')}: SBOM file is missing: {sbom_path}")
            continue
        command = ["grype", f"sbom:{sbom_path}", "-o", "json"]
        commands.append(command)
        if not apply:
            continue
        if not command_exists("grype"):
            failures.append("grype is not installed")
            break
        result = runner(command, cwd=root)
        if result.code != 0:
            failures.append(f"{item.get('service')}: grype failed: {result.stderr or result.stdout}")
            continue
        try:
            scan_payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            failures.append(f"{item.get('service')}: grype returned invalid JSON: {exc}")
            continue
        relative_report = Path("scans") / f"{_safe_name(str(item.get('service')))}.grype.json"
        report_path = out_dir / relative_report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(scan_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts = _severity_counts(scan_payload)
        passed = not _threshold_failed(counts, limit)
        if not passed:
            policy_failures.append(f"{item.get('service')}: vulnerabilities at or above {limit}")
        item["scan"] = {
            "tool": "grype",
            "path": relative_report.as_posix(),
            "sha256": _sha256(report_path),
            "generated_at": _utc_now(),
            "threshold": limit,
            "counts": counts,
            "passed": passed,
        }
    if apply:
        payload["generated_at"] = _utc_now()
        _write_json(manifest_path(config, root, output_override), payload)
    result_payload = {
        "applied": apply,
        "threshold": limit,
        "commands": [shlex_join(cmd) for cmd in commands],
        "failures": failures,
        "policy_failures": policy_failures,
    }
    if json_output:
        print(json.dumps(result_payload, ensure_ascii=False, indent=2))
    else:
        for command in commands:
            print(("+ " if apply else "[DRY-RUN] ") + shlex_join(command))
        for failure in [*failures, *policy_failures]:
            print(f"[ERROR] {failure}")
        if apply and not failures and not policy_failures:
            print(f"[OK] vulnerability reports written under {out_dir / 'scans'}")
    return 0 if not failures and not policy_failures else 2


def _trust_args(
    config: ProjectConfig,
    overrides: dict[str, str | None],
    service_policy: dict[str, Any] | None = None,
) -> tuple[list[str], str]:
    cosign = dict(_supply_config(config).get("cosign") or {})
    service_cosign = (service_policy or {}).get("cosign") or {}
    if isinstance(service_cosign, dict):
        cosign.update(service_cosign)
    key = overrides.get("key") or cosign.get("key")
    identity = overrides.get("certificate_identity") or cosign.get("certificate_identity")
    issuer = overrides.get("certificate_oidc_issuer") or cosign.get("certificate_oidc_issuer")
    if key:
        return ["--key", str(key)], "key"
    if identity and issuer:
        return ["--certificate-identity", str(identity), "--certificate-oidc-issuer", str(issuer)], "keyless-identity"
    return [], "unconfigured"


def _safe_artifact_path(base: Path, value: Any) -> Path:
    raw = str(value or "")
    relative = PurePosixPath(raw)
    if not raw or relative.is_absolute() or ".." in relative.parts:
        raise SupplyChainError(f"unsafe supply-chain artifact path: {raw!r}")
    candidate = (base / Path(*relative.parts)).resolve()
    resolved_base = base.resolve()
    if candidate != resolved_base and resolved_base not in candidate.parents:
        raise SupplyChainError(f"supply-chain artifact escapes output directory: {raw!r}")
    return candidate


def _verify_checksum(base: Path, metadata: dict[str, Any] | None) -> tuple[bool, str]:
    if not metadata:
        return False, "metadata missing"
    relative = metadata.get("path")
    expected = metadata.get("sha256")
    if not relative or not expected:
        return False, "path or checksum missing"
    try:
        path = _safe_artifact_path(base, relative)
    except SupplyChainError as exc:
        return False, str(exc)
    if not path.exists():
        return False, f"file missing: {path}"
    actual = _sha256(path)
    return actual == expected, "checksum matched" if actual == expected else f"checksum mismatch: expected {expected}, got {actual}"


def verify_supply_chain(
    config: ProjectConfig,
    root: Path,
    *,
    selected: Iterable[str] | None = None,
    output_override: str | None = None,
    threshold: str | None = None,
    require_signature: bool | None = None,
    require_attestation: bool | None = None,
    key: str | None = None,
    certificate_identity: str | None = None,
    certificate_oidc_issuer: str | None = None,
    attestation_type: str | None = None,
    json_output: bool = False,
    runner: Callable[..., RunResult] = run,
) -> int:
    payload = load_manifest(config, root, output_override)
    cfg = _supply_config(config)
    out_dir = output_dir(config, root, output_override)
    limit = str(threshold or cfg.get("vulnerability_threshold") or "high").lower()
    require_digest = bool(cfg.get("require_immutable_digest", True))
    require_source = bool(cfg.get("require_source_label", True))
    require_sbom = bool(cfg.get("require_sbom", True))
    require_scan = bool(cfg.get("require_scan", False))
    default_signature_required = bool(cfg.get("require_signature", False)) if require_signature is None else require_signature
    default_attestation_required = bool(cfg.get("require_attestation", False)) if require_attestation is None else require_attestation
    service_policies = _configured_services(config)
    trust_overrides = {
        "key": key,
        "certificate_identity": certificate_identity,
        "certificate_oidc_issuer": certificate_oidc_issuer,
    }
    rows: list[dict[str, Any]] = []
    overall = True
    policy_summary: dict[str, dict[str, Any]] = {}
    for item in _service_rows(payload, selected):
        checks: list[dict[str, Any]] = []
        target = str(item.get("resolved_reference") or "")
        service_name = str(item.get("service") or "")
        service_policy = service_policies.get(service_name, {})
        signature_required = default_signature_required if require_signature is not None else bool(service_policy.get("require_signature", default_signature_required))
        attestation_required = default_attestation_required if require_attestation is not None else bool(service_policy.get("require_attestation", default_attestation_required))
        trust_args, trust_mode = _trust_args(config, trust_overrides, service_policy)
        policy_summary[service_name] = {
            "require_signature": signature_required,
            "require_attestation": attestation_required,
            "trust_mode": trust_mode,
        }

        def add(name: str, ok: bool, detail: str, required: bool = True) -> None:
            nonlocal overall
            checks.append({"name": name, "ok": ok, "required": required, "detail": detail})
            if required and not ok:
                overall = False

        immutable_ok = bool(item.get("digest") and "@sha256:" in target)
        add("immutable-digest", immutable_ok, target or "immutable reference missing", require_digest)
        source_ok = bool(item.get("source_match"))
        add("source-provenance", source_ok, "source label matched" if source_ok else "source label mismatch or missing", require_source)
        sbom_ok, sbom_detail = _verify_checksum(out_dir, item.get("sbom") if isinstance(item.get("sbom"), dict) else None)
        add("sbom", sbom_ok, sbom_detail, require_sbom)
        scan_ok, scan_detail = _verify_checksum(out_dir, item.get("scan") if isinstance(item.get("scan"), dict) else None)
        if scan_ok:
            scan_data = item.get("scan") or {}
            counts = scan_data.get("counts") or {}
            scan_policy_ok = not _threshold_failed({str(k): int(v) for k, v in counts.items()}, limit)
            scan_detail = f"checksum matched; threshold={limit}; counts={counts}"
            scan_ok = scan_policy_ok
        add("vulnerability-scan", scan_ok, scan_detail, require_scan)

        signature_ok = not signature_required
        signature_detail = "not required"
        attestation_ok = not attestation_required
        attestation_detail = "not required"
        if signature_required or attestation_required:
            if not target or "@sha256:" not in target:
                if signature_required:
                    signature_ok, signature_detail = False, "immutable target is unavailable"
                if attestation_required:
                    attestation_ok, attestation_detail = False, "immutable target is unavailable"
            elif not trust_args:
                if signature_required:
                    signature_ok, signature_detail = False, "cosign trust policy is not configured"
                if attestation_required:
                    attestation_ok, attestation_detail = False, "cosign trust policy is not configured"
            elif not command_exists("cosign"):
                if signature_required:
                    signature_ok, signature_detail = False, "cosign is not installed"
                if attestation_required:
                    attestation_ok, attestation_detail = False, "cosign is not installed"
            else:
                if signature_required:
                    result = runner(["cosign", "verify", *trust_args, target], cwd=root)
                    signature_ok = result.code == 0
                    signature_detail = "signature verified" if signature_ok else (result.stderr or result.stdout or "cosign verify failed")
                if attestation_required:
                    cosign_cfg = dict(cfg.get("cosign") or {})
                    if isinstance(service_policy.get("cosign"), dict):
                        cosign_cfg.update(service_policy["cosign"])
                    predicate = attestation_type or cosign_cfg.get("attestation_type")
                    command = ["cosign", "verify-attestation", *trust_args]
                    if predicate:
                        command += ["--type", str(predicate)]
                    policy = cosign_cfg.get("attestation_policy")
                    if policy:
                        command += ["--policy", str(policy)]
                    command.append(target)
                    result = runner(command, cwd=root)
                    attestation_ok = result.code == 0
                    attestation_detail = "attestation verified" if attestation_ok else (result.stderr or result.stdout or "cosign verify-attestation failed")
        add("signature", signature_ok, f"{signature_detail}; trust={trust_mode}", signature_required)
        add("attestation", attestation_ok, f"{attestation_detail}; trust={trust_mode}", attestation_required)
        rows.append({"service": item.get("service"), "image": target or item.get("image"), "ok": all(check["ok"] or not check["required"] for check in checks), "checks": checks})

    result_payload = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "verified_at": _utc_now(),
        "ok": overall,
        "policy": {
            "require_immutable_digest": require_digest,
            "require_source_label": require_source,
            "require_sbom": require_sbom,
            "require_scan": require_scan,
            "vulnerability_threshold": limit,
            "require_signature": default_signature_required,
            "require_attestation": default_attestation_required,
            "service_overrides": policy_summary,
        },
        "services": rows,
    }
    if json_output:
        print(json.dumps(result_payload, ensure_ascii=False, indent=2))
    else:
        print(f"Supply chain: {'VERIFIED' if overall else 'FAILED'} threshold={limit}")
        for row in rows:
            print(f" - [{'OK' if row['ok'] else 'FAIL'}] {row['service']} image={row['image'] or '-'}")
            for check in row["checks"]:
                marker = "OK" if check["ok"] else ("WARN" if not check["required"] else "FAIL")
                print(f"     [{marker:<4}] {check['name']}: {check['detail']}")
    return 0 if overall else 2


def report_supply_chain(
    config: ProjectConfig,
    root: Path,
    *,
    selected: Iterable[str] | None = None,
    output_override: str | None = None,
    json_output: bool = False,
) -> int:
    payload = load_manifest(config, root, output_override)
    rows = _service_rows(payload, selected)
    if json_output:
        print(json.dumps({**payload, "services": rows}, ensure_ascii=False, indent=2))
    else:
        print(f"project: {payload.get('project')} generated={payload.get('generated_at')} engine={payload.get('engine')}")
        print("SERVICE                  DIGEST        SOURCE     SBOM   SCAN   IMAGE")
        print("-" * 100)
        for item in rows:
            digest = str(item.get("digest") or "-")
            digest_short = digest[:19] if digest != "-" else "-"
            source = "MATCH" if item.get("source_match") else "FAIL"
            sbom = "YES" if item.get("sbom") else "NO"
            scan = "PASS" if (item.get("scan") or {}).get("passed") else "NO/FAIL"
            print(f"{str(item.get('service')):<24} {digest_short:<19} {source:<10} {sbom:<6} {scan:<7} {item.get('resolved_reference') or item.get('image') or '-'}")
    return 0


def collect_supply_chain(
    config: ProjectConfig,
    root: Path,
    *,
    selected: Iterable[str] | None = None,
    engine: str | None = None,
    sbom_format: str | None = None,
    threshold: str | None = None,
    output_override: str | None = None,
    allow_mutable: bool = False,
    apply: bool = False,
    json_output: bool = False,
    runner: Callable[..., RunResult] = run,
) -> int:
    report = resolve_supply_chain(
        config, root, selected=selected, engine=engine, output_override=output_override,
        write=apply, runner=runner,
    )
    if not apply:
        commands: list[str] = []
        fmt = str(sbom_format or _supply_config(config).get("sbom_format") or "cyclonedx-json")
        for item in report.services:
            target = item.resolved_reference or item.image
            if target:
                commands.append(shlex_join(["syft", target, "-o", fmt]))
                commands.append(f"grype sbom:<generated-for-{item.service}> -o json")
        payload = {"applied": False, "resolution": report.to_dict(), "commands": commands}
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("[DRY-RUN] resolve immutable image digests and source labels")
            for command in commands:
                print(f"[DRY-RUN] {command}")
        return 0 if report.services else 2
    if not report.ok:
        if json_output:
            print(json.dumps({"applied": True, "resolution": report.to_dict(), "stopped": "resolution-failed"}, ensure_ascii=False, indent=2))
        else:
            for item in report.services:
                for error in item.errors:
                    print(f"[ERROR] {item.service}: {error}")
            for error in report.errors:
                print(f"[ERROR] {error}")
        return 2
    sbom_code = generate_sboms(
        config, root, selected=selected, sbom_format=sbom_format, output_override=output_override,
        allow_mutable=allow_mutable, apply=True, json_output=json_output, runner=runner,
    )
    if sbom_code != 0:
        return sbom_code
    return scan_sboms(
        config, root, selected=selected, threshold=threshold, output_override=output_override,
        apply=True, json_output=json_output, runner=runner,
    )
