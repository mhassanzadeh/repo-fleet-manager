# Repo Fleet Manager v0.8.0 patch notes

## Base version

- RFM base: `0.7.0`
- Target: `0.8.0`
- Config schema remains `1.0.0`

## Added

### Named profiles and inheritance

Profiles live under `profiles` and can overlay project, providers, local execution, Compose, fingerprint settings, and individual repositories.

```bash
rfm config --config repo-fleet.json --profile developer render
rfm doctor --config repo-fleet.json --profile ci
```

Profiles can extend one or more parent profiles. RFM detects unknown parents and inheritance cycles before execution.

### Repository overlays

Profile repository overlays are keyed by repository name or path:

```json
{
  "profiles": {
    "ci": {
      "repositories": {
        "web-client": {"enabled": false},
        "api-service": {"branch": "main"}
      }
    }
  }
}
```

`enabled: false` removes the repository from the effective catalog. The result is validated after all overlays are applied.

### Tags and groups

Repositories may define `tags`. Named groups select explicit repositories, tags, or both. Dependency inclusion is configurable.

```bash
rfm git --config repo-fleet.json --group backend status
rfm local --config repo-fleet.json --profile developer --group backend localize
```

Multiple `--profile` and `--group` options are combined in order; comma-separated values are also accepted.

### Effective config rendering

```bash
rfm config --config repo-fleet.json profiles
rfm config --config repo-fleet.json groups
rfm config --config repo-fleet.json --profile ci --group backend render
rfm config --config repo-fleet.json --profile ci --group backend render --output effective.json
```

The rendered document contains a strict-valid concrete catalog and an `x-rfm-resolution` trace.

## Validation and safety

RFM now rejects profile cycles, unknown profiles, unsupported overlay sections, unknown repository selectors and groups that reference missing repositories or tags. Dependency edges are expanded or pruned according to group policy before the effective config is validated.

## Compatibility

Existing schema `1.0.0` configurations remain valid. `profiles`, `groups`, and repository `tags` are optional. No migration is required.
