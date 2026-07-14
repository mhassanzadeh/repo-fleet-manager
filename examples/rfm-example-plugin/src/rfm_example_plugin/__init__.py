from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path
from urllib.parse import urlparse

from repo_fleet_manager.plugin_api import (
    ArtifactBackendPluginV1,
    ArtifactRequest,
    CatalogExportRequest,
    CatalogExporterPluginV1,
    PluginResult,
    ProviderPluginV1,
    ProviderRequest,
    RuntimePluginV1,
    RuntimeRequest,
)


class ExampleProvider(ProviderPluginV1):
    name = "example-forge"
    version = "0.1.0"
    description = "Non-destructive reference provider plugin"
    aliases = ("example-forge",)

    def capabilities(self):
        return {"operations": ["auth-status", "repository-get", "create", "fork", "reconcile"]}

    def execute(self, request: ProviderRequest) -> PluginResult:
        if request.operation == "auth-status":
            return PluginResult(data={"authenticated": True, "active_user": "example", "scopes_known": True})
        if request.operation == "repository-get":
            return PluginResult(code=1, message="example remote is not materialized")
        repo = (request.repository or {}).get("repo", "repository")
        mode = "apply" if request.apply else "dry-run"
        return PluginResult(message=f"[EXAMPLE:{mode}] {request.operation} {repo}")


class ExampleRuntime(RuntimePluginV1):
    name = "example-runtime"
    version = "0.1.0"
    description = "Reference runtime returning a deterministic ready service"
    aliases = ("example-runtime",)

    def execute(self, request: RuntimeRequest) -> PluginResult:
        services = request.selected_services or ("example",)
        return PluginResult(data={
            "ready": True,
            "engine": "example-runtime",
            "services": [
                {"name": name, "required": True, "depends_on": [], "state": "running", "running": True,
                 "ready": True, "readiness_source": "plugin:example-runtime"}
                for name in services
            ],
        })


class ExampleCatalogExporter(CatalogExporterPluginV1):
    name = "example-csv"
    version = "0.1.0"
    description = "CSV service-catalog exporter"
    formats = ("csv",)

    def render(self, request: CatalogExportRequest) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["view", "project", "catalog_version"])
        writer.writerow([request.view, request.catalog.get("project", {}).get("name", ""), request.catalog.get("catalog_version", "")])
        return output.getvalue()


class ExampleArtifactBackend(ArtifactBackendPluginV1):
    name = "example-store"
    version = "0.1.0"
    description = "Example URI backend stored below .repo-fleet/example-artifacts"
    schemes = ("example",)

    @staticmethod
    def _path(request: ArtifactRequest) -> Path:
        parsed = urlparse(request.uri)
        relative = Path(parsed.netloc) / parsed.path.lstrip("/")
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe example artifact URI")
        return request.root / ".repo-fleet" / "example-artifacts" / relative

    def execute(self, request: ArtifactRequest) -> PluginResult:
        target = self._path(request)
        if request.operation == "put":
            if request.apply:
                assert request.source is not None
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(request.source, target)
            return PluginResult(message=f"example artifact stored at {target}")
        if request.operation == "get":
            if request.apply:
                assert request.destination is not None
                request.destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, request.destination)
            return PluginResult(message=f"example artifact restored from {target}")
        if request.operation == "list":
            base = target if target.is_dir() else target.parent
            return PluginResult(data={"items": [str(item) for item in sorted(base.glob("*"))] if base.exists() else []})
        if request.operation == "delete":
            if request.apply and target.exists():
                target.unlink()
            return PluginResult(message=f"example artifact deleted: {target}")
        return PluginResult(code=2, message=f"unsupported artifact operation: {request.operation}")
