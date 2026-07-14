from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from repo_fleet_manager.cli import main
from repo_fleet_manager.config import load_config
from repo_fleet_manager.runtime import (
    RuntimeErrorDetail,
    discover_runtime_services,
    ordered_runtime_up,
    runtime_levels,
    runtime_status,
    wait_runtime,
)
from repo_fleet_manager.schema import validate_config_data
from repo_fleet_manager.shell import RunResult


def base_config() -> dict:
    return {
        "schema_version": "1.0.0",
        "project": {"name": "runtime-test", "default_provider": "local", "default_branch": "main"},
        "providers": {
            "local": {
                "type": "local",
                "driver": "local",
                "namespace": ".repo-fleet/remotes",
                "url_template": "file://{root}/{namespace}/{repo}.git",
                "cli": "git",
                "required_scopes": [],
            }
        },
        "repositories": [
            {"path": ".", "repo": "runtime-test", "kind": "root", "provider": "local", "branch": "main", "source_type": "existing", "depends_on": []},
            {"path": "services/db", "repo": "db-repo", "kind": "service", "provider": "local", "branch": "main", "source_type": "existing", "existing_path": "services/db", "compose_service": "db", "depends_on": []},
            {"path": "services/api", "repo": "api-repo", "kind": "service", "provider": "local", "branch": "main", "source_type": "existing", "existing_path": "services/api", "compose_service": "api", "depends_on": ["db-repo"]},
        ],
        "compose": {"file": "compose.yaml", "project_name": "runtime-test", "engine": "docker"},
        "runtime": {
            "timeout_seconds": 1,
            "interval_seconds": 0.01,
            "default_running_is_ready": False,
            "services": {
                "db": {"required": True, "depends_on": []},
                "api": {"required": True, "depends_on": ["db"], "probe": {"type": "command", "command": ["true"]}},
            },
        },
    }


class FakeRuntimeRunner:
    def __init__(self, health: dict[str, list[str] | str] | None = None):
        self.health = health or {"db": "healthy", "api": "healthy"}
        self.inspect_count: dict[str, int] = {}
        self.commands: list[list[str]] = []

    def __call__(self, cmd, cwd=None, check=False):
        command = [str(item) for item in cmd]
        self.commands.append(command)
        if "config" in command and "--format" in command:
            return RunResult(0, json.dumps({"services": {"db": {}, "api": {"depends_on": {"db": {"condition": "service_healthy"}}}}}), "")
        if "config" in command and "--services" in command:
            return RunResult(0, "db\napi", "")
        if "ps" in command and "-q" in command:
            service = command[-1]
            return RunResult(0, f"cid-{service}", "")
        if len(command) >= 3 and command[0] == "docker" and command[1] == "inspect":
            service = command[2].replace("cid-", "")
            raw = self.health.get(service, "healthy")
            if isinstance(raw, list):
                index = self.inspect_count.get(service, 0)
                value = raw[min(index, len(raw) - 1)]
                self.inspect_count[service] = index + 1
            else:
                value = raw
            return RunResult(0, json.dumps([{"State": {"Status": "running", "Running": True, "Health": {"Status": value}, "ExitCode": 0}}]), "")
        if command == ["true"]:
            return RunResult(0, "ok", "")
        if "logs" in command:
            return RunResult(0, "example failure log", "")
        return RunResult(0, "", "")


