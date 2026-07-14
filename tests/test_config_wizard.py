from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from repo_fleet_manager.cli import main
from repo_fleet_manager.wizard import WizardError, load_answers, run_wizard, scan_project


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


class ConfigWizardTests(unittest.TestCase):
    def make_repo(self, root: Path, remote: str = "git@github.com:acme/platform.git") -> None:
        root.mkdir(parents=True, exist_ok=True)
        git(root, "init", "-b", "main")
        git(root, "config", "user.name", "Wizard Test")
        git(root, "config", "user.email", "wizard@example.invalid")
        (root / "README.md").write_text("# Platform\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "initial")
        git(root, "remote", "add", "origin", remote)

    def test_scan_detects_git_compose_images_and_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "platform"
            self.make_repo(root)
            (root / "infra-compose").mkdir()
            (root / "infra-compose" / "compose.yaml").write_text(
                "services:\n  db:\n    image: postgres:16\n  api:\n    build: ../services/api\n",
                encoding="utf-8",
            )
            (root / "infra-compose" / ".env.example").write_text("DB_HOST=db\n", encoding="utf-8")
            scan = scan_project(root)
            self.assertEqual(scan.default_provider, "github")
            self.assertEqual(scan.namespace, "acme")
            self.assertEqual(scan.repositories[0]["path"], ".")
            self.assertEqual(scan.compose_file, "infra-compose/compose.yaml")
            self.assertEqual(scan.env_file, "infra-compose/.env.example")
            self.assertIn("postgres:16", scan.cache_images)
            generated = run_wizard(output=root / "repo-fleet.json", scan_path=root, non_interactive=True).config
            self.assertNotIn(str(root), json.dumps(generated))

    def test_non_interactive_scan_writes_strict_valid_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "platform"
            self.make_repo(root)
            output = root / "repo-fleet.json"
            result = run_wizard(output=output, scan_path=root, non_interactive=True, advanced=True, apply=True)
            self.assertTrue(output.exists())
            self.assertTrue(result.changed)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], "1.0.0")
            self.assertEqual(data["project"]["default_provider"], "github")
            self.assertIn("developer", data["profiles"])
            self.assertEqual(data["repositories"][0]["path"], ".")

    def test_edit_creates_backup_and_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "repo-fleet.json"
            first = run_wizard(
                output=output,
                answers={"config": {
                    "project": {"name": "alpha", "default_provider": "local", "default_branch": "main"},
                    "providers": {"local": {"type": "local", "driver": "local", "namespace": ".repo-fleet/remotes", "cli": "git", "url_template": "file://{root}/{namespace}/{repo}.git", "required_scopes": []}},
                    "repositories": [{"path": ".", "repo": "alpha", "kind": "root", "provider": "local", "branch": "main", "source_type": "existing", "depends_on": []}],
                }},
                non_interactive=True,
                apply=True,
            )
            self.assertTrue(first.changed)
            second = run_wizard(
                output=output,
                config_path=output,
                answers={"project": {"description": "Updated safely"}},
                non_interactive=True,
                apply=True,
            )
            self.assertIsNotNone(second.backup)
            self.assertTrue(second.backup.exists())
            self.assertIn("Updated safely", output.read_text(encoding="utf-8"))
            self.assertIn("description", second.diff)

    def test_secret_like_answers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            answers = Path(tmp) / "answers.json"
            answers.write_text(json.dumps({"github_token": "unsafe"}), encoding="utf-8")
            with self.assertRaises(WizardError):
                load_answers(answers)

    def test_cli_non_interactive_dry_run_and_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "platform"
            self.make_repo(root, "git@gitlab.com:bank/platform.git")
            output = root / "repo-fleet.json"
            buffer = StringIO()
            with redirect_stdout(buffer):
                rc = main(["config", "wizard", "--scan", str(root), "--output", str(output), "--non-interactive"])
            self.assertEqual(rc, 0, buffer.getvalue())
            self.assertFalse(output.exists())
            self.assertIn("DRY-RUN", buffer.getvalue())
            buffer = StringIO()
            with redirect_stdout(buffer):
                rc = main(["config", "wizard", "--scan", str(root), "--output", str(output), "--non-interactive", "--apply"])
            self.assertEqual(rc, 0, buffer.getvalue())
            self.assertTrue(output.exists())
            self.assertEqual(json.loads(output.read_text())["project"]["default_provider"], "gitlab")


    def test_resume_reuses_saved_answers_and_removes_session_after_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "repo-fleet.json"
            session = root / ".repo-fleet/wizard/session.json"
            values = iter(["resumed-platform", "main", "local", "auto"])
            first = run_wizard(output=output, session_file=session, input_fn=lambda _prompt: next(values))
            self.assertFalse(output.exists())
            self.assertTrue(session.exists())
            self.assertEqual(first.config["project"]["name"], "resumed-platform")
            second = run_wizard(
                output=output,
                session_file=session,
                resume=True,
                apply=True,
                input_fn=lambda prompt: self.fail(f"unexpected prompt after resume: {prompt}"),
            )
            self.assertTrue(output.exists())
            self.assertFalse(session.exists())
            self.assertEqual(second.config["project"]["name"], "resumed-platform")

    def test_absolute_answer_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "repo-fleet.json"
            with self.assertRaises(WizardError):
                run_wizard(
                    output=output,
                    answers={"local": {"remotes_dir": "/home/user/remotes"}},
                    non_interactive=True,
                )

    def test_reset_removes_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / ".repo-fleet/wizard/session.json"
            session.parent.mkdir(parents=True)
            session.write_text('{"format":1,"answers":{}}\n', encoding="utf-8")
            rc = main(["config", "wizard", "--root", str(root), "--session-file", str(session), "--reset"])
            self.assertEqual(rc, 0)
            self.assertFalse(session.exists())


if __name__ == "__main__":
    unittest.main()
