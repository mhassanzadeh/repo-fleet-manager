# Repo Fleet Manager service catalog

> Catalog version `0.15.0` · schema `1.0` · lifecycle `beta`

Config-driven orchestration for large Git repository fleets, submodules, local development, providers, Compose runtimes and source/image integrity.

## Executive summary

| Metric | Value |
|---|---:|
| Domains | 11 |
| Capabilities | 58 |
| Implemented | 52 |
| Partial | 3 |
| Planned | 1 |
| Missing | 2 |
| Logical completion | 92.5% |
| Open gaps | 18 |

The completion percentage is a planning indicator: implemented capabilities count as 100%, partial as 50%, and planned as 15%. It is not a production-readiness certification.

## Capability tree

### CLI and operator experience

Terminal entrypoint, discoverability, safety switches and machine-readable output.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `cli.entrypoint` — Installable rfm terminal command | ✓ implemented | beta | `rfm --version`<br>`make install`<br>`pyproject.toml`<br>`src/repo_fleet_manager/cli.py`<br>`Makefile` |
| `cli.completion` — Bash and Fish completion | ✓ implemented | beta | `rfm completion bash`<br>`rfm completion fish`<br>`completions/rfm.bash`<br>`completions/rfm.fish`<br>`src/repo_fleet_manager/cli.py` |
| `cli.plan-apply` — Dry-run and explicit apply model | ✓ implemented | beta | `rfm local plan`<br>`rfm local localize --apply`<br>`src/repo_fleet_manager/cli.py`<br>`src/repo_fleet_manager/localops.py` |
| `cli.structured-output` — Unified text, JSON and JSONL output | ✓ implemented | beta | `rfm --format json config validate`<br>`rfm runtime status --format jsonl`<br>`rfm --format json doctor`<br>`src/repo_fleet_manager/observability.py`<br>`src/repo_fleet_manager/cli.py`<br>`schemas/rfm-event.schema.json`<br>`tests/test_observability.py` |
| `cli.profiles` — Named execution profiles and environment overlays | × missing | not-started | — |

### Configuration and inventory

Central definition of projects, providers, repository lifecycle, Compose and fingerprint behavior.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `config.central-manifest` — Single repo-fleet.json inventory | ✓ implemented | beta | `rfm doctor`<br>`rfm catalog`<br>`src/repo_fleet_manager/config.py`<br>`configs/repo-fleet.example.json` |
| `config.lifecycle-model` — new/upstream/existing repository lifecycle | ✓ implemented | beta | `rfm local plan`<br>`rfm local localize`<br>`src/repo_fleet_manager/config.py`<br>`configs/repo-fleet.lifecycle.example.json`<br>`docs/09-repository-lifecycle.md` |
| `config.schema-validation` — Versioned JSON Schema validation | ✓ implemented | beta | `rfm config --config repo-fleet.json validate --strict`<br>`schemas/repo-fleet.schema.json`<br>`src/repo_fleet_manager/schema.py`<br>`tests/test_schema_migration.py` |
| `config.migrations` — Config schema migrations and backward compatibility | ✓ implemented | beta | `rfm config --config repo-fleet.json migrate`<br>`rfm config --config repo-fleet.json migrate --apply`<br>`src/repo_fleet_manager/schema.py`<br>`docs/02-configuration.md`<br>`MIGRATION.md` |
| `config.overlays` — Profiles, overlays and repository groups | ✓ implemented | beta | `rfm config --config repo-fleet.json --profile ci --group backend render`<br>`rfm git --config repo-fleet.json --group backend status`<br>`src/repo_fleet_manager/profiles.py`<br>`src/repo_fleet_manager/config.py`<br>`schemas/repo-fleet.schema.json`<br>`docs/13-profiles-overlays-and-groups.md`<br>`tests/test_profiles_groups.py` |
| `config.wizard` — Interactive and non-interactive configuration wizard | ✓ implemented | beta | `rfm config wizard --quick --output repo-fleet.json`<br>`rfm config wizard --scan . --advanced --non-interactive --apply`<br>`rfm config wizard --answers answers.json --non-interactive --apply`<br>`src/repo_fleet_manager/wizard.py`<br>`src/repo_fleet_manager/cli.py`<br>`tests/test_config_wizard.py`<br>`docs/16-configuration-wizard.md`<br>`configs/wizard-answers.example.json` |

