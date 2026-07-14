# Repo Fleet Manager v0.13.0 patch notes

## Release identity

- Base revision: `e265e5320438e17d4ab3cb0d7f20708768e87db7`
- Base version: `0.12.0`
- Target version: `0.13.0`
- Schema version: `1.0.0` (unchanged)
- Event schema version: `1.0.0`
- Primary scope: GAP-007 — unified structured output and audit logging

## Added

- Position-independent `--format text|json|jsonl` for all CLI commands.
- Stable JSON execution envelope and JSONL event stream.
- Redacted audit logs under `.repo-fleet/logs`.
- Event JSON Schema in `schemas/rfm-event.schema.json`.
- `rfm logs list/show/verify/purge` commands.
- Run IDs, duration, exit status and operation journal correlation.
- Configurable audit directory, retention and output capture.

## Compatibility

Existing command-specific `--json` options keep their previous payload shape. Command-specific catalog/graph formats continue to work. New structured envelopes are selected explicitly with the global output format.

## Security

- Sensitive argv values, mappings, URL credentials and common provider tokens are redacted.
- Operation journal argv and step commands are redacted.
- Audit files are created with user-only permissions.
- Config validation still rejects stored secrets.

## Validation performed

- Existing regression suite
- JSON envelope and JSONL event contract
- Event schema verification
- Audit list/show/verify workflows
- Redaction and operation correlation
- Strict config validation
- Bash/Fish completion validation
- Documentation and catalog evidence checks
- Wheel and source distribution smoke tests
