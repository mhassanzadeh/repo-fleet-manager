from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from repo_fleet_manager.cli import main
from repo_fleet_manager.operations import OperationJournal, SafetyError, WorkspaceLock


class OperationTests(unittest.TestCase):
    def test_lock_requires_explicit_reason_to_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / ".repo-fleet/lock"
            first = WorkspaceLock(root, "first", path)
            first.acquire()
            try:
                with self.assertRaises(SafetyError):
                    WorkspaceLock(root, "second", path).acquire()
                with self.assertRaises(SafetyError):
                    WorkspaceLock(root, "second", path, force=True).acquire()
            finally:
                first.release()

    def test_journal_restores_file_and_removes_created_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            directory = root / ".repo-fleet/operations"
            target = root / "config.txt"
            target.write_text("before", encoding="utf-8")
            created = root / "created"
            journal = OperationJournal(root, "test", ["test"], directory)
            journal.backup_file(target)
            journal.track_created_path(created)
            target.write_text("after", encoding="utf-8")
            created.mkdir()
            failures, _ = journal.rollback()
            self.assertEqual(failures, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "before")
            self.assertFalse(created.exists())

    def test_cli_local_operation_can_be_rolled_back(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = {
                "schema_version": "1.0.0",
                "project": {"name": "ops-demo", "default_provider": "local"},
                "providers": {"local": {"type": "local", "namespace": ".repo-fleet/remotes"}},
                "repositories": [
                    {"path": ".", "repo": "ops-demo", "kind": "root", "source_type": "new", "remote_mode": "create", "depends_on": []},
                    {"path": "services/api", "repo": "ops-api", "source_type": "new", "remote_mode": "create", "depends_on": []},
                ],
                "local": {"remotes_dir": ".repo-fleet/remotes", "operations_dir": ".repo-fleet/operations", "lock_file": ".repo-fleet/lock"},
            }
            config_path = root / "repo-fleet.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            code = main(["local", "--root", str(root), "--config", str(config_path), "remotes", "--apply"])
            self.assertEqual(code, 0)
            operations = sorted((root / ".repo-fleet/operations").glob("*.json"))
            self.assertEqual(len(operations), 1)
            operation_id = json.loads(operations[0].read_text())["id"]
            self.assertTrue((root / ".repo-fleet/remotes/ops-api.git").exists())
            code = main(["ops", "--root", str(root), "--config", str(config_path), "rollback", operation_id])
            self.assertEqual(code, 0)
            self.assertFalse((root / ".repo-fleet/remotes/ops-api.git").exists())

    def test_journal_restores_git_head_after_commit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "RFM Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "rfm@example.invalid"], cwd=root, check=True)
            target = root / "README.md"
            target.write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
            initial = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

            journal = OperationJournal(root, "test", ["test"], root / ".repo-fleet/operations")
            journal.track_git_head(root)
            journal.backup_file(target)
            target.write_text("after\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "changed"], cwd=root, check=True, capture_output=True)

            failures, _ = journal.rollback()
            current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            self.assertEqual(failures, 0)
            self.assertEqual(current, initial)
            self.assertEqual(target.read_text(encoding="utf-8"), "before\n")

    def test_failed_operation_can_resume_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = {
                "schema_version": "1.0.0",
                "project": {"name": "resume-demo", "default_provider": "local"},
                "providers": {"local": {"type": "local", "driver": "local", "namespace": ".repo-fleet/remotes", "required_scopes": []}},
                "repositories": [
                    {"path": ".", "repo": "resume-demo", "kind": "root", "source_type": "new", "remote_mode": "create", "depends_on": []},
                    {"path": "services/api", "repo": "resume-api", "source_type": "new", "remote_mode": "create", "depends_on": []},
                ],
                "local": {"remotes_dir": ".repo-fleet/remotes", "operations_dir": ".repo-fleet/operations", "lock_file": ".repo-fleet/lock", "default_jobs": 1},
            }
            config_path = root / "repo-fleet.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            argv = ["local", "--root", str(root), "--config", str(config_path), "remotes", "--apply"]
            self.assertEqual(main(argv), 0)
            operation_path = next((root / ".repo-fleet/operations").glob("*.json"))
            data = json.loads(operation_path.read_text(encoding="utf-8"))
            operation_id = data["id"]
            missing = root / ".repo-fleet/remotes/resume-api.git"
            subprocess.run(["rm", "-rf", str(missing)], check=True)
            data["status"] = "failed"
            data["exit_code"] = 1
            data["error"] = "simulated interruption"
            operation_path.write_text(json.dumps(data), encoding="utf-8")

            self.assertEqual(main(["ops", "--root", str(root), "--config", str(config_path), "resume", operation_id]), 0)
            resumed = json.loads(operation_path.read_text(encoding="utf-8"))
            self.assertTrue(missing.exists())
            self.assertEqual(resumed["status"], "completed")
            self.assertEqual(resumed["resume_count"], 1)
            self.assertGreaterEqual(len(resumed["attempts"]), 2)


if __name__ == "__main__":
    unittest.main()