### Repository lifecycle management

Create, import, localize, mirror and publish repositories across local, GitHub and GitLab targets.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `repo.new` — Create new local repositories and bare remotes | ✓ implemented | beta | `rfm local remotes --apply --seed`<br>`rfm local init --apply`<br>`src/repo_fleet_manager/localops.py` |
| `repo.upstream-local` — Clone or mirror upstream repositories locally | ✓ implemented | beta | `rfm local remotes --mirror-sources --apply`<br>`rfm local localize --apply`<br>`src/repo_fleet_manager/localops.py` |
| `repo.existing-import` — Import existing local worktrees | ✓ implemented | beta | `rfm local localize --apply`<br>`rfm repos publish --only existing`<br>`src/repo_fleet_manager/localops.py`<br>`src/repo_fleet_manager/gitops.py`<br>`tests/test_local_workflow.py` |
| `repo.provider-create` — Create repositories through gh/glab | ✓ implemented | beta | `rfm repos create --provider github --apply`<br>`rfm repos create --provider gitlab --apply`<br>`src/repo_fleet_manager/gitops.py` |
| `repo.provider-publish` — Publish local worktrees and mirrors to personal providers | ✓ implemented | beta | `rfm repos publish --provider github --apply`<br>`rfm repos publish --provider gitlab --apply`<br>`src/repo_fleet_manager/gitops.py`<br>`src/repo_fleet_manager/provider.py`<br>`docs/05-repository-providers.md` |
| `repo.native-fork` — Native GitHub/GitLab fork operation with upstream tracking | ✓ implemented | beta | `rfm repos --config repo-fleet.json fork --provider github --apply`<br>`rfm repos --config repo-fleet.json fork --provider gitlab --apply`<br>`src/repo_fleet_manager/provider.py`<br>`tests/test_provider.py`<br>`docs/05-repository-providers.md` |
| `repo.reconcile` — Desired-state reconciliation and drift repair | ✓ implemented | beta | `rfm repos --config repo-fleet.json reconcile --provider github`<br>`rfm repos --config repo-fleet.json reconcile --provider github --apply`<br>`src/repo_fleet_manager/provider.py`<br>`docs/05-repository-providers.md` |

### Local-only workspace

Operate a complete multi-repository project without GitHub or GitLab after required sources are available.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `local.bare-remotes` — Local file:// bare remotes | ✓ implemented | beta | `rfm local remotes --apply`<br>`src/repo_fleet_manager/localops.py`<br>`docs/08-local-only-workflows.md` |
| `local.materialize` — Materialize workspace from lifecycle config | ✓ implemented | beta | `rfm local plan`<br>`rfm local localize --apply`<br>`src/repo_fleet_manager/localops.py` |
| `local.parent-bootstrap` — Bootstrap after cloning the parent repository | ✓ implemented | beta | `rfm init-project NAME --apply`<br>`rfm bootstrap --config repo-fleet.json verify`<br>`rfm local --config repo-fleet.json bootstrap --apply`<br>`src/repo_fleet_manager/scaffold.py`<br>`src/repo_fleet_manager/localops.py`<br>`docs/14-project-scaffolding-and-bootstrap-lock.md` |
| `local.offline-cache` — Portable offline source/image cache | ✓ implemented | beta | `rfm cache --config repo-fleet.json export --apply`<br>`rfm cache verify FILE.rfm-cache.tar.gz --require-complete`<br>`rfm cache --root TARGET import FILE.rfm-cache.tar.gz --apply`<br>`rfm cache --root TARGET bootstrap FILE.rfm-cache.tar.gz --apply`<br>`src/repo_fleet_manager/cache.py`<br>`src/repo_fleet_manager/cli.py`<br>`tests/test_offline_cache.py`<br>`docs/15-offline-cache-and-air-gapped-bootstrap.md` |
| `local.backup-restore` — Backup and restore local bare remotes and state | ✓ implemented | beta | `rfm local backup --apply`<br>`rfm local verify-backup ARCHIVE`<br>`rfm local restore ARCHIVE --apply`<br>`src/repo_fleet_manager/backup.py`<br>`src/repo_fleet_manager/operations.py`<br>`docs/12-backup-and-restore.md`<br>`tests/test_backup_restore.py` |

