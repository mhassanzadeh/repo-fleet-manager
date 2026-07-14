from __future__ import annotations

import inspect
import json
import os
from dataclasses import asdict, dataclass, field
from importlib import metadata
from typing import Any, Iterable, Mapping

from .plugin_api import (
    ENTRY_POINT_GROUPS,
    PLUGIN_API_MAJOR,
    PLUGIN_API_VERSION,
    SUPPORTED_PLUGIN_KINDS,
    ArtifactBackendPluginV1,
    CatalogExporterPluginV1,
    ProviderPluginV1,
    RFMPluginV1,
    RuntimePluginV1,
)


class PluginError(RuntimeError):
    pass


class PluginCompatibilityError(PluginError):
    pass


class PluginLoadError(PluginError):
    pass


@dataclass(slots=True)
class PluginRecord:
    kind: str
    name: str
    entry_point: str
    distribution: str | None = None
    distribution_version: str | None = None
    builtin: bool = False
    loaded: bool = False
    compatible: bool | None = None
    api_version: str | None = None
    plugin_version: str | None = None
    description: str | None = None
    aliases: list[str] = field(default_factory=list)
    capabilities: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    plugin: RFMPluginV1 | None = field(default=None, repr=False)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("plugin", None)
        return payload


_BUILTINS: tuple[PluginRecord, ...] = (
    PluginRecord("provider", "local", "builtin:local", builtin=True, loaded=True, compatible=True, api_version=PLUGIN_API_VERSION, plugin_version="core", description="Local file:// bare repositories", aliases=["local"]),
    PluginRecord("provider", "github", "builtin:github", builtin=True, loaded=True, compatible=True, api_version=PLUGIN_API_VERSION, plugin_version="core", description="GitHub provider through gh", aliases=["github"]),
    PluginRecord("provider", "gitlab", "builtin:gitlab", builtin=True, loaded=True, compatible=True, api_version=PLUGIN_API_VERSION, plugin_version="core", description="GitLab provider through glab", aliases=["gitlab"]),
    PluginRecord("runtime", "compose", "builtin:compose", builtin=True, loaded=True, compatible=True, api_version=PLUGIN_API_VERSION, plugin_version="core", description="Docker/Podman Compose runtime", aliases=["compose", "auto", "docker", "podman"]),
    PluginRecord("catalog-exporter", "core-catalog", "builtin:catalog", builtin=True, loaded=True, compatible=True, api_version=PLUGIN_API_VERSION, plugin_version="core", description="Text, JSON and Markdown catalog exporters", aliases=["text", "json", "markdown"]),
    PluginRecord("artifact-backend", "file", "builtin:file", builtin=True, loaded=True, compatible=True, api_version=PLUGIN_API_VERSION, plugin_version="core", description="Local filesystem artifact backend", aliases=["file"]),
)


def _major(value: str) -> int:
    try:
        return int(str(value).split(".", 1)[0])
    except (TypeError, ValueError) as exc:
        raise PluginCompatibilityError(f"invalid plugin api_version: {value!r}") from exc


def _entry_points_for(group: str) -> list[Any]:
    points = metadata.entry_points()
    if hasattr(points, "select"):
        return list(points.select(group=group))
    return list(points.get(group, []))  # type: ignore[union-attr]


def _distribution_details(entry_point: Any) -> tuple[str | None, str | None]:
    dist = getattr(entry_point, "dist", None)
    if dist is None:
        return None, None
    name = getattr(dist, "name", None)
    version = getattr(dist, "version", None)
    if not name:
        try:
            name = dist.metadata["Name"]
        except Exception:  # noqa: BLE001
            name = None
    return str(name) if name else None, str(version) if version else None


def _coerce_plugin(value: Any) -> RFMPluginV1:
    candidate = value
    if inspect.isclass(candidate):
        candidate = candidate()
    elif callable(candidate) and not isinstance(candidate, RFMPluginV1):
        candidate = candidate()
    if not isinstance(candidate, RFMPluginV1):
        raise PluginLoadError(
            "entry point must expose an instance, class or zero-argument factory derived from RFMPluginV1"
        )
    return candidate


def _validate_kind(kind: str, plugin: RFMPluginV1) -> None:
    expected = {
        "provider": ProviderPluginV1,
        "runtime": RuntimePluginV1,
        "catalog-exporter": CatalogExporterPluginV1,
        "artifact-backend": ArtifactBackendPluginV1,
    }[kind]
    if not isinstance(plugin, expected):
        raise PluginLoadError(f"plugin does not implement {expected.__name__}")


def _aliases(kind: str, plugin: RFMPluginV1, entry_name: str) -> list[str]:
    if kind in {"provider", "runtime"}:
        raw = getattr(plugin, "aliases", ())
    elif kind == "catalog-exporter":
        raw = getattr(plugin, "formats", ())
    else:
        raw = getattr(plugin, "schemes", ())
    aliases = [str(item).strip().lower() for item in raw if str(item).strip()]
    if entry_name.lower() not in aliases:
        aliases.insert(0, entry_name.lower())
    return list(dict.fromkeys(aliases))


