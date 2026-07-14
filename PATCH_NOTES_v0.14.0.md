# Repo Fleet Manager v0.14.0 patch notes

## Release identity

- Base revision: `c7bbd31ccce34086509ec6d0e098983c917999cb`
- Base version: `0.13.0`
- Target version: `0.14.0`
- Config schema version: `1.0.0` (unchanged)
- Provenance manifest schema: `1.0.0`
- Primary scope: GAP-012 — container registry provenance, SBOM and signatures

## Added

- `rfm supply-chain resolve`, `sbom`, `scan`, `verify`, `report` and `collect`.
- Immutable digest resolution through Docker, Podman or Skopeo.
- Source fingerprint comparison with image labels.
- CycloneDX/SPDX SBOM generation through Syft.
- Grype vulnerability reports with configurable inclusive severity thresholds.
- Cosign key-based or keyless signature and attestation verification.
- Per-service signature and attestation enforcement.
- Versioned provenance manifest with SHA-256 inventory and safe relative paths.

## Security

- Mutable tags cannot satisfy verification policy.
- Signature/attestation enforcement fails closed without a trust policy.
- Manifest path traversal and absolute artifact paths are rejected.
- Verification is performed against `image@sha256:digest`.

## Validation performed

- Existing regression suite
- Digest and source-label matching
- Mutable reference rejection
- SBOM generation and checksum validation
- Vulnerability threshold enforcement
- Cosign signature and attestation policy
- Manifest schema and path traversal rejection
- Strict config, completion, documentation and catalog checks
- Wheel and source distribution smoke tests