### Git and submodule fleet operations

Synchronize submodule metadata and execute Git actions across the repository fleet.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `git.submodule-sync` — Generate and synchronize .gitmodules | ✓ implemented | beta | `rfm submodules sync --apply`<br>`src/repo_fleet_manager/gitops.py` |
| `git.fleet-actions` — Fleet status, pull and push | ✓ implemented | beta | `rfm git status`<br>`rfm git pull --apply`<br>`rfm git push --apply`<br>`src/repo_fleet_manager/gitops.py` |
| `git.dirty-safety` — Dirty worktree, detached HEAD and divergence guards | ✓ implemented | beta | `rfm safety --config repo-fleet.json status`<br>`src/repo_fleet_manager/safety.py`<br>`src/repo_fleet_manager/operations.py`<br>`tests/test_operations.py` |
| `git.dependency-order` — Dependency-aware execution graph | ✓ implemented | beta | `rfm graph --config repo-fleet.json show`<br>`src/repo_fleet_manager/graph.py`<br>`tests/test_graph.py` |
| `git.parallel` — Controlled parallel fleet operations | ✓ implemented | beta | `rfm local --config repo-fleet.json localize --jobs 4 --apply`<br>`rfm git --config repo-fleet.json pull --jobs 4 --apply`<br>`src/repo_fleet_manager/graph.py`<br>`src/repo_fleet_manager/localops.py`<br>`src/repo_fleet_manager/gitops.py`<br>`tests/test_graph.py` |

### Provider integrations

GitHub, GitLab and local provider adapters, authentication and remote URL policies.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `provider.github` — GitHub CLI integration | ✓ implemented | beta | `rfm repos create --provider github`<br>`rfm repos publish --provider github`<br>`src/repo_fleet_manager/provider.py`<br>`src/repo_fleet_manager/gitops.py`<br>`tests/test_provider.py` |
| `provider.gitlab` — GitLab CLI integration | ✓ implemented | beta | `rfm repos create --provider gitlab`<br>`rfm repos publish --provider gitlab`<br>`src/repo_fleet_manager/provider.py`<br>`src/repo_fleet_manager/gitops.py`<br>`tests/test_provider.py` |
| `provider.local` — Local file provider | ✓ implemented | beta | `rfm local remotes`<br>`rfm repos audit --provider local`<br>`src/repo_fleet_manager/localops.py`<br>`src/repo_fleet_manager/config.py` |
| `provider.auth-doctor` — Authentication/session validation | ✓ implemented | beta | `rfm auth --config repo-fleet.json status --verbose`<br>`rfm doctor --config repo-fleet.json --auth --strict-auth`<br>`src/repo_fleet_manager/provider.py`<br>`src/repo_fleet_manager/cli.py`<br>`docs/05-repository-providers.md` |
| `provider.remote-policy` — Per-repository multi-remote and push policy | ~ partial | alpha | `rfm repos publish --remote-name personal`<br>`src/repo_fleet_manager/gitops.py` |

### Runtime, Compose and image integrity

