# Supply-chain provenance, SBOM and image trust

RFM 0.14.0 establishes an auditable link between the current service source, an immutable registry digest, an SBOM, a vulnerability report and an optional Cosign trust policy.

## Workflow

```bash
rfm supply-chain --config repo-fleet.json resolve
rfm supply-chain --config repo-fleet.json resolve --apply
rfm supply-chain --config repo-fleet.json sbom --apply
rfm supply-chain --config repo-fleet.json scan --fail-on high --apply
rfm supply-chain --config repo-fleet.json verify
```

The combined workflow is:

```bash
rfm supply-chain --config repo-fleet.json collect --fail-on high
rfm supply-chain --config repo-fleet.json collect --fail-on high --apply
rfm supply-chain --config repo-fleet.json verify
```

Mutation commands remain dry-run by default. Generated files are stored below `.repo-fleet/supply-chain` unless `supply_chain.output_dir` or `--output-dir` changes the location.

## Configuration

```json
{
  "supply_chain": {
    "output_dir": ".repo-fleet/supply-chain",
    "engine": "auto",
    "digest_resolver": "auto",
    "sbom_format": "cyclonedx-json",
    "vulnerability_threshold": "high",
    "require_immutable_digest": true,
    "require_source_label": true,
    "require_sbom": true,
    "require_scan": true,
    "require_signature": true,
    "require_attestation": true,
    "cosign": {
      "certificate_identity": "https://github.com/example/platform/.github/workflows/release.yml@refs/tags/*",
      "certificate_oidc_issuer": "https://token.actions.githubusercontent.com",
      "attestation_type": "cyclonedx"
    },
    "services": {
      "api": {
        "image": "registry.example.com/platform/api:1.4.0",
        "require_signature": true,
        "require_attestation": true
      }
    }
  }
}
```

A public-key or KMS-based policy can use `cosign.key` instead of certificate identity and issuer. RFM fails closed when signature or attestation enforcement is enabled without a trust policy.

## Digest resolution

`resolve` discovers images from Compose and optional `supply_chain.services` overrides. It accepts an already immutable reference, resolves local `RepoDigests` through Docker/Podman, or uses Skopeo when configured and available. The provenance manifest stores only immutable `name@sha256:...` references for verification.

RFM also compares the image labels `io.repo-fleet.source-digest` and `io.repo-fleet.build-sha` with the current source fingerprint. This detects an image built from source other than the checked-out workspace.

## SBOM and vulnerability scanning

Syft generates CycloneDX JSON or SPDX JSON:

```bash
rfm supply-chain --config repo-fleet.json sbom --format cyclonedx-json --apply
```

Grype scans the generated SBOM and records severity counts:

```bash
rfm supply-chain --config repo-fleet.json scan --fail-on high --apply
```

The threshold is inclusive: `--fail-on high` rejects High and Critical findings. SBOM and scan files are recorded with SHA-256 checksums in `provenance.json`.

## Signature and attestation verification

```bash
rfm supply-chain --config repo-fleet.json verify \
  --require-signature \
  --require-attestation
```

Key-based verification:

```bash
rfm supply-chain --config repo-fleet.json verify \
  --key cosign.pub \
  --require-signature
```

Keyless verification:

```bash
rfm supply-chain --config repo-fleet.json verify \
  --certificate-identity 'https://github.com/example/platform/.github/workflows/release.yml@refs/tags/*' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  --require-signature \
  --require-attestation
```

Verification is always performed against the immutable digest, never a mutable tag.

## Manifest safety

`provenance.json` is validated against `schemas/rfm-provenance.schema.json`. Referenced SBOM and scan paths must be relative and remain inside the configured output directory. Absolute paths and `..` traversal are rejected. Artifact checksums are verified before policy evaluation.

## Reports and CI

```bash
rfm supply-chain --config repo-fleet.json report
rfm --format json supply-chain --config repo-fleet.json verify
rfm --format jsonl supply-chain --config repo-fleet.json verify
```

A verification failure exits with code `2`, allowing CI to block mutable, unsigned, unattested, source-mismatched or vulnerable images.

## Governance gate

Supply-chain verification can be made part of the broader Policy-as-Code gate. `supply-chain.registry` restricts registries, while `supply-chain.requirements` checks that immutable digest, source label, SBOM, scan, signature and attestation requirements are enabled and represented in the provenance manifest.

```bash
rfm policy --config repo-fleet.json enforce --rule approved-registries
rfm policy --config repo-fleet.json enforce --rule supply-chain-controls
```

See [Policy-as-Code governance](20-policy-as-code.md).
