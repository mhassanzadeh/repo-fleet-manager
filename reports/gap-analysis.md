# Repo Fleet Manager logical gap analysis

> Catalog version `0.16.0` · 18 prioritized gaps

## P0

### GAP-001 — Versioned config schema and migration engine

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

### GAP-002 — Transactional apply, operation journal and rollback

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

### GAP-003 — Native fork/mirror workflows and provider reconciliation

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

### GAP-004 — Workspace safety guards and concurrency lock

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

### GAP-005 — Authentication profiles and credential diagnostics

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

### GAP-006 — Integration tests, dependency graph and controlled parallelism

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

## P1

### GAP-007 — Unified structured output and audit logging

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

### GAP-008 — Backup and restore for local remotes and state

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

### GAP-009 — Profiles, overlays and repository groups

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

### GAP-010 — Portable parent bootstrap and repository scaffolding

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

### GAP-011 — Offline source and image cache

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

### GAP-012 — Container registry provenance, SBOM and signatures

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

### GAP-013 — Service health, readiness and ordered runtime startup

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

### GAP-018 — Interactive configuration wizard

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

## P2

### GAP-014 — Policy-as-code for repository and supply-chain governance

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

### GAP-015 — Backstage and external service catalog export

**Category:** `catalog` · **Current state:** `planned`

The internal RFM catalog is useful for the CLI, while larger organizations often need ownership and dependency data in a developer portal.

Recommended scope:

- Export catalog-info.yaml
- Map repositories/services to System/Component/Resource
- Include owners, lifecycle and links

Acceptance criteria:

- Generated entities pass Backstage validation
- Dependencies and ownership remain generated from one source of truth

### GAP-016 — Stable plugin API for providers and workflows

**Category:** `extensibility` · **Current state:** `implemented`

Hard-coding every provider, runtime and artifact backend in the core will make RFM difficult to extend and test.

Recommended scope:

- Define provider/runtime/catalog interfaces
- Load plugins through Python entry points
- Publish compatibility contract

Acceptance criteria:

- A provider can be added without editing cli.py
- Plugin failures are isolated and reported
- Version compatibility is checked

### GAP-017 — Automated release and compatibility discipline

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

