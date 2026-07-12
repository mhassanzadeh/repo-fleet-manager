# Repo Fleet Manager v0.9.0 patch notes

## Base revision

- Repository: `mhassanzadeh/repo-fleet-manager`
- Branch: `master`
- Base commit: `2168c5487157522966058d703ef34df1e5517f4d`
- Base version: `0.8.0`
- Target version: `0.9.0`
- Config schema remains `1.0.0`

## Added

### Portable parent project initialization

```bash
rfm init-project banking-platform \
  --directory ./banking-platform \
  --provider github \
  --namespace my-org

rfm init-project banking-platform \
  --directory ./banking-platform \
  --provider github \
  --namespace my-org \
  --apply
```

The generated parent contains `repo-fleet.json`, `repo-fleet.lock.json`, README, MIT license, gitignore and a baseline GitHub Actions workflow. Git initialization is enabled by default and can be disabled with `--no-git-init`.

### Repository and service templates

```bash
rfm scaffold templates
rfm scaffold repository customer-api \
  --config repo-fleet.json \
  --root . \
  --path services/customer-api \
  --template python-service \
  --kind service \
  --tag backend \
  --apply
```

Built-in templates:

- `generic`
- `python-cli`
- `python-service`
- `node-service`

Scaffolding updates the base config and regenerates the bootstrap lock. Existing files are protected unless `--force` is explicitly supplied.

### Bootstrap lock

```bash
rfm bootstrap --config repo-fleet.json --root . lock
rfm bootstrap --config repo-fleet.json --root . lock --apply
rfm bootstrap --config repo-fleet.json --root . verify
rfm bootstrap --config repo-fleet.json --root . verify --json
```

The deterministic lock records normalized config digest, repository lifecycle and dependency contract, template identity and selected baseline file checksums. It contains no absolute workspace paths.

## Compatibility

Existing `0.8.0` configuration files remain valid. No schema migration is required. The bootstrap lock is optional for existing projects until generated.

## Validation

- Legacy test suite and new scaffold/lock tests
- Strict validation of all sample configs
- Bash and Fish completion syntax checks
- Catalog evidence validation
- Wheel and source distribution build
- Clean-environment wheel installation
- Patch apply and rollback against exact base commit `2168c548...`
