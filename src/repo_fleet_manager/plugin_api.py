"""Public, versioned extension contracts for Repo Fleet Manager plugins.

Plugin packages should depend only on this module, not on RFM internal modules.  The
contracts intentionally use immutable dataclasses and JSON-compatible mappings so that
minor core releases can evolve without forcing plugin rewrites.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

PLUGIN_API_VERSION = "1.0"
PLUGIN_API_MAJOR = 1

ENTRY_POINT_GROUPS: Mapping[str, str] = {
    "provider": "repo_fleet_manager.providers",
    "runtime": "repo_fleet_manager.runtimes",
    "catalog-exporter": "repo_fleet_manager.catalog_exporters",
    "artifact-backend": "repo_fleet_manager.artifact_backends",
}
SUPPORTED_PLUGIN_KINDS = tuple(ENTRY_POINT_GROUPS)


@dataclass(frozen=True, slots=True)
class PluginResult:
    """Normalized result returned by provider/runtime/artifact plugins."""

    code: int = 0
    message: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    operation: str
    root: Path
    provider: Mapping[str, Any]
    repository: Mapping[str, Any] | None = None
    project: Mapping[str, Any] = field(default_factory=dict)
    apply: bool = False
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeRequest:
    operation: str
    root: Path
    config: Mapping[str, Any]
    selected_services: tuple[str, ...] = ()
    apply: bool = False
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CatalogExportRequest:
    root: Path
    catalog: Mapping[str, Any]
    view: str
    output_format: str
    priority: str | None = None
    status: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactRequest:
    operation: str
    root: Path
    uri: str
    source: Path | None = None
    destination: Path | None = None
    apply: bool = False
    options: Mapping[str, Any] = field(default_factory=dict)


class RFMPluginV1(ABC):
    """Base metadata contract shared by every v1 plugin."""

    api_version = PLUGIN_API_VERSION
    name = ""
    version = "0.0.0"
    description = ""

    def capabilities(self) -> Mapping[str, Any]:
        return {}

    def health(self) -> PluginResult:
        return PluginResult(message="plugin loaded")


class ProviderPluginV1(RFMPluginV1):
    """Provider extension contract.

    ``aliases`` contains provider ``driver`` values handled by this plugin.  The single
    execute entry point keeps the v1 ABI small while allowing new provider operations to
    be introduced through ``request.operation`` and ``request.options``.
    """

    aliases: Sequence[str] = ()

    @abstractmethod
    def execute(self, request: ProviderRequest) -> PluginResult:
        raise NotImplementedError


class RuntimePluginV1(RFMPluginV1):
    """Runtime driver contract used by ``rfm runtime``."""

    aliases: Sequence[str] = ()

    @abstractmethod
    def execute(self, request: RuntimeRequest) -> PluginResult:
        raise NotImplementedError


class CatalogExporterPluginV1(RFMPluginV1):
    """Catalog exporter contract for additional ``rfm catalog --format`` values."""

    formats: Sequence[str] = ()

    @abstractmethod
    def render(self, request: CatalogExportRequest) -> str | bytes:
        raise NotImplementedError


class ArtifactBackendPluginV1(RFMPluginV1):
    """Artifact storage contract selected by URI scheme."""

    schemes: Sequence[str] = ()

    @abstractmethod
    def execute(self, request: ArtifactRequest) -> PluginResult:
        raise NotImplementedError
