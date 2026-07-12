from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from repo_fleet_manager.cli import main
from repo_fleet_manager.scaffold import (
    DEFAULT_LOCK_FILE,
    ScaffoldError,
    init_project,
    scaffold_repository,
    verify_bootstrap_lock,
)
from repo_fleet_manager.schema import validate_or_raise


class ScaffoldBootstrapTests(unittest.TestCase):
    def test_init_project_dry_run_does_not_create_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "demo"
            result = init_project("demo", directory=target, apply=False)
            self.assertFalse(target.exists())
            self.assertIn("repo-fleet.json", result.written)
            self.assertIn(DEFAULT_LOCK_FILE, result.written)

    def test_init_project_creates_valid_portable_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "demo"
            result = init_project("demo", directory=target, apply=True, git_init=False)
            self.assertTrue(result.config_path and result.config_path.is_file())
            self.assertTrue(result.lock_path and result.lock_path.is_file())
            config = json.loads((target / "repo-fleet.json").read_text(encoding="utf-8"))
            validate_or_raise(config)
            report = verify_bootstrap_lock(config, root=target)
            self.assertTrue(report["valid"], report["issues"])
            lock_text = (target / DEFAULT_LOCK_FILE).read_text(encoding="utf-8")
            self.assertNotIn(str(target.resolve()), lock_text)
            self.assertIn('"schema": "rfm-bootstrap-lock/v1"', lock_text)

    def test_scaffold_repository_updates_config_and_lock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "platform"
            init_project("platform", directory=root, apply=True, git_init=False)
            config_path = root / "repo-fleet.json"
            result = scaffold_repository(
                config_path,
                root=root,
                name="platform-api",
                path="services/api",
                template="python-service",
                kind="service",
                description="API service",
                branch=None,
                provider=None,
                visibility="private",
                tags=["backend", "runtime"],
                depends_on=None,
                owner="Example Team",
                apply=True,
                force=False,
            )
            self.assertEqual(result.target, root / "services/api")
            self.assertTrue((root / "services/api/pyproject.toml").is_file())
            self.assertTrue((root / "services/api/.rfm-template.json").is_file())
            config = json.loads(config_path.read_text(encoding="utf-8"))
            validate_or_raise(config)
            repo = next(item for item in config["repositories"] if item["repo"] == "platform-api")
            self.assertEqual(repo["metadata"]["scaffold_template"], "python-service")
            self.assertEqual(repo["tags"], ["backend", "runtime"])
            report = verify_bootstrap_lock(config, root=root)
            self.assertTrue(report["valid"], report["issues"])
            self.assertEqual(report["repositories"], 2)

    def test_verify_detects_config_and_file_drift(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "demo"
            init_project("demo", directory=root, apply=True, git_init=False)
            config_path = root / "repo-fleet.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["project"]["description"] = "changed"
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            (root / "README.md").write_text("changed\n", encoding="utf-8")
            report = verify_bootstrap_lock(config, root=root)
            self.assertFalse(report["valid"])
            self.assertTrue(any("configuration digest mismatch" in issue for issue in report["issues"]))
            self.assertTrue(any("README.md" in issue for issue in report["issues"]))

    def test_unsafe_repository_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "demo"
            init_project("demo", directory=root, apply=True, git_init=False)
            with self.assertRaises(ScaffoldError):
                scaffold_repository(
                    root / "repo-fleet.json",
                    root=root,
                    name="escape",
                    path="../escape",
                    template="generic",
                    kind="module",
                    description=None,
                    branch=None,
                    provider=None,
                    visibility=None,
                    tags=None,
                    depends_on=None,
                    owner="Example",
                    apply=True,
                    force=False,
                )

    def test_cli_templates_and_project_workflow(self) -> None:
        buffer = StringIO()
        with redirect_stdout(buffer):
            rc = main(["scaffold", "templates", "--json"])
        self.assertEqual(rc, 0)
        self.assertIn("python-service", buffer.getvalue())
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "cli-demo"
            rc = main([
                "init-project", "cli-demo", "--directory", str(target),
                "--no-git-init", "--apply",
            ])
            self.assertEqual(rc, 0)
            rc = main([
                "bootstrap", "--config", str(target / "repo-fleet.json"),
                "--root", str(target), "verify",
            ])
            self.assertEqual(rc, 0)
            rc = main([
                "bootstrap", "--root", str(target), "verify",
            ])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
