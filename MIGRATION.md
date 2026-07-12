# Migration guide

## 0.5.0 to 0.6.0

RFM 0.6 introduces a versioned configuration contract and safety journal. Existing 0.5 files continue to load through in-memory migration, but writing the normalized form is recommended.

### 1. Preview migration

```bash
rfm config --config repo-fleet.json migrate
```

### 2. Apply with backup

```bash
rfm config --config repo-fleet.json migrate --apply
```

The original file is saved as `repo-fleet.json.bak` or a numbered backup if one already exists.

### 3. Validate strictly

```bash
rfm config --config repo-fleet.json validate --strict
```

The migrated file includes:

- `schema_version: "1.0.0"`;
- provider `driver` and `required_scopes` defaults;
- repository `source_type`, `remote_mode` and `depends_on` defaults;
- `local.operations_dir`, `local.lock_file` and `local.default_jobs`.

Unknown custom fields should be renamed with an `x-` prefix or moved into repository `metadata`. Secrets must be removed from the manifest and supplied through the provider CLI, environment or an external credential store.

### 4. Review execution order

```bash
rfm graph --config repo-fleet.json show
```

Declare `depends_on` where repositories must be created, cloned, pulled or built in order.

### 5. Verify provider identity

```bash
rfm auth --config repo-fleet.json status --verbose
```

Before a provider-side `--apply`, verify the expected user, host and namespace.

### 6. Apply local desired state

```bash
rfm local --config repo-fleet.json plan
rfm local --config repo-fleet.json localize --apply
```

Every applied mutation is now recorded under `.repo-fleet/operations` and protected by `.repo-fleet/lock`.

## Older versions

Configurations from 0.3 and 0.4 are migrated through the same normalization path. Review `source_type` and `remote_mode` inference before applying changes.
