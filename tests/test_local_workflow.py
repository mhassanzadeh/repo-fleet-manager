from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from repo_fleet_manager.cli import main
from repo_fleet_manager.shell import run
from repo_fleet_manager.gitops import audit
from repo_fleet_manager.config import load_config


class LocalWorkflowTests(unittest.TestCase):
    def write_config(self, root: Path) -> Path:
        config = {
            "project": {"name": "local-demo", "default_provider": "local", "default_branch": "main"},
            "local": {"remotes_dir": ".repo-fleet/remotes"},
            "providers": {
                "local": {
                    "type": "local",
                    "namespace": ".repo-fleet/remotes",
                    "url_template": "file://{root}/{namespace}/{repo}.git",
                    "cli": "git",
                }
            },
            "repositories": [
                {"path": ".", "repo": "local-demo", "kind": "root", "branch": "main", "provider": "local"},
                {"path": "services/api", "repo": "local-demo-api", "kind": "service", "branch": "main", "provider": "local"},
            ],
        }
        path = root / "repo-fleet.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_local_bootstrap_creates_submodule_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config_path = self.write_config(root)
            rc = main(["local", "--root", str(root), "--config", str(config_path), "bootstrap", "--apply", "--set-origin"])
            self.assertEqual(rc, 0)
            self.assertTrue((root / ".gitmodules").exists())
            self.assertTrue((root / "services" / "api" / ".git").is_file())
            tracked_local_remotes = run(["git", "ls-files", ".repo-fleet/remotes"], cwd=root)
            self.assertEqual(tracked_local_remotes.stdout, "")
            cfg = load_config(config_path)
            report = audit(cfg, root, provider_override="local")
            self.assertEqual(report["issue_count"], 0)


if __name__ == "__main__":
    unittest.main()
