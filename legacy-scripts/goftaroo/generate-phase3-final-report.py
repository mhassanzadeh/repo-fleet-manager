#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(cmd, cwd=str(cwd), text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Phase 3 final hardening report.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default="docs/11-engineering/phase-03-final-hardening-report.md")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)

    inventory_json = root / "docs/11-engineering/phase-03-final-api-gateway-inventory.json"
    inventory_md = root / "docs/11-engineering/phase-03-final-api-gateway-inventory.md"

    subprocess.check_call(
        [
            "python3",
            str(root / "scripts/phase3-final-inventory.py"),
            "--repo-root",
            str(root),
            "--json",
            str(inventory_json),
            "--markdown",
            str(inventory_md),
            "--strict",
        ],
        cwd=str(root),
    )

    git_root_status = run(["git", "status", "--short"], root)
    api_gateway_status = run(["git", "status", "--short"], root / "services/api-gateway")
    root_head = run(["git", "rev-parse", "--short", "HEAD"], root)
    api_gateway_head = run(["git", "rev-parse", "--short", "HEAD"], root / "services/api-gateway")

    report = f"""# Phase 3 Final Hardening Report

Generated at: `{datetime.now(timezone.utc).isoformat()}`

## Scope

This report closes the Phase 3 API Gateway modularization and audit/security hardening work.

## Final state

- API Gateway `app.py` has been reduced to bootstrap/wiring responsibilities.
- Direct route decorators, direct `app.add_api_route`, direct middleware decorators, and direct startup decorators have been extracted.
- Legacy phase-prefixed helper functions have been moved out of `app.py`.
- Phase 3.20 audit integrity and Phase 3.21 export verification smoke tests remain the final regression anchors.
- Phase 3.40 is the consolidated API Gateway smoke source of truth.

## Inventory

See:

- `docs/11-engineering/phase-03-final-api-gateway-inventory.md`
- `docs/11-engineering/phase-03-final-api-gateway-inventory.json`

## Git status snapshot

### Root

- HEAD: `{root_head}`

```text
{git_root_status or "clean"}
```

### services/api-gateway

- HEAD: `{api_gateway_head}`

```text
{api_gateway_status or "clean"}
```

## Required validation

```bash
./scripts/validate-phase3-41-final-hardening.sh
./scripts/smoke-phase3-41-final-hardening.sh
```

## Release decision

Phase 3 can be considered closed after:

1. `validate-phase3-41-final-hardening.sh` passes.
2. `smoke-phase3-41-final-hardening.sh` passes.
3. `services/api-gateway` submodule changes are committed and pushed.
4. root repository gitlink/docs/scripts are committed and tagged.

Recommended tag:

```bash
git tag -a v3.41.0 -m "Phase 3.41 Final Hardening and API Gateway Modularization Closure"
```
"""
    output.write_text(report, encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
