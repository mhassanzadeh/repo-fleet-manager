# Profiles, overlays and repository groups

RFM can keep one provider-neutral base catalog and derive environment-specific or user-specific effective configurations without duplicating `repo-fleet.json`.

## Profiles

Profiles are named overlays under the top-level `profiles` object. They may override `project`, `providers`, `compose`, `fingerprint`, `local`, and individual repositories.

```json
{
  "profiles": {
    "developer": {
      "project": {"default_provider": "local"},
      "local": {"default_jobs": 2},
      "providers": {
        "local": {"namespace": ".repo-fleet/dev-remotes"}
      }
    },
    "ci": {
      "extends": "developer",
      "project": {"default_provider": "github"},
      "local": {"default_jobs": 8},
      "repositories": {
        "web-client": {"enabled": false},
        "api-service": {"branch": "main"}
      }
    }
  }
}
```

`extends` accepts one profile name or an array. Parent profiles are merged first and the selected profile wins. Cycles and unknown parents fail validation.

Repository overlay keys may be either repository `repo` names or `path` values. An overlay can change any repository field. `enabled: false` removes the repository from the effective catalog.

Apply one or more profiles:

```bash
rfm doctor --config repo-fleet.json --profile developer
rfm local --config repo-fleet.json --profile developer localize
rfm repos --config repo-fleet.json --profile ci audit
```

Options are repeatable and comma-separated values are accepted:

```bash
rfm doctor --config repo-fleet.json \
  --profile developer \
  --profile personal
```

## Repository tags and groups

Repositories can define tags:

```json
{
  "path": "services/api",
  "repo": "api-service",
  "tags": ["backend", "runtime"],
  "depends_on": ["shared-contracts"]
}
```

Groups select repositories by explicit name/path, tags, or both:

```json
{
  "groups": {
    "backend": {
      "tags": ["backend"],
      "include_dependencies": true
    },
    "frontend-only": {
      "repositories": ["web-client"],
      "include_dependencies": false
    },
    "shared": ["shared-contracts"]
  }
}
```

When `include_dependencies` is true, RFM recursively includes all required repositories. When false, dependency edges to unselected repositories are removed from the effective catalog.

Use a group with any config-aware command:

```bash
rfm graph --config repo-fleet.json --group backend show
rfm git --config repo-fleet.json --group backend status
rfm repos --config repo-fleet.json --group backend audit
rfm local --config repo-fleet.json --profile developer --group backend localize
```

Multiple groups are combined as a union.

## Inspect the effective configuration

List available definitions:

```bash
rfm config --config repo-fleet.json profiles
rfm config --config repo-fleet.json groups
```

Render the fully merged and filtered configuration:

```bash
rfm config --config repo-fleet.json \
  --profile ci \
  --group backend \
  render
```

Write it to a reusable strict-valid JSON file:

```bash
rfm config --config repo-fleet.json \
  --profile ci \
  --group backend \
  render --output .repo-fleet/rendered/ci-backend.json
```

The rendered document removes the source `profiles` and `groups` definitions and adds an `x-rfm-resolution` section describing the active selections.

## Validation rules

RFM rejects:

- unknown profiles or parent profiles;
- profile inheritance cycles;
- unsupported profile overlay sections;
- repository overlays targeting unknown repositories;
- groups referencing unknown repositories or tags;
- invalid effective configs after merging;
- dependencies that become invalid after an overlay.

The base file remains compatible with schema `1.0.0`; profiles and groups are optional additions.