class RuntimeReadinessTests(unittest.TestCase):
    def make_config(self, root: Path, data: dict | None = None):
        payload = data or base_config()
        (root / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
        path = root / "repo-fleet.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return load_config(path)

    def test_status_distinguishes_running_from_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = self.make_config(root)
            runner = FakeRuntimeRunner({"db": "starting", "api": "healthy"})
            with patch("repo_fleet_manager.runtime.detect_compose_bin", side_effect=lambda *_args, **_kwargs: ["docker", "compose"]), patch("repo_fleet_manager.compose.detect_compose_bin", side_effect=lambda *_args, **_kwargs: ["docker", "compose"]):
                report = runtime_status(cfg, root, runner=runner)
            by_name = {item.name: item for item in report.services}
            self.assertTrue(by_name["db"].running)
            self.assertFalse(by_name["db"].ready)
            self.assertEqual(by_name["db"].readiness_source, "compose-health")
            self.assertTrue(by_name["api"].ready)
            self.assertFalse(report.ready)

    def test_wait_transitions_to_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = self.make_config(root)
            runner = FakeRuntimeRunner({"db": ["starting", "healthy"], "api": "healthy"})
            clock = iter([0.0, 0.0, 0.1, 0.2, 0.3])
            with patch("repo_fleet_manager.runtime.detect_compose_bin", side_effect=lambda *_args, **_kwargs: ["docker", "compose"]), patch("repo_fleet_manager.compose.detect_compose_bin", side_effect=lambda *_args, **_kwargs: ["docker", "compose"]):
                report = wait_runtime(
                    cfg, root, timeout_seconds=1, interval_seconds=0.01, runner=runner,
                    sleep_fn=lambda _seconds: None, monotonic_fn=lambda: next(clock),
                )
            self.assertTrue(report.ready)

    def test_runtime_levels_and_dry_run_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = self.make_config(root)
            runner = FakeRuntimeRunner()
            with patch("repo_fleet_manager.runtime.detect_compose_bin", side_effect=lambda *_args, **_kwargs: ["docker", "compose"]), patch("repo_fleet_manager.compose.detect_compose_bin", side_effect=lambda *_args, **_kwargs: ["docker", "compose"]):
                specs = discover_runtime_services(cfg, root, runner=runner)
                levels = runtime_levels(specs)
                self.assertEqual([[item.name for item in level] for level in levels], [["db"], ["api"]])
                output = StringIO()
                with redirect_stdout(output):
                    report = ordered_runtime_up(cfg, root, apply=False, runner=runner)
            self.assertIn("runtime level 0: db", output.getvalue())
            self.assertIn("runtime level 1: api", output.getvalue())
            self.assertEqual([item.state for item in report.services], ["planned", "planned"])

    def test_runtime_cycle_is_rejected_by_schema(self):
        data = base_config()
        data["runtime"]["services"]["db"]["depends_on"] = ["api"]
        issues = validate_config_data(data)
        self.assertTrue(any(item.code == "runtime-dependency-cycle" for item in issues))

    def test_selected_service_includes_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = self.make_config(root)
            runner = FakeRuntimeRunner()
            with patch("repo_fleet_manager.runtime.detect_compose_bin", side_effect=lambda *_args, **_kwargs: ["docker", "compose"]), patch("repo_fleet_manager.compose.detect_compose_bin", side_effect=lambda *_args, **_kwargs: ["docker", "compose"]):
                specs = discover_runtime_services(cfg, root, ["api"], runner=runner)
            self.assertEqual([item.name for item in specs], ["db", "api"])

    def test_unknown_selected_service_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = self.make_config(root)
            runner = FakeRuntimeRunner()
            with patch("repo_fleet_manager.runtime.detect_compose_bin", side_effect=lambda *_args, **_kwargs: ["docker", "compose"]), patch("repo_fleet_manager.compose.detect_compose_bin", side_effect=lambda *_args, **_kwargs: ["docker", "compose"]):
                with self.assertRaises(RuntimeErrorDetail):
                    discover_runtime_services(cfg, root, ["missing"], runner=runner)

    def test_cli_runtime_status_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg_path = root / "repo-fleet.json"
            cfg_path.write_text(json.dumps(base_config()), encoding="utf-8")
            fake_report = type("Report", (), {"ready": True, "to_dict": lambda self: {"ready": True, "services": []}})()
            output = StringIO()
            with patch("repo_fleet_manager.cli.runtime_status", return_value=fake_report), redirect_stdout(output):
                rc = main(["runtime", "--config", str(cfg_path), "--root", str(root), "status", "--json"])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(output.getvalue())["ready"])


if __name__ == "__main__":
    unittest.main()
