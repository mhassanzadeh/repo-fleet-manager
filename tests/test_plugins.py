from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from repo_fleet_manager.artifacts import get_artifact, put_artifact
from repo_fleet_manager.config import load_config
from repo_fleet_manager.gitops import create_repositories
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
from repo_fleet_manager.plugins import PluginRegistry
from repo_fleet_manager.runtime import runtime_status
from repo_fleet_manager.service_catalog import render_catalog


class FakeDist:
    name = "rfm-demo-plugin"
    version = "1.2.3"


class FakeEntryPoint:
    def __init__(self, group: str, name: str, value, target: object) -> None:
        self.group = group
        self.name = name
        self.value = value
        self._target = target
        self.dist = FakeDist()

    def load(self):
        return self._target


class DemoCatalog(CatalogExporterPluginV1):
    name = "demo-catalog"
    version = "1.0.0"
    formats = ("yaml", "demo-yaml")

    def render(self, request: CatalogExportRequest) -> str:
        return f"view: {request.view}\nproject: {request.catalog['project']['name']}\n"


class IncompatibleCatalog(DemoCatalog):
    api_version = "2.0"


class DemoRuntime(RuntimePluginV1):
    name = "demo-runtime"
    version = "1.0.0"
    aliases = ("demo-runtime",)

    def execute(self, request: RuntimeRequest) -> PluginResult:
        return PluginResult(data={
            "ready": True,
            "engine": "demo",
            "services": [{
                "name": "api", "required": True, "depends_on": [], "state": "running",
                "running": True, "ready": True, "readiness_source": "plugin:demo-runtime",
            }],
        })


class DemoProvider(ProviderPluginV1):
    name = "demo-provider"
    version = "1.0.0"
    aliases = ("demo-provider",)
    calls: list[str] = []

    def execute(self, request: ProviderRequest) -> PluginResult:
        type(self).calls.append(request.operation)
        if request.operation == "auth-status":
            return PluginResult(data={"authenticated": True, "active_user": "demo", "scopes_known": True})
        if request.operation == "repository-get":
            return PluginResult(code=1, message="not found")
        return PluginResult(message=f"[PLUGIN] {request.operation} {request.repository['repo'] if request.repository else ''}")


class MemoryArtifact(ArtifactBackendPluginV1):
    name = "memory-artifact"
    version = "1.0.0"
    schemes = ("memory",)
    storage: dict[str, bytes] = {}

    def execute(self, request: ArtifactRequest) -> PluginResult:
        if request.operation == "put":
            assert request.source is not None
            if request.apply:
                type(self).storage[request.uri] = request.source.read_bytes()
            return PluginResult(message="stored")
        if request.operation == "get":
            assert request.destination is not None
            if request.apply:
                request.destination.parent.mkdir(parents=True, exist_ok=True)
                request.destination.write_bytes(type(self).storage[request.uri])
            return PluginResult(message="restored")
        if request.operation == "list":
            return PluginResult(data={"items": sorted(type(self).storage)})
        if request.operation == "delete":
            if request.apply:
                type(self).storage.pop(request.uri, None)
            return PluginResult(message="deleted")
        return PluginResult(code=2, message="unsupported")


def ep_for(kind: str, name: str, target: object) -> FakeEntryPoint:
    groups = {
        "provider": "repo_fleet_manager.providers",
        "runtime": "repo_fleet_manager.runtimes",
        "catalog-exporter": "repo_fleet_manager.catalog_exporters",
        "artifact-backend": "repo_fleet_manager.artifact_backends",
    }
    return FakeEntryPoint(groups[kind], name, f"tests:{name}", target)