Run local services and compare source state with built container image metadata.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `runtime.compose` — Docker/Podman Compose lifecycle | ✓ implemented | beta | `rfm compose up --apply`<br>`rfm compose down --apply`<br>`rfm compose ps`<br>`src/repo_fleet_manager/compose.py` |
| `runtime.source-fingerprint` — Deterministic source fingerprint metadata | ✓ implemented | beta | `rfm source fingerprint --write`<br>`src/repo_fleet_manager/fingerprint.py`<br>`docs/04-source-fingerprint-and-images.md` |
| `runtime.image-label-verify` — Verify image labels against source fingerprints | ✓ implemented | beta | `rfm images verify`<br>`rfm supply-chain resolve`<br>`rfm supply-chain verify`<br>`src/repo_fleet_manager/images.py`<br>`src/repo_fleet_manager/supply_chain.py`<br>`tests/test_supply_chain.py`<br>`docs/19-supply-chain-provenance.md` |
| `runtime.registry-provenance` — Registry digest, SBOM and signature verification | ✓ implemented | beta | `rfm supply-chain resolve --apply`<br>`rfm supply-chain sbom --apply`<br>`rfm supply-chain scan --apply`<br>`rfm supply-chain verify`<br>`src/repo_fleet_manager/supply_chain.py`<br>`schemas/rfm-provenance.schema.json`<br>`tests/test_supply_chain.py`<br>`docs/19-supply-chain-provenance.md` |
| `runtime.health` — Service health/readiness orchestration | ✓ implemented | beta | `rfm runtime status`<br>`rfm runtime doctor --logs`<br>`rfm runtime wait`<br>`rfm runtime up --apply`<br>`src/repo_fleet_manager/runtime.py`<br>`src/repo_fleet_manager/cli.py`<br>`tests/test_runtime_readiness.py`<br>`docs/17-runtime-health-readiness.md` |

### Reliability and safety

Idempotency, transactions, locking, recovery and traceability for destructive operations.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `safety.dry-run` — Safe dry-run default | ✓ implemented | beta | `rfm local remotes`<br>`rfm repos create`<br>`src/repo_fleet_manager/cli.py` |
| `safety.idempotency` — Idempotent repeat execution | ~ partial | alpha | `rfm local localize --apply`<br>`src/repo_fleet_manager/localops.py`<br>`src/repo_fleet_manager/gitops.py` |
| `safety.transaction` — Transactional apply and rollback | ✓ implemented | beta | `rfm ops --config repo-fleet.json rollback OPERATION_ID`<br>`src/repo_fleet_manager/operations.py`<br>`tests/test_operations.py`<br>`docs/11-operational-safety-and-recovery.md` |
| `safety.lock` — Workspace operation lock | ✓ implemented | beta | `rfm local --config repo-fleet.json localize --apply`<br>`src/repo_fleet_manager/operations.py`<br>`tests/test_operations.py` |
| `safety.journal` — Persistent operation journal and resume | ✓ implemented | beta | `rfm ops --config repo-fleet.json list`<br>`rfm ops --config repo-fleet.json resume OPERATION_ID`<br>`src/repo_fleet_manager/operations.py`<br>`src/repo_fleet_manager/cli.py`<br>`tests/test_operations.py` |

### Security and governance

Credentials, policy enforcement, auditability and supply-chain controls.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `security.secret-guidance` — Avoid secrets in config documentation | ✓ implemented | beta | `rfm config --config repo-fleet.json validate --strict`<br>`rfm auth --config repo-fleet.json status`<br>`src/repo_fleet_manager/schema.py`<br>`src/repo_fleet_manager/provider.py`<br>`docs/11-operational-safety-and-recovery.md` |
| `security.credentials` — Credential profiles and secret-store integration | ~ partial | beta | `rfm auth --config repo-fleet.json status --strict-scopes`<br>`src/repo_fleet_manager/provider.py`<br>`docs/05-repository-providers.md` |
| `security.policy` — Policy-as-code for repository, operation and supply-chain governance | ✓ implemented | beta | `rfm policy check`<br>`rfm policy enforce`<br>`rfm policy explain RULE_ID`<br>`rfm policy exceptions`<br>`src/repo_fleet_manager/policy.py`<br>`src/repo_fleet_manager/cli.py`<br>`schemas/rfm-policy-report.schema.json`<br>`tests/test_policy.py`<br>`docs/20-policy-as-code.md` |
| `security.audit-log` — Structured redacted JSONL audit log | ✓ implemented | beta | `rfm logs list`<br>`rfm logs show RUN_ID`<br>`rfm logs verify RUN_ID`<br>`rfm logs purge --apply`<br>`src/repo_fleet_manager/observability.py`<br>`src/repo_fleet_manager/operations.py`<br>`schemas/rfm-event.schema.json`<br>`tests/test_observability.py`<br>`docs/18-structured-output-and-audit-logging.md` |
| `security.supply-chain` — SBOM, image signing and commit verification | ✓ implemented | beta | `rfm supply-chain verify --require-signature --require-attestation`<br>`rfm policy enforce --rule supply-chain-controls`<br>`src/repo_fleet_manager/supply_chain.py`<br>`src/repo_fleet_manager/policy.py`<br>`schemas/rfm-provenance.schema.json`<br>`tests/test_supply_chain.py`<br>`tests/test_policy.py`<br>`SECURITY.md`<br>`docs/19-supply-chain-provenance.md`<br>`docs/20-policy-as-code.md` |

