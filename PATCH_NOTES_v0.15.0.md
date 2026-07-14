# Repo Fleet Manager v0.15.0 patch notes

## Release identity

- Base revision: `61d56a9a080e2209327c949f9d837e6c088b2c59`
- Base version: `0.14.0`
- Target version: `0.15.0`
- Config schema version: `1.0.0` (unchanged)
- Policy report schema version: `1.0.0`
- Primary scope: GAP-014 — Policy-as-Code for repository and supply-chain governance

## Added commands

```bash
rfm policy check
rfm policy enforce
rfm policy explain RULE_ID
rfm policy exceptions
rfm policy input
```

## Built-in controls

- Repository visibility, branch, provider and remote-host restrictions.
- Clean-worktree and signed-HEAD requirements.
- Approved container registries and supply-chain requirement gates.
- Mutation operation guards requiring reason, force or complete denial.
- Rule and repository filters for focused CI checks.

## Exceptions and audit

- Exceptions require rule ID, reason, approver and expiration.
- Optional repository/action globs and ticket references.
- Expired exceptions never suppress violations.
- Policy evaluation emits a structured `policy.evaluated` audit event.
- Enforcement failures use exit code `2`.

## Rego

- Optional OPA/Rego adapter using normalized JSON policy input.
- Rego path is workspace-relative and cannot contain `..`.
- Queries may return strings or structured denial objects.

## Compatibility

- Existing configs remain valid because the `policy` section is optional.
- Built-in mutation enforcement is active only when `policy.enabled` is true and `policy.mode` is `enforce`.
- Existing safety and operation journal behavior is preserved.
