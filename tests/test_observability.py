from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from repo_fleet_manager.cli import main
from repo_fleet_manager.config import load_config
from repo_fleet_manager.observability import AuditSession, correlate_operation, redact, redact_argv, verify_log
from repo_fleet_manager.shell import run


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "configs" / "repo-fleet.example.json"


class ObservabilityTests(unittest.TestCase):
    def test_redaction_covers_nested_values_argv_and_urls(self) -> None:
        value = {
            "token": "ghp_abcdefghijklmnopqrstuvwxyz123456",
            "nested": {"client_secret": "hidden", "url": "https://user:pass@example.test/repo"},
            "safe": "visible",
        }
        cleaned = redact(value)
        self.assertEqual(cleaned["token"], "***")
        self.assertEqual(cleaned["nested"]["client_secret"], "***")
        self.assertEqual(cleaned["nested"]["url"], "https://user:***@example.test/repo")
        self.assertEqual(cleaned["safe"], "visible")
        self.assertEqual(redact({"tenant_credential": "value"}, ["tenant_credential"])["tenant_credential"], "***")
        argv = redact_argv(["cmd", "--token", "abc", "PASSWORD=secret", "--api-key=value"])
        self.assertEqual(argv, ["cmd", "--token", "***", "PASSWORD=***", "--api-key=***"])

    def test_observability_config_supports_profile_overlays(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "repo-fleet.json"
            data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
            data.setdefault("profiles", {})["quiet"] = {"observability": {"audit_enabled": False, "retention_days": 7}}
            path.write_text(json.dumps(data), encoding="utf-8")
            cfg = load_config(path, profiles=["quiet"])
            self.assertFalse(cfg.observability["audit_enabled"])
            self.assertEqual(cfg.observability["retention_days"], 7)

    def test_real_cli_enables_audit_logging_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            config = base / "repo-fleet.json"
            config.write_bytes(EXAMPLE.read_bytes())
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            result = subprocess.run(
                [sys.executable, "-m", "repo_fleet_manager", "config", "--config", str(config), "--root", str(base), "validate", "--strict"],
                cwd=base, env=env, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            logs = list((base / ".repo-fleet/logs").glob("*.jsonl"))
            self.assertEqual(len(logs), 1)
            self.assertTrue(verify_log(logs[0])["valid"])

    def test_unified_json_envelope_and_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            config = base / "repo-fleet.json"
            config.write_bytes(EXAMPLE.read_bytes())
            logs = base / "audit"
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main([
                    "config", "--config", str(config), "--root", str(base), "validate", "--strict",
                    "--format", "json", "--audit-log", "--log-dir", str(logs), "--run-id", "json-envelope-test",
                ])
            self.assertEqual(rc, 0, output.getvalue())
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema_version"], "1.0.0")
            self.assertEqual(payload["run_id"], "json-envelope-test")
            self.assertEqual(payload["status"], "succeeded")
            self.assertTrue(payload["result"]["valid"])
            log_path = logs / "json-envelope-test.jsonl"
            self.assertTrue(log_path.exists())
            report = verify_log(log_path)
            self.assertTrue(report["valid"], report["errors"])
            self.assertGreaterEqual(report["events"], 3)

    def test_jsonl_output_is_one_event_per_line(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            config = base / "repo-fleet.json"
            config.write_bytes(EXAMPLE.read_bytes())
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main([
                    "config", "--config", str(config), "validate", "--strict",
                    "--format=jsonl", "--no-audit-log", "--run-id=jsonl-test",
                ])
            self.assertEqual(rc, 0)
            events = [json.loads(line) for line in output.getvalue().splitlines() if line]
            self.assertEqual(events[0]["type"], "run.started")
            self.assertEqual(events[-1]["type"], "run.completed")
            self.assertEqual(events[-1]["exit_code"], 0)
            self.assertTrue(any(event["type"] == "command.output" for event in events))
            self.assertTrue(all(event["run_id"] == "jsonl-test" for event in events))

    def test_legacy_json_flag_keeps_original_payload_shape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "repo-fleet.json"
            config.write_bytes(EXAMPLE.read_bytes())
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(["config", "--config", str(config), "validate", "--strict", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(output.getvalue())
            self.assertIn("valid", payload)
            self.assertNotIn("run_id", payload)

    def test_operation_correlation_is_written_to_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with AuditSession("test mutation", ["test", "--token", "secret"], root, root / "logs", enabled=True, run_id="correlation") as session:
                correlate_operation("operation-123")
                session.complete(0)
            events = [json.loads(line) for line in (root / "logs/correlation.jsonl").read_text().splitlines()]
            self.assertTrue(any(event["type"] == "operation.correlated" for event in events))
            self.assertEqual(events[-1]["operation_id"], "operation-123")
            self.assertNotIn("secret", json.dumps(events))

    def test_subprocess_events_include_exit_code_and_redacted_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with AuditSession("process test", ["process-test"], root, root / "logs", enabled=True, run_id="process-run") as session:
                result = run(["python3", "-c", "print('token=secret-value')"])
                self.assertEqual(result.code, 0)
                session.complete(0)
            events = [json.loads(line) for line in (root / "logs/process-run.jsonl").read_text().splitlines()]
            completed = [event for event in events if event["type"] == "process.completed"]
            self.assertEqual(len(completed), 1)
            self.assertEqual(completed[0]["exit_code"], 0)
            self.assertNotIn("secret-value", json.dumps(completed))

    def test_logs_commands_list_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logs = root / "logs"
            with AuditSession("doctor", ["doctor"], root, logs, enabled=True, run_id="doctor-run") as session:
                session.emit("doctor.check", data={"ok": True})
                session.complete(0)
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(["logs", "--root", str(root), "--log-dir", str(logs), "list", "--json"])
            self.assertEqual(rc, 0)
            rows = json.loads(output.getvalue())
            self.assertEqual(rows[0]["run_id"], "doctor-run")
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(["logs", "--root", str(root), "--log-dir", str(logs), "verify", "doctor-run", "--json"])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(output.getvalue())["valid"])


if __name__ == "__main__":
    unittest.main()
