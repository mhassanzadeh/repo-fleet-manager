from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from repo_fleet_manager.cli import main
from repo_fleet_manager.config import load_config
from repo_fleet_manager.policy import (
    PolicyEnforcementError,
    enforce_operation_policy,
    evaluate_policy,
    explain_rule,
    list_policy_exceptions, validate_policy_report,
)
from repo_fleet_manager.schema import validate_config_data
from repo_fleet_manager.shell import RunResult


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Policy Test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "policy@example.invalid"], cwd=self.root, check=True)
        (self.root / "README.md").write_text("demo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=self.root, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "remote", "add", "origin", "git@github.com:example/policy-demo.git"], cwd=self.root, check=True)
        self.config_path = self.root / "repo-fleet.json"
        self.raw = {
            "schema_version": "1.0.0",
            "project": {
                "name": "policy-demo",
                "default_provider": "github",
                "default_branch": "main",
                "build_dir": ".repo-fleet/build",
            },
            "providers": {
                "github": {
                    "type": "remote",
                    "driver": "github",
                    "namespace": "example",
                    "host": "github.com",
                    "cli": "gh",
                    "url_template": "git@{host}:{namespace}/{repo}.git",
                }
            },
            "repositories": [
                {
                    "path": ".",
                    "repo": "policy-demo",
                    "kind": "root",
                    "provider": "github",
                    "branch": "main",
                    "visibility": "public",
                    "source_type": "existing",
                    "depends_on": [],
                    "tags": ["critical"],
                }
            ],
            "local": {
                "remotes_dir": ".repo-fleet/remotes",
                "workspace_mode": "submodules",
                "operations_dir": ".repo-fleet/operations",
                "lock_file": ".repo-fleet/lock",
                "default_jobs": 1,
            },
            "policy": {
                "enabled": True,
                "mode": "enforce",
                "fail_on": "error",
                "rules": [
                    {
                        "id": "critical-private",
                        "type": "repository.visibility",
                        "severity": "error",
                        "selectors": {"tags": ["critical"]},
                        "parameters": {"allowed": ["private"]},
                    },
                    {
                        "id": "approved-host",
                        "type": "repository.remote-host",
                        "severity": "error",
                        "parameters": {"allowed_hosts": ["github.com"]},
                    },
                    {
                        "id": "protect-publish",
                        "type": "operation.guard",
                        "severity": "error",
                        "parameters": {"actions": ["repos publish", "compose down"], "require_reason": True},
                    },
                ],
                "exceptions": [],
            },
        }
        self.config_path.write_text(json.dumps(self.raw), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def config(self):
        return load_config(self.config_path)

    def test_policy_report_matches_packaged_schema(self):
        report = evaluate_policy(self.config(), self.root, mode="check")
        self.assertEqual(validate_policy_report(report.to_dict()), [])

    def test_check_reports_violation_without_blocking(self):
        report = evaluate_policy(self.config(), self.root, mode="check")
        self.assertFalse(report.ok)
        self.assertEqual(report.noncompliant_count, 1)
        self.assertEqual(report.blocking_count, 0)
        self.assertEqual(report.violations[0].rule_id, "critical-private")

    def test_enforce_blocks_violation(self):
        report = evaluate_policy(self.config(), self.root, mode="enforce")
        self.assertFalse(report.ok)
        self.assertEqual(report.blocking_count, 1)

    def test_active_exception_suppresses_violation(self):
        raw = json.loads(self.config_path.read_text())
        raw["policy"]["exceptions"] = [{
            "id": "temporary-public",
            "rule_id": "critical-private",
            "reason": "Migration window approved by security",
            "approved_by": "security@example.invalid",
            "expires_at": "2099-01-01T00:00:00Z",
            "repositories": ["policy-demo"],
            "ticket": "SEC-42",
        }]
        self.config_path.write_text(json.dumps(raw), encoding="utf-8")
        report = evaluate_policy(self.config(), self.root, mode="enforce")
        self.assertTrue(report.ok)
        self.assertEqual(report.blocking_count, 0)
        self.assertEqual(report.violations[0].exception_id, "temporary-public")
        self.assertEqual(len(report.applied_exceptions), 1)

    def test_expired_exception_does_not_suppress(self):
        raw = json.loads(self.config_path.read_text())
        raw["policy"]["exceptions"] = [{
            "id": "expired-public",
            "rule_id": "critical-private",
            "reason": "Old migration exception",
            "approved_by": "security@example.invalid",
            "expires_at": "2020-01-01T00:00:00Z",
            "repositories": ["policy-demo"],
        }]
        self.config_path.write_text(json.dumps(raw), encoding="utf-8")
        report = evaluate_policy(self.config(), self.root, mode="enforce")
        self.assertFalse(report.ok)
        self.assertEqual(len(report.expired_exceptions), 1)
        self.assertIsNone(report.violations[0].exception_id)

    def test_operation_guard_requires_reason(self):
        config = self.config()
        with self.assertRaises(PolicyEnforcementError):
            enforce_operation_policy(config, self.root, "repos publish", reason=None, force=False)
        # Visibility still violates, so constrain the run to an operation-only config.
        raw = json.loads(self.config_path.read_text())
        raw["repositories"][0]["visibility"] = "private"
        self.config_path.write_text(json.dumps(raw), encoding="utf-8")
        config = self.config()
        report = enforce_operation_policy(config, self.root, "repos publish", reason="approved release", force=False)
        self.assertIsNotNone(report)
        self.assertTrue(report.ok)

    def test_remote_host_and_signed_head_rules(self):
        raw = json.loads(self.config_path.read_text())
        raw["repositories"][0]["visibility"] = "private"
        raw["policy"]["rules"].append({
            "id": "signed-head",
            "type": "repository.signed-head",
            "severity": "warning",
            "parameters": {"accepted_statuses": ["G", "U"]},
        })
        self.config_path.write_text(json.dumps(raw), encoding="utf-8")
        report = evaluate_policy(self.config(), self.root, mode="enforce", fail_on="warning")
        ids = {item.rule_id for item in report.violations}
        self.assertNotIn("approved-host", ids)
        self.assertIn("signed-head", ids)

    def test_schema_rejects_unknown_exception_rule(self):
        raw = json.loads(self.config_path.read_text())
        raw["policy"]["exceptions"] = [{
            "id": "bad",
            "rule_id": "missing-rule",
            "reason": "Approved temporary exception",
            "approved_by": "security@example.invalid",
            "expires_at": "2099-01-01T00:00:00Z",
        }]
        codes = {item.code for item in validate_config_data(raw)}
        self.assertIn("unknown-policy-rule", codes)

    def test_explain_and_exception_listing(self):
        payload = explain_rule(self.config(), "critical-private")
        self.assertEqual(payload["rule"]["type"], "repository.visibility")
        self.assertEqual(list_policy_exceptions(self.config()), [])

    def test_mutation_is_blocked_before_compose_execution(self):
        raw = json.loads(self.config_path.read_text())
        raw["repositories"][0]["visibility"] = "private"
        raw["compose"] = {"file": "compose.yml", "bin": "definitely-not-installed-compose", "engine": "docker"}
        self.config_path.write_text(json.dumps(raw), encoding="utf-8")
        (self.root / "compose.yml").write_text("services: {}\n", encoding="utf-8")
        (self.root / "compose.yml").write_text("services: {}\n", encoding="utf-8")
        output = StringIO()
        with redirect_stdout(output):
            code = main(["compose", "--config", str(self.config_path), "--root", str(self.root), "--apply", "down"])
        self.assertEqual(code, 2)
        self.assertFalse((self.root / ".repo-fleet/operations").exists())

    def test_cli_check_and_enforce_exit_codes(self):
        check_output = StringIO()
        with redirect_stdout(check_output):
            check_code = main(["policy", "--config", str(self.config_path), "--root", str(self.root), "check"])
        self.assertEqual(check_code, 0)
        self.assertIn("critical-private", check_output.getvalue())
        enforce_output = StringIO()
        with redirect_stdout(enforce_output):
            enforce_code = main(["policy", "--config", str(self.config_path), "--root", str(self.root), "enforce"])
        self.assertEqual(enforce_code, 2)

    def test_rego_adapter_converts_denials(self):
        raw = json.loads(self.config_path.read_text())
        raw["repositories"][0]["visibility"] = "private"
        raw["policy"]["rego"] = {"enabled": True, "policy_path": "policy", "query": "data.rfm.deny"}
        self.config_path.write_text(json.dumps(raw), encoding="utf-8")
        (self.root / "policy").write_text("package rfm\n", encoding="utf-8")
        opa_payload = {"result": [{"expressions": [{"value": [{"rule_id": "rego-demo", "severity": "error", "subject": "policy-demo", "message": "denied by Rego"}]}]}]}
        with patch("repo_fleet_manager.policy.command_exists", return_value=True), patch(
            "repo_fleet_manager.policy._opa_run", return_value=RunResult(0, json.dumps(opa_payload), "")
        ):
            report = evaluate_policy(self.config(), self.root, mode="enforce")
        self.assertFalse(report.ok)
        self.assertIn("rego-demo", {item.rule_id for item in report.violations})


if __name__ == "__main__":
    unittest.main()
