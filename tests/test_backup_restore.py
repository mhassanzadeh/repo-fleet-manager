from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import unittest
import warnings
from contextlib import redirect_stdout
from pathlib import Path

from repo_fleet_manager.backup import BackupError, create_backup, restore_backup, verify_backup
from repo_fleet_manager.cli import main
from repo_fleet_manager.config import load_config


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


class BackupRestoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "workspace"
        self.root.mkdir()
        self.config_path = self.root / "repo-fleet.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "project": {
                        "name": "backup-demo",
                        "default_provider": "local",
                        "default_branch": "main",
                    },
                    "providers": {
                        "local": {
                            "type": "local",
                            "driver": "local",
                            "namespace": ".repo-fleet/remotes",
                            "cli": "git",
                            "url_template": "file://{root}/{namespace}/{repo}.git",
                        }
                    },
                    "repositories": [
                        {
                            "path": ".",
                            "repo": "backup-demo",
                            "kind": "root",
                            "provider": "local",
                            "branch": "main",
                            "source_type": "existing",
                            "remote_mode": "create",
                            "depends_on": [],
                        },
                        {
                            "path": "modules/api",
                            "repo": "backup-api",
                            "kind": "service",
                            "provider": "local",
                            "branch": "main",
                            "source_type": "new",
                            "remote_mode": "create",
                            "depends_on": [],
                        },
                    ],
                    "local": {
                        "remotes_dir": ".repo-fleet/remotes",
                        "workspace_mode": "submodules",
                        "operations_dir": ".repo-fleet/operations",
                        "lock_file": ".repo-fleet/lock",
                        "backups_dir": ".repo-fleet/backups",
                        "backup_retention": 5,
                        "backup_include_operations": False,
                        "default_jobs": 1,
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.config = load_config(self.config_path)
        self.remotes = self.root / ".repo-fleet/remotes"
        self.remotes.mkdir(parents=True)
        self.expected_refs: dict[str, str] = {}
        self._create_mirror("backup-demo")
        self._create_mirror("backup-api")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create_mirror(self, name: str) -> None:
        source = self.base / f"source-{name}"
        git("init", "-b", "main", str(source))
        git("config", "user.name", "Backup Test", cwd=source)
        git("config", "user.email", "backup@example.invalid", cwd=source)
        (source / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        git("add", ".", cwd=source)
        git("commit", "-m", "initial", cwd=source)
        git("branch", "unpublished/work", cwd=source)
        git("tag", "local-only-v1", cwd=source)
        target = self.remotes / f"{name}.git"
        git("clone", "--mirror", str(source), str(target))
        refs = git(f"--git-dir={target}", "show-ref")
        for line in refs.splitlines():
            sha, ref = line.split(" ", 1)
            self.expected_refs[f"{name}:{ref}"] = sha

    def _refs(self, remote: Path, name: str) -> dict[str, str]:
        result: dict[str, str] = {}
        refs = git(f"--git-dir={remote / (name + '.git')}", "show-ref")
        for line in refs.splitlines():
            sha, ref = line.split(" ", 1)
            result[f"{name}:{ref}"] = sha
        return result

    def test_backup_verify_and_restore_on_clean_machine(self) -> None:
        archive = self.root / ".repo-fleet/backups/demo.rfm-backup.tar.gz"
        rc = create_backup(self.config, self.root, output=str(archive), apply=True)
        self.assertEqual(rc, 0)
        self.assertTrue(archive.is_file())
        self.assertEqual(verify_backup(archive), 0)

        target = self.base / "restored"
        rc = restore_backup(archive, target, config=None, apply=True)
        self.assertEqual(rc, 0)
        self.assertTrue((target / "repo-fleet.json").is_file())
        restored_remotes = target / ".repo-fleet/remotes"
        actual: dict[str, str] = {}
        actual.update(self._refs(restored_remotes, "backup-demo"))
        actual.update(self._refs(restored_remotes, "backup-api"))
        self.assertEqual(actual, self.expected_refs)

    def test_cli_backup_json_stdout_is_machine_readable(self) -> None:
        archive = self.root / ".repo-fleet/backups/json.rfm-backup.tar.gz"
        output = io.StringIO()
        with redirect_stdout(output):
            rc = main([
                "local", "--root", str(self.root), "--config", str(self.config_path),
                "backup", "--output", str(archive), "--json", "--apply",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["archive"], str(archive))
        self.assertFalse(payload["dry_run"])
        self.assertTrue(payload["sha256"])

    def test_cli_restore_does_not_require_existing_config(self) -> None:
        archive = self.root / ".repo-fleet/backups/cli.rfm-backup.tar.gz"
        create_backup(self.config, self.root, output=str(archive), apply=True)
        target = self.base / "clean-cli-target"
        output = io.StringIO()
        with redirect_stdout(output):
            rc = main(["local", "--root", str(target), "restore", str(archive), "--apply"])
        self.assertEqual(rc, 0, output.getvalue())
        self.assertIn("backup restored", output.getvalue())
        self.assertTrue((target / "repo-fleet.json").exists())
        self.assertTrue((target / ".repo-fleet/remotes/backup-api.git").exists())

    def test_restore_overwrite_can_be_rolled_back(self) -> None:
        archive = self.root / ".repo-fleet/backups/rollback.rfm-backup.tar.gz"
        create_backup(self.config, self.root, output=str(archive), apply=True)

        target = self.base / "overwrite-target"
        target.mkdir()
        target_config = target / "repo-fleet.json"
        target_config.write_bytes(self.config_path.read_bytes())
        old_remotes = target / ".repo-fleet/remotes"
        old_remotes.mkdir(parents=True)
        marker = old_remotes / "before-restore.txt"
        marker.write_text("preserve me", encoding="utf-8")

        rc = main([
            "local", "--root", str(target), "--config", str(target_config),
            "restore", str(archive), "--overwrite", "--apply",
        ])
        self.assertEqual(rc, 0)
        self.assertFalse(marker.exists())
        self.assertTrue((old_remotes / "backup-api.git").exists())

        journals = []
        for path in (target / ".repo-fleet/operations").glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("command") == "local restore":
                journals.append(data)
        self.assertEqual(len(journals), 1)
        operation_id = journals[0]["id"]
        rc = main([
            "ops", "--root", str(target), "--config", str(target_config),
            "rollback", operation_id,
        ])
        self.assertEqual(rc, 0)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve me")
        self.assertFalse((old_remotes / "backup-api.git").exists())

    def test_checksum_tampering_is_rejected(self) -> None:
        archive = self.root / ".repo-fleet/backups/original.rfm-backup.tar.gz"
        create_backup(self.config, self.root, output=str(archive), apply=True)
        extract = self.base / "tampered"
        extract.mkdir()
        with tarfile.open(archive, "r:gz") as source:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                source.extractall(extract)
        config_file = extract / "payload/config/repo-fleet.json"
        config_file.write_text(config_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        tampered = self.base / "tampered.rfm-backup.tar.gz"
        with tarfile.open(tampered, "w:gz") as output:
            for name in ("manifest.json", "CHECKSUMS.sha256", "payload"):
                output.add(extract / name, arcname=name)
        with self.assertRaisesRegex(BackupError, "checksum mismatch"):
            verify_backup(tampered)

    def test_unsafe_archive_member_is_rejected(self) -> None:
        archive = self.base / "unsafe.rfm-backup.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            member = tarfile.TarInfo("../outside")
            payload = b"unsafe"
            member.size = len(payload)
            output.addfile(member, io.BytesIO(payload))
        with self.assertRaisesRegex(BackupError, "unsafe archive member"):
            verify_backup(archive)

    def test_retention_prunes_old_archives(self) -> None:
        directory = self.root / ".repo-fleet/backups"
        directory.mkdir(parents=True, exist_ok=True)
        old1 = directory / "old-1.rfm-backup.tar.gz"
        old2 = directory / "old-2.rfm-backup.tar.gz"
        old1.write_bytes(b"old1")
        old2.write_bytes(b"old2")
        now = time.time()
        os.utime(old1, (now - 20, now - 20))
        os.utime(old2, (now - 10, now - 10))
        archive = directory / "new.rfm-backup.tar.gz"
        create_backup(self.config, self.root, output=str(archive), retention=2, apply=True)
        names = sorted(path.name for path in directory.glob("*.rfm-backup.tar.gz"))
        self.assertEqual(names, ["new.rfm-backup.tar.gz", "old-2.rfm-backup.tar.gz"])


if __name__ == "__main__":
    unittest.main()