### Catalog and extensibility

Capability inventory, gap analysis, templates and external developer portal integration.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `catalog.capability-manifest` — Machine-readable RFM capability catalog | ✓ implemented | beta | `rfm catalog --view tree`<br>`rfm catalog --view gaps`<br>`catalog/rfm-service-catalog.json`<br>`src/repo_fleet_manager/service_catalog.py` |
| `catalog.markdown-export` — Markdown and JSON catalog export | ✓ implemented | beta | `rfm catalog --view all --format markdown --output docs/generated/rfm-service-catalog.md`<br>`src/repo_fleet_manager/service_catalog.py`<br>`docs/generated/rfm-service-catalog.md` |
| `catalog.backstage` — Backstage catalog-info.yaml export | → planned | not-started | — |
| `extension.plugins` — Plugin/provider extension API | × missing | not-started | — |
| `extension.templates` — Repository and service scaffolding templates | ✓ implemented | beta | `rfm scaffold templates`<br>`rfm scaffold repository NAME --path PATH --template TEMPLATE --apply`<br>`src/repo_fleet_manager/scaffold.py`<br>`tests/test_scaffold_bootstrap.py`<br>`docs/14-project-scaffolding-and-bootstrap-lock.md` |

### Quality, testing and release

Automated verification, compatibility matrix, packaging and release discipline.

| Capability | Status | Maturity | Commands / evidence |
|---|---|---|---|
| `quality.unit-tests` — Python unit tests | ✓ implemented | beta | `make test`<br>`tests/test_config.py`<br>`tests/test_schema_migration.py`<br>`tests/test_provider.py` |
| `quality.integration-tests` — End-to-end local Git graph tests | ✓ implemented | beta | `make test`<br>`tests/test_local_workflow.py`<br>`tests/test_operations.py` |
| `quality.ci` — CI pipeline and cross-platform matrix | ✓ implemented | beta | `.github/workflows/ci.yml`<br>`.gitlab-ci.yml` |
| `quality.packaging` — Installable Python package and Makefile | ✓ implemented | beta | `make install`<br>`python -m build`<br>`pyproject.toml`<br>`Makefile` |
| `quality.release` — Automated package and GitHub release workflow | ✓ implemented | beta | `make release-check`<br>`make release-artifacts`<br>`.github/workflows/release.yml`<br>`scripts/check_release_version.py`<br>`CHANGELOG.md`<br>`PATCH_NOTES_v0.7.0.md` |

## Prioritized logical gaps

### P0

#### GAP-001 — Versioned config schema and migration engine

**Category:** `reliability` · **Current state:** `implemented`

The config is the desired-state source of truth. Without strict schema validation, typos or incompatible fields can fail midway through destructive operations.

Recommended scope:

- Publish a JSON Schema
- Add schema_version to configs
- Validate before every command
- Provide rfm config migrate and config validate

Acceptance criteria:

- Invalid fields fail before any filesystem change
- Old supported schema versions can be migrated deterministically
- Validation errors include JSON paths and remediation

#### GAP-002 — Transactional apply, operation journal and rollback

**Category:** `recovery` · **Current state:** `implemented`

A multi-repository operation can succeed for some repos and fail for others, leaving an inconsistent workspace with no reliable resume or rollback path.

Recommended scope:

- Create an execution plan with operation IDs
- Persist before/after state
- Support resume and compensating rollback
- Make all mutating commands idempotent

Acceptance criteria:

- Interrupted localize can resume
- Changed remotes and .gitmodules can be restored
- The journal records every command result

#### GAP-003 — Native fork/mirror workflows and provider reconciliation

**Category:** `providers` · **Current state:** `implemented`

Current publish logic creates and pushes repositories but does not fully model native forks, upstream relationships, mirror settings, default branches or provider-side drift.

