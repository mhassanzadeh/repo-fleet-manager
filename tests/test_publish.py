from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from repo_fleet_manager.config import load_config
from repo_fleet_manager.gitops import publish_repositories
from repo_fleet_manager.shell import RunResult


class PublishWorkflowTests(unittest.TestCase):
    def test_existing_root_repository_dry_run_reaches_remote_and_push_plan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config_path = root / "repo-fleet.json"
            config_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "project": {
                            "name": "repo-fleet-manager",
                            "default_provider": "github",
                            "default_branch": "master",
                        },
                        "providers": {
                            "github": {
                                "type": "remote",
                                "driver": "github",
                                "namespace": "mhassanzadeh",
                                "cli": "gh",
                                "url_template": "git@github.com:{namespace}/{repo}.git",
                            }
                        },
                        "repositories": [
                            {
                                "path": ".",
                                "repo": "repo-fleet-manager",
                                "provider": "github",
                                "branch": "master",
                                "source_type": "existing",
                                "remote_mode": "create",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            config = load_config(config_path)

            def fake_run(cmd: list[str], cwd: Path | None = None, **_: object) -> CommandResult:
                if cmd[:3] == ["gh", "repo", "view"]:
                    return RunResult(1, "", "not found")
                if cmd[:4] == ["git", "rev-parse", "--is-inside-work-tree"]:
                    return RunResult(0, "true", "")
                if cmd[:4] == ["git", "remote", "get-url"]:
                    return RunResult(2, "", "missing")
                if cmd[:3] == ["git", "branch", "--show-current"]:
                    return RunResult(0, "master", "")
                return RunResult(0, "", "")

            output = io.StringIO()
            with (
                patch("repo_fleet_manager.gitops.command_exists", return_value=True),
                patch("repo_fleet_manager.gitops.run", side_effect=fake_run),
                patch("repo_fleet_manager.localops.run", side_effect=fake_run),
                redirect_stdout(output),
            ):
                result = publish_repositories(
                    config,
                    root,
                    provider_override="github",
                    namespace="mhassanzadeh",
                    visibility="private",
                    apply=False,
                    remote_name="origin",
                )

            rendered = output.getvalue()
            self.assertEqual(result, 0)
            self.assertIn("gh repo create mhassanzadeh/repo-fleet-manager", rendered)
            self.assertIn("git remote add origin git@github.com:mhassanzadeh/repo-fleet-manager.git", rendered)
            self.assertIn("git push -u origin HEAD:master", rendered)


if __name__ == "__main__":
    unittest.main()
