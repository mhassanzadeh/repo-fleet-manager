# Repo Fleet Manager v0.16.0 patch notes

## Release identity

- Base revision: `3b4800d846c0462d15436db55af05b02bb2fefdb`
- Base version: `0.15.0`
- Target version: `0.16.0`
- Config schema: `1.0.0` (unchanged)
- Plugin API: `1.0`
- Primary scope: GAP-016 — stable plugin API

## Added

- Public contracts in `repo_fleet_manager.plugin_api`.
- Entry-point loader for provider, runtime, catalog exporter and artifact backend plugins.
- Lazy discovery, compatibility checks, allow/deny configuration, alias conflict detection and failure isolation.
- Real provider and runtime delegation paths.
- Plugin-defined catalog formats.
- URI-based artifact storage commands and built-in local file backend.
- Plugin diagnostic JSON Schema.
- Reference package under `examples/rfm-example-plugin`.

## Compatibility

Built-in providers, Compose runtime and core catalog formats remain unchanged. Plugin API `1.x` is the supported contract for the `0.16.x` release line.

## Security

Plugins execute in-process with the operator's permissions and must be trusted. Secrets remain outside config. External discovery can be disabled with `RFM_DISABLE_PLUGINS=1`, and strict health checks are opt-in.

## Validation

- Existing regression suite
- Plugin entry-point discovery and contract tests
- API major mismatch and alias conflict isolation
- Provider/runtime/catalog/artifact delegation
- Example plugin installation from packaged artifacts
- Strict configuration validation
- Completion, documentation and catalog evidence checks
- Wheel and source distribution smoke tests