Recommended scope:

- Use gh repo fork and GitLab fork APIs/CLI
- Set upstream and personal remotes
- Reconcile visibility/default branch/topics/mirror state
- Support provider-side mirror updates

Acceptance criteria:

- Fork lineage is visible on the provider
- upstream and personal remotes are configured consistently
- Audit reports provider drift and can repair it

#### GAP-004 — Workspace safety guards and concurrency lock

**Category:** `safety` · **Current state:** `implemented`

Imports, remote rewrites and bulk pushes need stronger checks for dirty trees, divergence, path collisions and concurrent RFM processes.

Recommended scope:

- Add a .repo-fleet/lock
- Refuse unsafe dirty/diverged operations unless explicitly overridden
- Detect nested/path collisions
- Add --force with explicit reason

Acceptance criteria:

- Two apply processes cannot mutate one workspace
- Dirty or divergent repos are listed before mutation
- Unsafe overrides are recorded in the journal

#### GAP-005 — Authentication profiles and credential diagnostics

**Category:** `security` · **Current state:** `implemented`

Checking only that gh/glab exists is insufficient. The tool must identify account, host, scopes and non-interactive authentication before starting a fleet operation.

Recommended scope:

- Add provider auth check
- Support named accounts/hosts
- Integrate with native credential helpers
- Never persist tokens in repo-fleet.json

Acceptance criteria:

- doctor reports authenticated identity and required scopes
- CI/non-interactive mode fails fast
- Secrets are redacted from all output

#### GAP-006 — Integration tests, dependency graph and controlled parallelism

**Category:** `quality` · **Current state:** `implemented`

Unit tests do not prove that multi-repo, submodule, bare remote, failure and resume scenarios work together. Sequential execution will also become slow at fleet scale.

Recommended scope:

- Build temporary end-to-end Git graphs in tests
- Model depends_on between repos/services
- Execute independent nodes in parallel
- Add CI matrix for Linux Docker and Podman

Acceptance criteria:

- new/upstream/existing scenarios run end to end
- Failures are deterministic and resumable
- Parallel mode preserves readable per-repo logs

### P1

#### GAP-007 — Unified structured output and audit logging

**Category:** `observability` · **Current state:** `implemented`

Automation and support need stable event records rather than mixed human text and command-specific JSON shapes.

Recommended scope:

- Define a common event schema
- Add --format text|json|jsonl
- Write operation logs under .repo-fleet/logs
- Include command, repo, duration and result

Acceptance criteria:

- All commands can emit JSONL
- Sensitive values are redacted
- A failed fleet run can be diagnosed from one log directory

#### GAP-008 — Backup and restore for local remotes and state

**Category:** `recovery` · **Current state:** `implemented`

Local-only mode makes .repo-fleet/remotes valuable infrastructure. Losing it can remove unpublished branches and tags.

Recommended scope:

- Add rfm local backup/restore
- Bundle refs, config, lockfiles and metadata
- Support verification and retention

Acceptance criteria:

- A clean machine can restore the fleet
- Backup integrity is verified
- Unpublished refs are preserved

#### GAP-009 — Profiles, overlays and repository groups

**Category:** `configuration` · **Current state:** `implemented`

Large projects need developer/CI/production differences and selective operations without duplicating the full catalog.

Recommended scope:

- Add config inheritance/overlays
- Define tags and groups
- Support --profile and --group filters
- Render final merged config

Acceptance criteria:

- Base config stays provider-neutral
- Users can operate on a subset
- Merged configuration is inspectable and validated

#### GAP-010 — Portable parent bootstrap and repository scaffolding

**Category:** `developer-experience` · **Current state:** `implemented`

After cloning the parent repo, new modules should be created from consistent templates and the root repository should declare the exact bootstrap contract.

Recommended scope:

- Add rfm init-project
- Add repo/service templates
- Generate README, license, CI and baseline files
- Create a portable bootstrap lockfile

Acceptance criteria:

- A new developer runs one documented command
- New repos follow the same conventions
- Bootstrap does not depend on the original author's filesystem

#### GAP-011 — Offline source and image cache

**Category:** `offline` · **Current state:** `implemented`