class PluginRegistry:
    def __init__(self, plugin_config: Mapping[str, Any] | None = None) -> None:
        cfg = dict(plugin_config or {})
        self.enabled = bool(cfg.get("enabled", True)) and not bool(os.environ.get("RFM_DISABLE_PLUGINS"))
        self.strict = bool(cfg.get("strict", False))
        self.allow = {str(item) for item in cfg.get("allow", [])}
        self.deny = {str(item) for item in cfg.get("deny", [])}
        self.settings = dict(cfg.get("settings") or {})
        self._records: list[PluginRecord] | None = None

    def _allowed(self, name: str) -> bool:
        if name in self.deny:
            return False
        return not self.allow or name in self.allow

    def discover(self, *, load: bool = False, kinds: Iterable[str] | None = None) -> list[PluginRecord]:
        selected = set(kinds or SUPPORTED_PLUGIN_KINDS)
        unknown = selected - set(SUPPORTED_PLUGIN_KINDS)
        if unknown:
            raise PluginError(f"unknown plugin kind(s): {', '.join(sorted(unknown))}")
        records = [PluginRecord(**{k: v for k, v in item.as_dict().items() if k != "plugin"}) for item in _BUILTINS if item.kind in selected]
        if not self.enabled:
            self._records = records
            return records
        seen: set[tuple[str, str]] = {(item.kind, item.name) for item in records}
        for kind in selected:
            group = ENTRY_POINT_GROUPS[kind]
            for ep in _entry_points_for(group):
                name = str(ep.name)
                dist_name, dist_version = _distribution_details(ep)
                record = PluginRecord(kind, name, f"{ep.group}:{ep.name}={ep.value}", dist_name, dist_version)
                if not self._allowed(name):
                    record.error = "disabled by plugins.allow/deny policy"
                    records.append(record)
                    continue
                key = (kind, name)
                if key in seen:
                    record.error = f"duplicate plugin name for kind {kind}: {name}"
                    records.append(record)
                    continue
                seen.add(key)
                if load:
                    try:
                        plugin = _coerce_plugin(ep.load())
                        _validate_kind(kind, plugin)
                        api_version = str(getattr(plugin, "api_version", ""))
                        compatible = _major(api_version) == PLUGIN_API_MAJOR
                        if not compatible:
                            raise PluginCompatibilityError(
                                f"plugin API {api_version!r} is incompatible with core API {PLUGIN_API_VERSION}"
                            )
                        plugin_name = str(getattr(plugin, "name", "") or name)
                        record.loaded = True
                        record.compatible = True
                        record.api_version = api_version
                        record.plugin_version = str(getattr(plugin, "version", "0.0.0"))
                        record.description = str(getattr(plugin, "description", "") or "")
                        record.aliases = _aliases(kind, plugin, name)
                        record.capabilities = dict(plugin.capabilities() or {})
                        record.plugin = plugin
                        if plugin_name != name:
                            record.capabilities.setdefault("declared_name", plugin_name)
                    except Exception as exc:  # noqa: BLE001
                        record.loaded = False
                        record.compatible = False if isinstance(exc, PluginCompatibilityError) else None
                        record.error = f"{type(exc).__name__}: {exc}"
                records.append(record)
        # Reject ambiguous aliases deterministically. Built-in selectors are reserved.
        alias_owners: dict[tuple[str, str], PluginRecord] = {}
        for record in records:
            if not (record.builtin or record.plugin):
                continue
            for alias in record.aliases:
                key = (record.kind, alias)
                previous = alias_owners.get(key)
                if previous is None:
                    alias_owners[key] = record
                    continue
                if previous is record:
                    continue
                message = f"alias conflict for {record.kind} selector {alias!r}: {previous.name}, {record.name}"
                if not previous.builtin:
                    previous.error = message
                    previous.plugin = None
                    previous.loaded = False
                record.error = message
                record.plugin = None
                record.loaded = False
        self._records = records
        return records

    def records(self, *, load: bool = True, kind: str | None = None) -> list[PluginRecord]:
        records = self.discover(load=load, kinds=[kind] if kind else None)
        if self.strict:
            failures = [item for item in records if not item.builtin and item.error and "disabled by" not in item.error]
            if failures:
                raise PluginLoadError("; ".join(f"{item.kind}/{item.name}: {item.error}" for item in failures))
        return records

    def resolve(self, kind: str, selector: str) -> RFMPluginV1 | None:
        normalized = selector.strip().lower()
        for record in self.records(load=True, kind=kind):
            if record.builtin:
                continue
            if record.plugin and normalized in record.aliases:
                return record.plugin
        return None

    def setting(self, plugin_name: str) -> Mapping[str, Any]:
        value = self.settings.get(plugin_name) or {}
        return value if isinstance(value, Mapping) else {}

    def doctor(self) -> dict[str, Any]:
        records = self.records(load=True)
        failures = [item for item in records if not item.builtin and item.error and "disabled by" not in item.error]
        return {
            "api_version": PLUGIN_API_VERSION,
            "enabled": self.enabled,
            "strict": self.strict,
            "plugin_count": len([item for item in records if not item.builtin]),
            "healthy": not failures,
            "records": [item.as_dict() for item in records],
        }


def registry_for(config: Any | None = None) -> PluginRegistry:
    plugin_cfg = getattr(config, "plugins", None) if config is not None else None
    return PluginRegistry(plugin_cfg)


def resolve_plugin(kind: str, selector: str, config: Any | None = None) -> RFMPluginV1 | None:
    return registry_for(config).resolve(kind, selector)


def print_plugin_records(records: list[PluginRecord], *, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps([item.as_dict() for item in records], ensure_ascii=False, indent=2))
        return
    for item in records:
        source = "builtin" if item.builtin else (item.distribution or "installed")
        status = "OK" if item.builtin or (item.loaded and not item.error) else "WARN" if item.error else "DISCOVERED"
        aliases = ",".join(item.aliases) or "-"
        print(f"[{status}] {item.kind:<18} {item.name:<24} source={source} aliases={aliases}")
        if item.description:
            print(f"     {item.description}")
        if item.error:
            print(f"     error={item.error}")
