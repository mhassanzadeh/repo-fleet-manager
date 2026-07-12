# Patch notes — Repo Fleet Manager v0.5.0

## Added

- Machine-readable RFM service/capability catalog.
- Capability tree grouped into 11 logical domains.
- Status and maturity model for implemented, partial, planned and missing capabilities.
- Prioritized logical gap analysis with P0/P1/P2 roadmap items and acceptance criteria.
- New catalog views: `summary`, `tree`, `gaps`, `all`, and backward-compatible `repositories`.
- Text, JSON and Markdown output formats.
- File output support and evidence validation for CI.
- Generated service catalog and gap analysis documents.
- Make targets for catalog generation and validation.

## Commands

```bash
rfm catalog --root . --view summary
rfm catalog --root . --view tree
rfm catalog --root . --view gaps --priority P0
rfm catalog --root . --view all --format markdown --output docs/generated/rfm-service-catalog.md
make catalog-docs catalog-check
```

## Compatibility

`rfm catalog --config repo-fleet.json` still prints the repository inventory. Use `--view` to select the new RFM capability catalog views.