class PluginRegistryTest(unittest.TestCase):
    def test_compatible_plugin_loads_and_incompatible_is_isolated(self):
        entries = {
            "repo_fleet_manager.catalog_exporters": [
                ep_for("catalog-exporter", "demo", DemoCatalog),
                ep_for("catalog-exporter", "future", IncompatibleCatalog),
            ]
        }
        with patch("repo_fleet_manager.plugins._entry_points_for", side_effect=lambda group: entries.get(group, [])):
            rows = PluginRegistry().records(load=True, kind="catalog-exporter")
        demo = next(row for row in rows if row.name == "demo")
        future = next(row for row in rows if row.name == "future")
        self.assertTrue(demo.loaded)
        self.assertIn("yaml", demo.aliases)
        self.assertFalse(future.loaded)
        self.assertIn("incompatible", future.error)


    def test_alias_conflict_is_isolated(self):
        class OtherCatalog(DemoCatalog):
            name = "other"
            formats = ("yaml",)
        entries = {"repo_fleet_manager.catalog_exporters": [
            ep_for("catalog-exporter", "demo", DemoCatalog),
            ep_for("catalog-exporter", "other", OtherCatalog),
        ]}
        with patch("repo_fleet_manager.plugins._entry_points_for", side_effect=lambda group: entries.get(group, [])):
            rows = PluginRegistry().records(load=True, kind="catalog-exporter")
        external = [row for row in rows if not row.builtin]
        self.assertTrue(all(row.error and "alias conflict" in row.error for row in external))

    def test_catalog_exporter_is_used_for_unknown_format(self):
        entries = {"repo_fleet_manager.catalog_exporters": [ep_for("catalog-exporter", "demo", DemoCatalog)]}
        catalog = {"project": {"name": "Fleet"}, "domains": [], "gaps": [], "catalog_version": "test"}
        with patch("repo_fleet_manager.plugins._entry_points_for", side_effect=lambda group: entries.get(group, [])):
            text = render_catalog(catalog, Path.cwd(), "summary", "yaml")
        self.assertEqual(text, "view: summary\nproject: Fleet\n")

    def test_runtime_driver_delegates_to_plugin(self):
        entries = {"repo_fleet_manager.runtimes": [ep_for("runtime", "demo-runtime", DemoRuntime)]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "repo-fleet.json"
            config_path.write_text(json.dumps({
                "schema_version": "1.0.0",
                "project": {"name": "demo", "default_provider": "local", "default_branch": "main"},
                "providers": {"local": {"type": "local", "driver": "local", "url_template": "file://{root}/.repo-fleet/remotes/{repo}.git"}},
                "repositories": [{"path": ".", "repo": "demo", "kind": "root", "branch": "main"}],
                "runtime": {"driver": "demo-runtime"},
            }), encoding="utf-8")
            cfg = load_config(config_path)
            with patch("repo_fleet_manager.plugins._entry_points_for", side_effect=lambda group: entries.get(group, [])):
                report = runtime_status(cfg, root)
        self.assertTrue(report.ready)
        self.assertEqual(report.engine, "demo")
        self.assertEqual(report.services[0].readiness_source, "plugin:demo-runtime")

    def test_provider_create_delegates_to_plugin(self):
        DemoProvider.calls.clear()
        entries = {"repo_fleet_manager.providers": [ep_for("provider", "demo-provider", DemoProvider)]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "repo-fleet.json"
            config_path.write_text(json.dumps({
                "schema_version": "1.0.0",
                "project": {"name": "demo", "default_provider": "demo", "default_branch": "main"},
                "providers": {"demo": {"type": "remote", "driver": "demo-provider", "namespace": "team", "cli": "demo", "url_template": "ssh://example/{namespace}/{repo}.git"}},
                "repositories": [{"path": ".", "repo": "demo", "kind": "root", "branch": "main"}],
            }), encoding="utf-8")
            cfg = load_config(config_path)
            output = StringIO()
            with patch("repo_fleet_manager.plugins._entry_points_for", side_effect=lambda group: entries.get(group, [])), redirect_stdout(output):
                code = create_repositories(cfg, root, None, None, "private", False)
        self.assertEqual(code, 0)
        self.assertIn("create", DemoProvider.calls)
        self.assertIn("[PLUGIN] create demo", output.getvalue())


    def test_doctor_report_matches_schema(self):
        schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "rfm-plugin-report.schema.json").read_text(encoding="utf-8"))
        report = PluginRegistry().doctor()
        Draft202012Validator(schema).validate(report)
        self.assertEqual(report["api_version"], "1.0")

    def test_artifact_backend_put_and_get(self):
        MemoryArtifact.storage.clear()
        entries = {"repo_fleet_manager.artifact_backends": [ep_for("artifact-backend", "memory", MemoryArtifact)]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            source.write_text("payload", encoding="utf-8")
            destination = root / "restored.txt"
            with patch("repo_fleet_manager.plugins._entry_points_for", side_effect=lambda group: entries.get(group, [])):
                self.assertEqual(put_artifact(None, root, str(source), "memory://bucket/item", apply=True), 0)
                self.assertEqual(get_artifact(None, root, "memory://bucket/item", str(destination), apply=True), 0)
            self.assertEqual(destination.read_text(encoding="utf-8"), "payload")


if __name__ == "__main__":
    unittest.main()
