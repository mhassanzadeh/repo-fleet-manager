from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from typing import Any


class ConfigResolutionError(ValueError):
    """Raised when profiles, overlays, or repository groups cannot be resolved."""


def normalize_names(values: str | Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        source = [values]
    else:
        source = list(values)
    result: list[str] = []
    seen: set[str] = set()
    for item in source:
        for part in str(item).split(","):
            name = part.strip()
            if name and name not in seen:
                result.append(name)
                seen.add(name)
    return tuple(result)


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, Mapping) and isinstance(overlay, Mapping):
        result = copy.deepcopy(dict(base))
        for key, value in overlay.items():
            if key in result:
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result
    return copy.deepcopy(overlay)


def _resolve_profile(
    profiles: Mapping[str, Any],
    name: str,
    *,
    stack: tuple[str, ...] = (),
    cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cache = cache if cache is not None else {}
    if name in cache:
        return copy.deepcopy(cache[name])
    if name in stack:
        cycle = " -> ".join((*stack, name))
        raise ConfigResolutionError(f"profile inheritance cycle: {cycle}")
    if name not in profiles:
        raise ConfigResolutionError(f"unknown profile: {name}")
    raw = profiles[name]
    if not isinstance(raw, Mapping):
        raise ConfigResolutionError(f"profile {name!r} must be an object")

    result: dict[str, Any] = {}
    parents = normalize_names(raw.get("extends"))
    for parent in parents:
        result = _deep_merge(result, _resolve_profile(profiles, parent, stack=(*stack, name), cache=cache))
    own = {key: value for key, value in raw.items() if key != "extends"}
    result = _deep_merge(result, own)
    cache[name] = copy.deepcopy(result)
    return result


def _repository_matches(item: Mapping[str, Any], selector: str) -> bool:
    return selector in {str(item.get("path") or ""), str(item.get("repo") or "")}


def _apply_repository_overlays(
    repositories: list[dict[str, Any]],
    overlays: Mapping[str, Any],
    profile_name: str,
    changes: list[str],
) -> list[dict[str, Any]]:
    result = copy.deepcopy(repositories)
    for selector, raw_patch in overlays.items():
        if not isinstance(raw_patch, Mapping):
            raise ConfigResolutionError(
                f"profile {profile_name!r} repository overlay {selector!r} must be an object"
            )
        patch = copy.deepcopy(dict(raw_patch))
        enabled = bool(patch.pop("enabled", True))
        matches = [index for index, item in enumerate(result) if _repository_matches(item, str(selector))]
        if not matches:
            if enabled and patch.get("path") and patch.get("repo"):
                result.append(patch)
                changes.append(f"profile {profile_name}: added repository {patch['repo']}")
                continue
            raise ConfigResolutionError(
                f"profile {profile_name!r} references unknown repository selector: {selector}"
            )
        if not enabled:
            removed = [result[index].get("repo") or result[index].get("path") for index in matches]
            result = [item for index, item in enumerate(result) if index not in set(matches)]
            changes.append(f"profile {profile_name}: disabled repositories {', '.join(map(str, removed))}")
            continue
        for index in matches:
            result[index] = _deep_merge(result[index], patch)
            changes.append(f"profile {profile_name}: overlaid repository {selector}")
    return result


def _apply_profile(data: dict[str, Any], overlay: Mapping[str, Any], name: str, changes: list[str]) -> dict[str, Any]:
    result = copy.deepcopy(data)
    repository_overlays = overlay.get("repositories") or {}
    if repository_overlays and not isinstance(repository_overlays, Mapping):
        raise ConfigResolutionError(f"profile {name!r}.repositories must be an object keyed by repo name or path")
    for key, value in overlay.items():
        if key in {"extends", "repositories"}:
            continue
        if key not in {"project", "providers", "compose", "runtime", "observability", "fingerprint", "local"}:
            raise ConfigResolutionError(f"profile {name!r} contains unsupported overlay section: {key}")
        result[key] = _deep_merge(result.get(key, {}), value)
        changes.append(f"profile {name}: merged {key}")
    if repository_overlays:
        result["repositories"] = _apply_repository_overlays(
            list(result.get("repositories") or []), repository_overlays, name, changes
        )
    return result


def _group_spec(raw: Any) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    if isinstance(raw, list):
        return normalize_names(raw), (), True
    if not isinstance(raw, Mapping):
        raise ConfigResolutionError("group definition must be an array or object")
    repositories = normalize_names(raw.get("repositories"))
    tags = normalize_names(raw.get("tags"))
    return repositories, tags, bool(raw.get("include_dependencies", True))


def _repository_lookup(repositories: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in repositories:
        if item.get("repo"):
            lookup[str(item["repo"])] = item
        if item.get("path") is not None:
            lookup[str(item["path"])] = item
    return lookup


def _filter_groups(data: dict[str, Any], names: tuple[str, ...], changes: list[str]) -> dict[str, Any]:
    definitions = data.get("groups") or {}
    repositories = list(data.get("repositories") or [])
    lookup = _repository_lookup(repositories)
    selected_ids: set[int] = set()
    dependency_roots: list[dict[str, Any]] = []

    for name in names:
        if name not in definitions:
            raise ConfigResolutionError(f"unknown repository group: {name}")
        selectors, tags, include_dependencies = _group_spec(definitions[name])
        matched: list[dict[str, Any]] = []
        for selector in selectors:
            item = lookup.get(selector)
            if item is None:
                raise ConfigResolutionError(f"group {name!r} references unknown repository: {selector}")
            matched.append(item)
        if tags:
            tag_set = set(tags)
            matched.extend(
                item for item in repositories
                if tag_set.intersection(str(tag) for tag in (item.get("tags") or []))
            )
        if not selectors and not tags:
            raise ConfigResolutionError(f"group {name!r} must select repositories or tags")
        for item in matched:
            selected_ids.add(id(item))
            if include_dependencies:
                dependency_roots.append(item)
        changes.append(f"group {name}: selected {len({id(item) for item in matched})} repositories")

    queue = list(dependency_roots)
    while queue:
        item = queue.pop(0)
        for dependency in item.get("depends_on") or []:
            dep = lookup.get(str(dependency))
            if dep is None:
                raise ConfigResolutionError(
                    f"repository {item.get('repo')!r} references unknown dependency: {dependency}"
                )
            if id(dep) not in selected_ids:
                selected_ids.add(id(dep))
                queue.append(dep)
                changes.append(
                    f"group dependency: included {dep.get('repo') or dep.get('path')} for {item.get('repo')}"
                )

    selected = [copy.deepcopy(item) for item in repositories if id(item) in selected_ids]
    selected_lookup = _repository_lookup(selected)
    for item in selected:
        item["depends_on"] = [
            dep for dep in (item.get("depends_on") or []) if str(dep) in selected_lookup
        ]
    result = copy.deepcopy(data)
    result["repositories"] = selected
    return result


def resolve_config_data(
    data: dict[str, Any],
    *,
    profiles: str | Iterable[str] | None = None,
    groups: str | Iterable[str] | None = None,
) -> tuple[dict[str, Any], tuple[str, ...], tuple[str, ...], list[str]]:
    """Resolve named profile overlays and repository groups into one concrete config."""
    profile_names = normalize_names(profiles)
    group_names = normalize_names(groups)
    result = copy.deepcopy(data)
    changes: list[str] = []
    definitions = result.get("profiles") or {}
    cache: dict[str, dict[str, Any]] = {}
    for name in profile_names:
        overlay = _resolve_profile(definitions, name, cache=cache)
        result = _apply_profile(result, overlay, name, changes)
    if group_names:
        result = _filter_groups(result, group_names, changes)

    result.pop("profiles", None)
    result.pop("groups", None)
    if profile_names or group_names:
        result["x-rfm-resolution"] = {
            "profiles": list(profile_names),
            "groups": list(group_names),
        }
    return result, profile_names, group_names, changes
