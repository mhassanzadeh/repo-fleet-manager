from __future__ import annotations

import json
from collections import Counter
from importlib import resources
from pathlib import Path
from typing import Any

STATUS_ICON = {
    "implemented": "✓",
    "partial": "~",
    "planned": "→",
    "missing": "×",
}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def load_service_catalog(root: Path, catalog_file: str | None = None) -> dict[str, Any]:
    candidates: list[Path] = []
    if catalog_file:
        requested = Path(catalog_file).expanduser()
        candidates.append(requested if requested.is_absolute() else root / requested)
    candidates.append(root / "catalog" / "rfm-service-catalog.json")

    for path in candidates:
        if path.exists():
            return _read_and_validate(path)

    packaged = resources.files("repo_fleet_manager").joinpath("data/rfm-service-catalog.json")
    with packaged.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    _validate(data, "packaged catalog")
    return data


def _read_and_validate(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    _validate(data, str(path))
    return data


def _validate(data: dict[str, Any], source: str) -> None:
    for key in ("schema_version", "catalog_version", "project", "domains", "gaps"):
        if key not in data:
            raise ValueError(f"Service catalog {source} is missing required key: {key}")
    domain_ids: set[str] = set()
    capability_ids: set[str] = set()
    for domain in data["domains"]:
        domain_id = domain.get("id")
        if not domain_id or domain_id in domain_ids:
            raise ValueError(f"Invalid or duplicate domain id in {source}: {domain_id}")
        domain_ids.add(domain_id)
        for capability in domain.get("capabilities", []):
            capability_id = capability.get("id")
            if not capability_id or capability_id in capability_ids:
                raise ValueError(f"Invalid or duplicate capability id in {source}: {capability_id}")
            capability_ids.add(capability_id)
    gap_ids = [gap.get("id") for gap in data["gaps"]]
    if len(gap_ids) != len(set(gap_ids)) or any(not item for item in gap_ids):
        raise ValueError(f"Invalid or duplicate gap id in {source}")


def capability_rows(catalog: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for domain in catalog["domains"]:
        for capability in domain.get("capabilities", []):
            components = capability.get("components", [])
            missing_evidence = [component for component in components if not (root / component).exists()]
            rows.append({
                **capability,
                "domain_id": domain["id"],
                "domain_name": domain["name"],
                "evidence_ok": not missing_evidence,
                "missing_evidence": missing_evidence,
            })
    return rows


def summary(catalog: dict[str, Any], root: Path) -> dict[str, Any]:
    rows = capability_rows(catalog, root)
    status_counts = Counter(row.get("status", "unknown") for row in rows)
    maturity_counts = Counter(row.get("maturity", "unknown") for row in rows)
    priority_counts = Counter(gap.get("priority", "unknown") for gap in catalog["gaps"])
    evidence_failures = [row["id"] for row in rows if not row["evidence_ok"]]
    total = len(rows)
    weighted = (
        status_counts.get("implemented", 0)
        + status_counts.get("partial", 0) * 0.5
        + status_counts.get("planned", 0) * 0.15
    )
    return {
        "project": catalog["project"],
        "schema_version": catalog["schema_version"],
        "catalog_version": catalog["catalog_version"],
        "domain_count": len(catalog["domains"]),
        "capability_count": total,
        "status_counts": dict(status_counts),
        "maturity_counts": dict(maturity_counts),
        "gap_count": len(catalog["gaps"]),
        "gap_priority_counts": dict(priority_counts),
        "logical_completion_percent": round((weighted / total * 100) if total else 0, 1),
        "missing_evidence": evidence_failures,
    }


def filtered_gaps(catalog: dict[str, Any], priority: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    gaps = catalog["gaps"]
    if priority:
        gaps = [gap for gap in gaps if gap.get("priority") == priority]
    if status:
        gaps = [gap for gap in gaps if gap.get("status") == status]
    return sorted(gaps, key=lambda item: (PRIORITY_ORDER.get(item.get("priority", "P9"), 99), item.get("id", "")))


def render_tree_text(catalog: dict[str, Any], root: Path) -> str:
    lines = [f"{catalog['project']['name']} capability tree (catalog {catalog['catalog_version']})"]
    for domain in catalog["domains"]:
        lines.append(f"\n{domain['name']} [{domain['id']}]")
        capabilities = domain.get("capabilities", [])
        for index, capability in enumerate(capabilities):
            branch = "└──" if index == len(capabilities) - 1 else "├──"
            icon = STATUS_ICON.get(capability.get("status"), "?")
            evidence = [item for item in capability.get("components", []) if not (root / item).exists()]
            evidence_note = f" | evidence-missing={','.join(evidence)}" if evidence else ""
            lines.append(
                f"  {branch} [{icon}] {capability['id']}: {capability['name']} "
                f"({capability.get('status')}/{capability.get('maturity')}){evidence_note}"
            )
    return "\n".join(lines) + "\n"


def render_gaps_text(catalog: dict[str, Any], priority: str | None = None, status: str | None = None) -> str:
    gaps = filtered_gaps(catalog, priority, status)
    lines = [f"RFM logical gap analysis ({len(gaps)} items)"]
    for gap in gaps:
        lines.extend([
            f"\n[{gap['priority']}] {gap['id']} — {gap['title']}",
            f"  category: {gap['category']} | status: {gap['status']}",
            f"  why: {gap['rationale']}",
            "  scope: " + "; ".join(gap.get("recommended_scope", [])),
        ])
    return "\n".join(lines) + "\n"


def render_summary_text(catalog: dict[str, Any], root: Path) -> str:
    data = summary(catalog, root)
    statuses = ", ".join(f"{key}={value}" for key, value in sorted(data["status_counts"].items()))
    priorities = ", ".join(f"{key}={value}" for key, value in sorted(data["gap_priority_counts"].items()))
    lines = [
        f"{data['project']['name']} service catalog",
        f"catalog version: {data['catalog_version']} | schema: {data['schema_version']}",
        f"domains: {data['domain_count']} | capabilities: {data['capability_count']} | gaps: {data['gap_count']}",
        f"capability status: {statuses}",
        f"gap priorities: {priorities}",
        f"logical completion: {data['logical_completion_percent']}%",
        f"missing evidence: {len(data['missing_evidence'])}",
    ]
    return "\n".join(lines) + "\n"


def render_markdown(catalog: dict[str, Any], root: Path, include_gaps: bool = True) -> str:
    data = summary(catalog, root)
    lines = [
        f"# {catalog['project']['name']} service catalog",
        "",
        f"> Catalog version `{catalog['catalog_version']}` · schema `{catalog['schema_version']}` · lifecycle `{catalog['project'].get('lifecycle', '-')}`",
        "",
        catalog["project"]["description"],
        "",
        "## Executive summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Domains | {data['domain_count']} |",
        f"| Capabilities | {data['capability_count']} |",
        f"| Implemented | {data['status_counts'].get('implemented', 0)} |",
        f"| Partial | {data['status_counts'].get('partial', 0)} |",
        f"| Planned | {data['status_counts'].get('planned', 0)} |",
        f"| Missing | {data['status_counts'].get('missing', 0)} |",
        f"| Logical completion | {data['logical_completion_percent']}% |",
        f"| Open gaps | {data['gap_count']} |",
        "",
        "The completion percentage is a planning indicator: implemented capabilities count as 100%, partial as 50%, and planned as 15%. It is not a production-readiness certification.",
        "",
        "## Capability tree",
        "",
    ]
    for domain in catalog["domains"]:
        lines.extend([f"### {domain['name']}", "", domain.get("description", ""), "", "| Capability | Status | Maturity | Commands / evidence |", "|---|---|---|---|"])
        for capability in domain.get("capabilities", []):
            commands = "<br>".join(f"`{item}`" for item in capability.get("commands", []))
            components = "<br>".join(f"`{item}`" for item in capability.get("components", []))
            details = commands or components or "—"
            if commands and components:
                details += "<br>" + components
            icon = STATUS_ICON.get(capability.get("status"), "?")
            lines.append(f"| `{capability['id']}` — {capability['name']} | {icon} {capability.get('status')} | {capability.get('maturity')} | {details} |")
        lines.append("")

    if include_gaps:
        lines.extend(["## Prioritized logical gaps", ""])
        for priority in ("P0", "P1", "P2", "P3"):
            gaps = filtered_gaps(catalog, priority=priority)
            if not gaps:
                continue
            lines.extend([f"### {priority}", ""])
            for gap in gaps:
                lines.extend([
                    f"#### {gap['id']} — {gap['title']}",
                    "",
                    f"**Category:** `{gap['category']}` · **Current state:** `{gap['status']}`",
                    "",
                    gap["rationale"],
                    "",
                    "Recommended scope:",
                    "",
                    *[f"- {item}" for item in gap.get("recommended_scope", [])],
                    "",
                    "Acceptance criteria:",
                    "",
                    *[f"- {item}" for item in gap.get("acceptance_criteria", [])],
                    "",
                ])
    lines.extend([
        "## Regeneration",
        "",
        "```bash",
        "rfm catalog --view all --format markdown --output docs/generated/rfm-service-catalog.md",
        "rfm catalog --view gaps --format markdown --output reports/gap-analysis.md",
        "```",
        "",
    ])
    return "\n".join(lines)



def render_gaps_markdown(catalog: dict[str, Any], priority: str | None = None, status: str | None = None) -> str:
    gaps = filtered_gaps(catalog, priority, status)
    lines = [
        f"# {catalog['project']['name']} logical gap analysis",
        "",
        f"> Catalog version `{catalog['catalog_version']}` · {len(gaps)} prioritized gaps",
        "",
    ]
    current_priority: str | None = None
    for gap in gaps:
        if gap["priority"] != current_priority:
            current_priority = gap["priority"]
            lines.extend([f"## {current_priority}", ""])
        lines.extend([
            f"### {gap['id']} — {gap['title']}",
            "",
            f"**Category:** `{gap['category']}` · **Current state:** `{gap['status']}`",
            "",
            gap["rationale"],
            "",
            "Recommended scope:",
            "",
            *[f"- {item}" for item in gap.get("recommended_scope", [])],
            "",
            "Acceptance criteria:",
            "",
            *[f"- {item}" for item in gap.get("acceptance_criteria", [])],
            "",
        ])
    return "\n".join(lines) + "\n"

def render_json(catalog: dict[str, Any], root: Path, view: str, priority: str | None = None, status: str | None = None) -> str:
    if view == "summary":
        payload: Any = summary(catalog, root)
    elif view == "tree":
        payload = {"project": catalog["project"], "domains": catalog["domains"], "summary": summary(catalog, root)}
    elif view == "gaps":
        payload = {"project": catalog["project"], "gaps": filtered_gaps(catalog, priority, status)}
    else:
        payload = {**catalog, "summary": summary(catalog, root)}
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_catalog(catalog: dict[str, Any], root: Path, view: str, output_format: str, priority: str | None = None, status: str | None = None, plugin_config: Any | None = None) -> str:
    normalized_format = output_format.strip().lower()
    if normalized_format not in {"text", "json", "markdown"}:
        from .plugin_api import CatalogExportRequest, CatalogExporterPluginV1
        from .plugins import registry_for
        registry = registry_for(plugin_config)
        plugin = registry.resolve("catalog-exporter", normalized_format)
        if plugin is None or not isinstance(plugin, CatalogExporterPluginV1):
            raise ValueError(
                f"unsupported catalog format: {output_format}; install a compatible catalog exporter plugin"
            )
        rendered = plugin.render(CatalogExportRequest(
            root=root.resolve(), catalog=catalog, view=view, output_format=normalized_format,
            priority=priority, status=status, options=dict(registry.setting(plugin.name)),
        ))
        return rendered.decode("utf-8") if isinstance(rendered, bytes) else str(rendered)
    output_format = normalized_format
    if output_format == "json":
        return render_json(catalog, root, view, priority, status)
    if output_format == "markdown":
        if view == "summary":
            data = summary(catalog, root)
            return "# RFM catalog summary\n\n```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```\n"
        if view == "gaps":
            return render_gaps_markdown(catalog, priority, status)
        if view == "tree":
            temporary = {**catalog, "gaps": []}
            return render_markdown(temporary, root, include_gaps=False)
        return render_markdown(catalog, root, include_gaps=True)
    if view == "summary":
        return render_summary_text(catalog, root)
    if view == "gaps":
        return render_gaps_text(catalog, priority, status)
    if view == "all":
        return render_summary_text(catalog, root) + "\n" + render_tree_text(catalog, root) + "\n" + render_gaps_text(catalog, priority, status)
    return render_tree_text(catalog, root)
