from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_fleet_manager.config import load_config
from repo_fleet_manager.fingerprint import build_metadata
from repo_fleet_manager.schema import validate_config_data
from repo_fleet_manager.shell import RunResult
from repo_fleet_manager.supply_chain import (
    generate_sboms,
    load_manifest,
    resolve_supply_chain,
    scan_sboms,
    verify_supply_chain,
)


DIGEST = "sha256:" + "a" * 64


class FakeRunner:
    def __init__(self, source_digest: str, *, mismatch: bool = False, critical: bool = False):
        self.source_digest = "deadbeefdeadbeef" if mismatch else source_digest
        self.critical = critical
        self.commands: list[list[str]] = []

    def __call__(self, command, cwd=None, check=False):
        command = [str(item) for item in command]
        self.commands.append(command)
        text = " ".join(command)
        if "config --format json" in text:
            return RunResult(0, json.dumps({"services": {"api": {"image": "registry.example/api:1.0"}}}), "")
        if command[:3] == ["docker", "image", "inspect"] and "RepoDigests" in command[-1]:
            return RunResult(0, json.dumps([f"registry.example/api@{DIGEST}"]), "")
        if command[:3] == ["docker", "image", "inspect"] and "source-digest" in command[-1]:
            return RunResult(0, self.source_digest, "")
        if command[:3] == ["docker", "image", "inspect"] and "build-sha" in command[-1]:
            return RunResult(0, "abc123", "")
        if command and command[0] == "syft":
            return RunResult(0, json.dumps({"bomFormat": "CycloneDX", "components": [{"name": "demo"}]}), "")
        if command and command[0] == "grype":
            severity = "Critical" if self.critical else "Low"
            return RunResult(0, json.dumps({"matches": [{"vulnerability": {"id": "CVE-1", "severity": severity}}]}), "")
        if command[:2] in (["cosign", "verify"], ["cosign", "verify-attestation"]):
            return RunResult(0, "{}", "")
        return RunResult(1, "", f"unexpected command: {command}")


class SupplyChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        service = self.root / "services/api/src"
        service.mkdir(parents=True)
        (service / "app.py").write_text("print('ok')\n", encoding="utf-8")
        self.config_path = self.root / "repo-fleet.json"
        config = {
            "schema_version": "1.0.0",
            "project": {"name": "supply-demo", "default_provider": "local", "default_branch": "main", "build_dir": ".repo-fleet/build"},
            "providers": {"local": {"type": "local", "driver": "local", "namespace": ".repo-fleet/remotes", "cli": "git", "url_template": "file://{root}/{namespace}/{repo}.git"}},
            "repositories": [
                {"path": ".", "repo": "supply-demo", "kind": "root", "provider": "local", "branch": "main", "source_type": "existing", "depends_on": [], "tags": ["root"]},
                {"path": "services/api", "repo": "supply-api", "kind": "service", "provider": "local", "branch": "main", "source_type": "existing", "existing_path": "services/api", "compose_service": "api", "depends_on": [], "tags": ["service"]},
            ],
            "compose": {"file": "compose.yml", "bin": "fake-compose", "engine": "docker"},
            "local": {"remotes_dir": ".repo-fleet/remotes", "workspace_mode": "submodules", "operations_dir": ".repo-fleet/operations", "lock_file": ".repo-fleet/lock", "default_jobs": 1},
            "fingerprint": {"algorithm": "sha256", "short_length": 16},
            "supply_chain": {
                "output_dir": ".repo-fleet/supply-chain",
                "engine": "docker",
                "digest_resolver": "engine",
                "sbom_format": "cyclonedx-json",
                "vulnerability_threshold": "high",
                "require_immutable_digest": True,
                "require_source_label": True,
                "require_sbom": True,
                "require_scan": True,
                "require_signature": True,
                "require_attestation": True,
                "cosign": {"key": "cosign.pub", "attestation_type": "cyclonedx"},
            },
        }
        self.config_path.write_text(json.dumps(config), encoding="utf-8")
        (self.root / "compose.yml").write_text("services:\n  api:\n    image: registry.example/api:1.0\n", encoding="utf-8")
        self.config = load_config(self.config_path)
        self.source_digest = build_metadata(self.config, self.root)["services"][0]["source_digest"]

    def tearDown(self):
        self.temp.cleanup()

    def _resolve(self, runner: FakeRunner):
        report = resolve_supply_chain(self.config, self.root, write=True, runner=runner)
        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual(report.services[0].digest, DIGEST)
        self.assertIn("@sha256:", report.services[0].resolved_reference)

    def test_full_provenance_workflow(self):
        runner = FakeRunner(self.source_digest)
        self._resolve(runner)
        with patch("repo_fleet_manager.supply_chain.command_exists", return_value=True):
            self.assertEqual(generate_sboms(self.config, self.root, apply=True, runner=runner), 0)
            self.assertEqual(scan_sboms(self.config, self.root, apply=True, runner=runner), 0)
            self.assertEqual(verify_supply_chain(self.config, self.root, runner=runner), 0)
        manifest = load_manifest(self.config, self.root)
        service = manifest["services"][0]
        self.assertTrue(service["immutable"])
        self.assertTrue(service["source_match"])
        self.assertTrue((self.root / ".repo-fleet/supply-chain" / service["sbom"]["path"]).exists())
        self.assertTrue((self.root / ".repo-fleet/supply-chain" / service["scan"]["path"]).exists())
        self.assertTrue(any(command[:2] == ["cosign", "verify"] for command in runner.commands))
        self.assertTrue(any(command[:2] == ["cosign", "verify-attestation"] for command in runner.commands))

    def test_source_label_mismatch_fails_resolution(self):
        report = resolve_supply_chain(self.config, self.root, runner=FakeRunner(self.source_digest, mismatch=True))
        self.assertFalse(report.ok)
        self.assertIn("does not match", " ".join(report.services[0].errors))

    def test_vulnerability_threshold_blocks_critical(self):
        runner = FakeRunner(self.source_digest, critical=True)
        self._resolve(runner)
        with patch("repo_fleet_manager.supply_chain.command_exists", return_value=True):
            self.assertEqual(generate_sboms(self.config, self.root, apply=True, runner=runner), 0)
            self.assertEqual(scan_sboms(self.config, self.root, apply=True, runner=runner), 2)
            self.assertEqual(verify_supply_chain(self.config, self.root, runner=runner), 2)

    def test_signature_enforcement_requires_trust_policy(self):
        raw = json.loads(self.config_path.read_text())
        raw["supply_chain"]["cosign"] = {}
        issues = validate_config_data(raw)
        self.assertIn("missing-cosign-trust-policy", {item.code for item in issues})

    def test_sbom_refuses_mutable_target(self):
        runner = FakeRunner(self.source_digest)
        self._resolve(runner)
        manifest = load_manifest(self.config, self.root)
        manifest["services"][0]["resolved_reference"] = "registry.example/api:1.0"
        path = self.root / ".repo-fleet/supply-chain/provenance.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with patch("repo_fleet_manager.supply_chain.command_exists", return_value=True):
            self.assertEqual(generate_sboms(self.config, self.root, apply=True, runner=runner), 2)

    def test_manifest_artifact_path_cannot_escape_output_directory(self):
        runner = FakeRunner(self.source_digest)
        self._resolve(runner)
        manifest = load_manifest(self.config, self.root)
        manifest["services"][0]["sbom"] = {"path": "../../outside.json", "sha256": "0" * 64}
        path = self.root / ".repo-fleet/supply-chain/provenance.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(verify_supply_chain(self.config, self.root, runner=runner), 2)

    def test_service_policy_can_require_signature(self):
        raw = json.loads(self.config_path.read_text())
        raw["supply_chain"]["require_signature"] = False
        raw["supply_chain"]["require_attestation"] = False
        raw["supply_chain"]["services"] = {"api": {"require_signature": True}}
        self.config_path.write_text(json.dumps(raw), encoding="utf-8")
        config = load_config(self.config_path)
        runner = FakeRunner(self.source_digest)
        report = resolve_supply_chain(config, self.root, write=True, runner=runner)
        self.assertTrue(report.ok)
        with patch("repo_fleet_manager.supply_chain.command_exists", return_value=True):
            self.assertEqual(generate_sboms(config, self.root, apply=True, runner=runner), 0)
            self.assertEqual(scan_sboms(config, self.root, apply=True, runner=runner), 0)
            self.assertEqual(verify_supply_chain(config, self.root, runner=runner), 0)
        self.assertTrue(any(command[:2] == ["cosign", "verify"] for command in runner.commands))


if __name__ == "__main__":
    unittest.main()
