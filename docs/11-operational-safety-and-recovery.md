# Operational safety and recovery

RFM 0.6 adds a safety boundary around every command that changes repositories, remotes, configuration, submodules or runtime state.

## Configuration gate

Validate the desired state before applying it:

```bash
rfm config --config repo-fleet.json validate --strict
```

A legacy 0.3–0.5 configuration can be inspected and migrated without changing the file:

```bash
rfm config --config repo-fleet.json migrate
```

Apply the migration with an automatic backup:

```bash
rfm config --config repo-fleet.json migrate --apply
```

The schema rejects unknown fields, duplicate or nested repository paths, unknown dependencies, dependency cycles and secret-like keys. Custom extensions must use an `x-` prefix or be placed under repository `metadata`.

## Workspace lock

Every mutating `--apply` command obtains the configured lock, normally `.repo-fleet/lock`. A second process is rejected. A stale or exceptional lock can only be overridden with an explicit reason:

```bash
rfm local --config repo-fleet.json localize --apply \
  --force --reason "confirmed stale lock after host restart"
```

The reason is persisted in the operation journal.

## Safety inspection

Before pull, publish, submodule replacement or another sensitive operation, inspect all worktrees:

```bash
rfm safety --config repo-fleet.json status
rfm safety --config repo-fleet.json status --json
```

RFM reports dirty worktrees, detached HEADs, configured-branch mismatches, upstreams, ahead/behind counts and divergence. A forced override always requires `--reason`.

## Operation journal

Each applied mutation creates a JSON journal under `.repo-fleet/operations` containing:

- operation ID, command and original arguments;
- attempts and resume count;
- command-level steps, working directories and exit codes;
- generated-path, file/directory backup, Git remote and Git HEAD rollback actions;
- final status and error details.

Inspect journals with:

```bash
rfm ops --config repo-fleet.json list
rfm ops --config repo-fleet.json show OPERATION_ID
rfm ops --config repo-fleet.json show OPERATION_ID --json
```

## Resume

A failed or interrupted operation can be replayed using its original arguments:

```bash
rfm ops --config repo-fleet.json resume OPERATION_ID
```

Resume is reconciliation-based: idempotent steps detect already-created repositories/remotes and continue from the desired state. It records a new attempt in the same journal.

## Rollback

Rollback executes recorded compensating actions in reverse order and restores Git history before file backups:

```bash
rfm ops --config repo-fleet.json rollback OPERATION_ID
```

Rollback can restore changed files or complete directories, remote URLs and previous Git HEADs, and remove paths created by the operation. Directory rollback is used by `rfm local restore --overwrite` to preserve the previous local remotes before replacement. Provider-side repository creation, native forks and remote mirror pushes cannot always be deleted safely or automatically; the journal records an explicit manual rollback note for those actions.

## Dependency graph and parallelism

Repository dependencies are declared with `depends_on`. Validate and view the graph:

```bash
rfm graph --config repo-fleet.json show
rfm graph --config repo-fleet.json show --format dot --output fleet.dot
```

Local and Git fleet actions execute topological levels in order. Independent repositories within the same level can run concurrently:

```bash
rfm local --config repo-fleet.json localize --jobs 4 --apply
rfm git --config repo-fleet.json pull --jobs 4 --apply
```

Use lower concurrency for providers, disks or networks with strict rate or resource limits.

## Provider authentication

Credentials stay outside `repo-fleet.json`. A provider can declare a driver, host/profile, expected user and optional required scopes:

```json
{
  "github-work": {
    "type": "remote",
    "driver": "github",
    "namespace": "my-org",
    "host": "github.com",
    "cli": "gh",
    "profile": "work",
    "user": "my-user",
    "required_scopes": ["repo"],
    "url_template": "git@github.com:{namespace}/{repo}.git"
  }
}
```

Check the active identity and capabilities without printing tokens:

```bash
rfm auth --config repo-fleet.json status --provider github-work --verbose
rfm auth --config repo-fleet.json status --provider github-work --strict-scopes
rfm doctor --config repo-fleet.json --auth --strict-auth
```

Scope reporting may be unavailable for some fine-grained or externally supplied tokens. In that case `--strict-scopes` deliberately fails instead of assuming sufficient permission.

## Fork, mirror and reconciliation

Native forks are explicit lifecycle actions:

```bash
rfm repos --config repo-fleet.json fork --provider github --apply
rfm repos --config repo-fleet.json fork --provider gitlab --apply
```

Mirror mode pushes the local bare mirror with all refs:

```bash
rfm repos --config repo-fleet.json mirror --provider gitlab --apply
```

Inspect and optionally repair desired provider metadata:

```bash
rfm repos --config repo-fleet.json reconcile --provider github
rfm repos --config repo-fleet.json reconcile --provider github --apply
```

Reconciliation checks repository existence, fork lineage, default branch, visibility and topics. It can repair metadata drift, but it does not silently rewrite an incorrect fork parent.

## Backup before high-risk operations

Operation rollback protects changes on the same workspace, while a portable backup protects against disk or host loss. Before provider-wide rewrites, localization changes or destructive maintenance:

```bash
rfm local --config repo-fleet.json backup
rfm local --config repo-fleet.json backup --apply
rfm local verify-backup .repo-fleet/backups/<archive>.rfm-backup.tar.gz
```

See [backup and restore](12-backup-and-restore.md) for clean-machine recovery.

## ارتباط Operation Journal با Audit Log

از نسخه `0.13.0` هر اجرای CLI یک `run_id` دارد و mutationها پس از ایجاد journal، `operation_id` را در event stream ثبت می‌کنند. بنابراین برای تحلیل یک خطا می‌توان این دو فایل را کنار هم بررسی کرد:

```text
.repo-fleet/logs/<RUN_ID>.jsonl
.repo-fleet/operations/<OPERATION_ID>.json
```

```bash
rfm logs show RUN_ID
rfm ops show OPERATION_ID
```

argv و commandهای ثبت‌شده پیش از ذخیره پالایش می‌شوند تا token یا password وارد log و journal نشود.

## Policy guard before mutations

RFM 0.15.0 evaluates enabled policy rules before entering a mutation journal. `operation.guard` can deny selected actions or require `--reason` and `--force`. Policy decisions, violations and applied exception IDs are written into the same structured audit run as the operation. This governance layer complements workspace safety checks; it does not replace clean-tree, detached-HEAD or divergence protection.
