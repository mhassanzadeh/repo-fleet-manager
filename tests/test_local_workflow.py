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

    def make_git_repo(self, path: Path, branch: str = "main", filename: str = "README.md") -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.assertEqual(run(["git", "init", "-b", branch], cwd=path).code, 0)
        (path / filename).write_text(f"# {path.name}\n", encoding="utf-8")
        self.assertEqual(run(["git", "add", "."], cwd=path).code, 0)
        self.assertEqual(run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "init"], cwd=path).code, 0)

    def test_localize_handles_new_upstream_and_existing_repositories(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "platform"
            root.mkdir()

            upstream_work = base / "upstream-work"
            self.make_git_repo(upstream_work, filename="UPSTREAM.md")
            upstream_bare = base / "upstream.git"
            self.assertEqual(run(["git", "clone", "--bare", str(upstream_work), str(upstream_bare)], cwd=base).code, 0)

            existing_work = base / "existing-work"
            self.make_git_repo(existing_work, filename="EXISTING.md")

            config = {
                "project": {"name": "mixed-demo", "default_provider": "local", "default_branch": "main"},
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
                    {"path": ".", "repo": "mixed-demo", "kind": "root", "branch": "main", "provider": "local", "source_type": "new"},
                    {"path": "services/new-api", "repo": "mixed-new-api", "kind": "service", "branch": "main", "provider": "local", "source_type": "new"},
                    {"path": "vendor/upstream", "repo": "mixed-upstream", "kind": "module", "branch": "main", "provider": "local", "source_type": "upstream", "upstream_url": str(upstream_bare)},
                    {"path": "legacy/existing", "repo": "mixed-existing", "kind": "module", "branch": "main", "provider": "local", "source_type": "existing", "existing_path": str(existing_work)},
                ],
            }
            config_path = root / "repo-fleet.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            self.assertEqual(main(["local", "--root", str(root), "--config", str(config_path), "plan"]), 0)
            rc = main(["local", "--root", str(root), "--config", str(config_path), "localize", "--apply"])
            self.assertEqual(rc, 0)
            self.assertTrue((root / "services" / "new-api" / ".git").is_file())
            self.assertTrue((root / "vendor" / "upstream" / "UPSTREAM.md").exists())
            self.assertTrue((root / "legacy" / "existing" / "EXISTING.md").exists())
            tracked_local_remotes = run(["git", "ls-files", ".repo-fleet/remotes"], cwd=root)
            self.assertEqual(tracked_local_remotes.stdout, "")


if __name__ == "__main__":
    unittest.main()
