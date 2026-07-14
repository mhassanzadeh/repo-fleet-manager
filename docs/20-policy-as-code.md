# Policy-as-Code governance

RFM 0.15.0 adds a policy layer that evaluates repository, Git, operation and supply-chain state from the same `repo-fleet.json` source used by the rest of the CLI. The built-in engine has no external dependency. OPA/Rego can be enabled for organization-specific rules.

## Commands

```bash
rfm policy --config repo-fleet.json --root . check
rfm policy --config repo-fleet.json --root . enforce
rfm policy --config repo-fleet.json --root . explain RULE_ID
rfm policy --config repo-fleet.json --root . exceptions
rfm policy --config repo-fleet.json --root . input
```

`check` always returns zero after a successful evaluation and reports non-compliance without blocking. `enforce` returns exit code `2` when an unexcepted violation meets or exceeds `policy.fail_on`.

## Configuration

```json
{
  "policy": {
    "enabled": true,
    "mode": "enforce",
    "fail_on": "error",
    "rules": [
      {
        "id": "critical-repositories-private",
        "type": "repository.visibility",
        "severity": "error",
        "selectors": {
          "tags": ["critical"]
        },
        "parameters": {
          "allowed": ["private"]
        }
      },
      {
        "id": "approved-remote-hosts",
        "type": "repository.remote-host",
        "severity": "error",
        "parameters": {
          "allowed_hosts": ["github.com", "gitlab.example.com"],
          "require_remote": true
        }
      },
      {
        "id": "release-requires-reason",
        "type": "operation.guard",
        "severity": "error",
        "parameters": {
          "actions": ["repos publish", "repos mirror", "compose down"],
          "require_reason": true
        }
      }
    ],
    "exceptions": []
  }
}
```

Rules may select repositories by `repositories`, `tags`, `kinds` or `providers`. Empty selectors apply to every repository.

## Built-in rule types

| Type | Purpose | Important parameters |
|---|---|---|
| `repository.visibility` | Restrict configured visibility | `allowed` |
| `repository.branch` | Restrict configured or active branches | `allowed`, `forbidden`, `require_config_match` |
| `repository.provider` | Restrict provider profiles | `allowed` |
| `repository.remote-host` | Restrict Git remote hosts | `allowed_hosts`, `require_remote` |
| `repository.clean` | Require clean worktrees | none |
| `repository.signed-head` | Require an acceptable Git signature status | `accepted_statuses`, `require_worktree` |
| `supply-chain.registry` | Restrict image registries | `allowed_registries` |
| `supply-chain.requirements` | Require immutable digest, source match, SBOM, scan, signature or attestation policy | `require_*`, `require_manifest` |
| `operation.guard` | Deny operations or require reason/force | `actions`, `deny`, `require_reason`, `require_force` |

Git signature statuses use the values returned by `git log --format=%G?`. A conservative rule normally accepts `G` and optionally `U` after the organization's trust model has been documented.

## Exceptions

Exceptions are explicit, scoped and expiring:

```json
{
  "id": "temporary-public-demo",
  "rule_id": "critical-repositories-private",
  "repositories": ["demo-*"],
  "reason": "Customer demonstration migration window",
  "approved_by": "security@example.com",
  "ticket": "SEC-421",
  "expires_at": "2026-08-01T00:00:00Z"
}
```

An active exception changes a violation to `EXCEPTED`. An expired exception never suppresses a violation and is listed separately in the report. `rule_id: "*"` is supported but should be reserved for short emergency windows and tightly scoped repositories or actions.

```bash
rfm policy --config repo-fleet.json exceptions
rfm policy --config repo-fleet.json exceptions --active-only
```

## Mutation guard

When `policy.enabled` is true and `policy.mode` is `enforce`, every command that enters RFM's mutation journal evaluates policy before changing the workspace or a remote provider. An `operation.guard` can therefore block operations such as:

```text
repos publish
repos mirror
compose down
local restore
cache import
cache bootstrap
runtime up
```

Operations that require justification must receive the normal safety option:

```bash
rfm repos --config repo-fleet.json publish \
  --provider github \
  --namespace example \
  --apply \
  --reason "Approved release SEC-421"
```

The policy report and applied exception identifiers are emitted as `policy.evaluated` events in the JSONL audit log.

## CI gate

```bash
rfm --format json \
  policy --config repo-fleet.json --root . \
  enforce --fail-on warning
```

A minimal GitHub Actions step:

```yaml
- name: Enforce RFM policy
  run: rfm policy --config repo-fleet.json --root . enforce
```

Use `check` for advisory adoption and switch the config to `mode: enforce` after violations and exceptions have owners.

## OPA/Rego adapter

```json
{
  "policy": {
    "enabled": true,
    "mode": "enforce",
    "rego": {
      "enabled": true,
      "policy_path": "configs/policy.example.rego",
      "query": "data.rfm.deny",
      "executable": "opa"
    }
  }
}
```

The Rego path must be relative and cannot escape the workspace. RFM sends the normalized policy input on stdin. The query may return strings or objects with fields such as `rule_id`, `severity`, `subject`, `repository`, `action`, `message` and `remediation`.

Inspect the exact input without running OPA:

```bash
rfm policy --config repo-fleet.json --root . input
```

A starter policy is available at [`../configs/policy.example.rego`](../configs/policy.example.rego).

## Report schema

Machine-readable output uses [`../schemas/rfm-policy-report.schema.json`](../schemas/rfm-policy-report.schema.json). Reports include compliance and blocking counts separately: advisory `check` may be non-compliant while remaining non-blocking; `enforce` marks threshold violations as blocking.