Local mode is only fully offline after upstream repos and container images have already been fetched.

Recommended scope:

- Export/import Git bundle or mirror pack
- Save/load OCI images
- Track cache manifest and checksums
- Support air-gapped bootstrap

Acceptance criteria:

- Workspace and images can be prepared on a connected machine
- Air-gapped import requires no provider access
- Cache completeness is validated before bootstrap

#### GAP-012 — Container registry provenance, SBOM and signatures

**Category:** `supply-chain` · **Current state:** `implemented`

Source labels alone do not establish which registry digest was deployed or whether the image and dependencies are trusted.

Recommended scope:

- Resolve immutable registry digests
- Generate/attach SBOM
- Verify cosign signatures/attestations
- Compare source lock to image provenance

Acceptance criteria:

- Verification works without mutable tags
- Unsigned/untrusted images can be blocked by policy
- Reports identify exact source and image digests

#### GAP-013 — Service health, readiness and ordered runtime startup

**Category:** `runtime` · **Current state:** `implemented`

Compose up returning successfully does not mean the development platform is usable. Dependencies need readiness checks and actionable diagnostics.

Recommended scope:

- Read Compose health checks
- Add configurable readiness probes
- Wait on dependency graph
- Provide rfm runtime doctor

Acceptance criteria:

- Bootstrap waits for required services
- Failures show logs and remediation
- Status distinguishes running from ready

#### GAP-018 — Interactive configuration wizard

**Category:** `developer-experience` · **Current state:** `implemented`

Hand-editing a large repository inventory is error-prone and prevents new users from safely adopting profiles, local workflows, Compose and offline cache settings.

Recommended scope:

- Add quick and advanced interactive modes
- Scan Git repositories, submodules and Compose hints
- Support resumable and non-interactive answer files
- Validate, diff, back up and atomically write configuration

Acceptance criteria:

- A new user can generate a strict-valid config without editing JSON
- Existing projects can be scanned without storing absolute personal paths or secrets
- Interrupted sessions can resume and CI generation is repeatable
- An invalid result never replaces the existing configuration

### P2

#### GAP-014 — Policy-as-code for repository and supply-chain governance

**Category:** `governance` · **Current state:** `implemented`

Teams need enforceable rules for visibility, branches, remotes, signing, image sources and destructive actions.

Recommended scope:

- Define policy rules in config or Rego
- Add check/enforce modes
- Support exceptions with expiry and reason

Acceptance criteria:

- Policy violations are visible in audit
- CI can block non-compliant state
- Exceptions are explicit and traceable

#### GAP-015 — Backstage and external service catalog export

**Category:** `catalog` · **Current state:** `planned`

The internal RFM catalog is useful for the CLI, while larger organizations often need ownership and dependency data in a developer portal.

Recommended scope:

- Export catalog-info.yaml
- Map repositories/services to System/Component/Resource
- Include owners, lifecycle and links

Acceptance criteria:

- Generated entities pass Backstage validation
- Dependencies and ownership remain generated from one source of truth

#### GAP-016 — Stable plugin API for providers and workflows

**Category:** `extensibility` · **Current state:** `missing`

Hard-coding every provider, runtime and artifact backend in the core will make RFM difficult to extend and test.

Recommended scope:

- Define provider/runtime/catalog interfaces
- Load plugins through Python entry points
- Publish compatibility contract

Acceptance criteria:

- A provider can be added without editing cli.py
- Plugin failures are isolated and reported
- Version compatibility is checked

#### GAP-017 — Automated release and compatibility discipline

**Category:** `release` · **Current state:** `resolved`

Manual patch notes are useful but do not guarantee reproducible packages, changelogs or compatibility across Python, Git and container engines.

Recommended scope:

- Automate tests/build/tag/release
- Generate changelog from conventional commits
- Publish checksums and package metadata
- Maintain compatibility matrix

Acceptance criteria:

- A tagged release is reproducible
- Artifacts include checksums
- Supported versions are tested and documented

## Regeneration

```bash
rfm catalog --view all --format markdown --output docs/generated/rfm-service-catalog.md
rfm catalog --view gaps --format markdown --output reports/gap-analysis.md
```
