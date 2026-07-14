from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from repo_fleet_manager.cli import main
from repo_fleet_manager.config import load_config
from repo_fleet_manager.profiles import ConfigResolutionError
from repo_fleet_manager.schema import validate_config_data


class ProfilesAndGroupsTests(unittest.TestCase):
    def write_config(self, root: Path, *, cycle: bool = False) -> Path:
        profiles = {
            "developer": {
                "project": {"default_provider": "local"},
                "local": {"default_jobs": 2},
                "providers": {"local": {"namespace": ".repo-fleet/dev-remotes"}},
                "repositories": {
                    "api": {"branch": "dev", "tags": ["backend", "developer"]}
                },
            },
            "ci": {
                "extends": "developer",
                "project": {"default_provider": "github"},
                "local": {"default_jobs": 8},
                "repositories": {
                    "web": {"enabled": False},
                    "api": {"branch": "main"},
                },
            },
        }
        if cycle:
            profiles["developer"]["extends"] = "ci"
        data = {
            "schema_version": "1.0.0",
            "project": {"name": "demo", "default_provider": "github", "default_branch": "main"},
            "providers": {
                "github": {
                    "type": "remote", "driver": "github", "namespace": "example",
                    "host": "github.com", "cli": "gh",
                    "url_template": "git@github.com:{namespace}/{repo}.git",
                },
                "local": {
                    "type": "local", "driver": "local", "namespace": ".repo-fleet/remotes",
                    "cli": "git", "url_template": "file://{root}/{namespace}/{repo}.git",
                },
            },
            "repositories": [
                {
                    "path": ".", "repo": "demo", "kind": "root", "branch": "main",
                    "source_type": "new", "remote_mode": "create", "depends_on": [],
                    "tags": ["root"],
                },
                {
                    "path": "packages/contracts", "repo": "contracts", "kind": "package", "branch": "main",
                    "source_type": "new", "remote_mode": "create", "depends_on": [],
                    "tags": ["shared"],
                },
                {
                    "path": "services/api", "repo": "api", "kind": "service", "branch": "main",
                    "source_type": "new", "remote_mode": "create", "depends_on": ["contracts"],
                    "tags": ["backend"],
                },
                {
                    "path": "clients/web", "repo": "web", "kind": "client", "branch": "main",
                    "source_type": "new", "remote_mode": "create", "depends_on": ["api"],
                    "tags": ["frontend"],
                },
            ],
            "profiles": profiles,
            "groups": {
                "backend": {"tags": ["backend"], "include_dependencies": True},
                "frontend-only": {"repositories": ["web"], "include_dependencies": False},
            },
            "local": {"default_jobs": 1},
        }
        path = root / "repo-fleet.json"
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return path

    def test_profile_inheritance_and_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = self.write_config(Path(td))
            cfg = load_config(path, profiles=["ci"])
            self.assertEqual(cfg.project["default_provider"], "github")
            self.assertEqual(cfg.default_jobs, 8)
            self.assertEqual(cfg.providers["local"].namespace, ".repo-fleet/dev-remotes")
            self.assertEqual([repo.repo for repo in cfg.repositories], ["demo", "contracts", "api"])
            self.assertEqual(cfg.repository_map()["api"].branch, "main")
            self.assertEqual(cfg.active_profiles, ("ci",))

    def test_group_selects_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = self.write_config(Path(td))
            cfg = load_config(path, groups=["backend"])
            self.assertEqual([repo.repo for repo in cfg.repositories], ["contracts", "api"])
            self.assertEqual(cfg.repository_map()["api"].depends_on, ["contracts"])
            self.assertEqual(cfg.active_groups, ("backend",))

    def test_group_without_dependencies_prunes_edges(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = self.write_config(Path(td))
            cfg = load_config(path, groups=["frontend-only"])
            self.assertEqual([repo.repo for repo in cfg.repositories], ["web"])
            self.assertEqual(cfg.repositories[0].depends_on, [])

    def test_render_command_outputs_concrete_config(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = self.write_config(Path(td))
            output = StringIO()
            with redirect_stdout(output):
                rc = main([
                    "config", "--config", str(path), "--profile", "ci", "--group", "backend", "render"
                ])
            self.assertEqual(rc, 0)
            payload = json.loads(output.getvalue())
            self.assertNotIn("profiles", payload)
            self.assertNotIn("groups", payload)
            self.assertEqual(payload["x-rfm-resolution"], {"profiles": ["ci"], "groups": ["backend"]})
            self.assertEqual([repo["repo"] for repo in payload["repositories"]], ["contracts", "api"])

    def test_unknown_profile_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = self.write_config(Path(td))
            with self.assertRaises(ConfigResolutionError):
                load_config(path, profiles=["missing"])

    def test_policy_profile_overlay_is_schema_valid_and_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = self.write_config(Path(td))
            data = json.loads(path.read_text(encoding="utf-8"))
            data["policy"] = {"enabled": False, "mode": "check", "fail_on": "error", "rules": [], "exceptions": []}
            data["profiles"]["ci"]["policy"] = {
                "enabled": True,
                "mode": "enforce",
                "fail_on": "warning",
                "rules": [
                    {
                        "id": "ci-clean",
                        "type": "repository.clean",
                        "severity": "warning",
                        "parameters": {},
                    }
                ],
            }
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            issues = validate_config_data(data)
            self.assertEqual([], [item for item in issues if item.level == "error"])
            cfg = load_config(path, profiles=["ci"])
            self.assertTrue(cfg.policy["enabled"])
            self.assertEqual(cfg.policy["mode"], "enforce")
            self.assertEqual(cfg.policy["fail_on"], "warning")
            self.assertEqual(cfg.policy["rules"][0]["id"], "ci-clean")

    def test_profile_cycle_is_reported_by_validation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = self.write_config(Path(td), cycle=True)
            issues = validate_config_data(json.loads(path.read_text(encoding="utf-8")))
            self.assertTrue(any(issue.code == "profile-cycle" for issue in issues))


if __name__ == "__main__":
    unittest.main()
