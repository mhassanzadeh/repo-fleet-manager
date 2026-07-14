# Repo Fleet Manager v0.12.0 patch notes

## Release identity

- Base revision: `ece4926bf23436f8b9a6d9b8c6150a6947d94df1`
- Base version: `0.11.0`
- Target version: `0.12.0`
- Schema version: `1.0.0` (unchanged)
- Primary scope: GAP-013 — service health, readiness and ordered runtime startup

## Added commands

```bash
rfm runtime status
rfm runtime doctor --logs
rfm runtime wait --timeout 120
rfm runtime up --apply
```

## Runtime model

- Discovers Compose services from `compose config` with repository and explicit-config fallbacks.
- Reads container running state and Compose health status through Docker or Podman inspect.
- Supports HTTP, TCP and local command readiness probes.
- Keeps running and ready as independent fields.
- Resolves dependency levels from explicit runtime config, Compose dependencies or repository dependencies.
- Includes dependencies automatically when a service is selected.
- Starts one dependency level at a time and waits for readiness before continuing.

## Diagnostics

- Optional recent Compose logs for failing services.
- Per-service reason, probe result, latency and remediation.
- JSON output suitable for CI and automation.
- Exit code `2` when required services are not ready.

## Configuration

The optional top-level `runtime` section adds default timeout, polling interval, log tail, running fallback and service-specific probes. Profile overlays may override runtime values. Schema version remains `1.0.0`.

## Validation performed

- Existing regression suite
- Runtime dependency ordering and cycle detection
- Running-versus-ready distinction
- Health transition from starting to healthy
- Selected-service dependency expansion
- Wizard-generated runtime defaults
- Strict schema validation
- Bash/Fish completion validation
- Documentation link and catalog evidence validation
- Wheel and source distribution smoke tests
