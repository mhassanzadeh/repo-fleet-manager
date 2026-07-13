from __future__ import annotations

import json
import os
import subprocess
import tarfile
import tempfile
import unittest
import warnings
from pathlib import Path

from repo_fleet_manager.cache import (
    OfflineCacheError,
    bootstrap_from_cache,
    export_cache,
    import_cache,
    verify_cache,
)
from repo_fleet_manager.config import load_config


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


class OfflineCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "workspace"
        self.root.mkdir()
        git("init", "-b", "main", str(self.root))
        git("config", "user.name", "Cache Test", cwd=self.root)
        git("config", "user.email", "cache@example.invalid", cwd=self.root)

        self.service = self.root / "services/api"
        self.service.mkdir(parents=True)
        git("init", "-b", "main", str(self.service))
        git("config", "user.name", "Cache Test", cwd=self.service)
        git("config", "user.email", "cache@example.invalid", cwd=self.service)
        (self.service / "README.md").write_text("# cache-api\n", encoding="utf-8")
        git("add", ".", cwd=self.service)
        git("commit", "-m", "service initial", cwd=self.service)

        self.config_path = self.root / "repo-fleet.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "project": {
                        "name": "cache-demo",
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
                            "repo": "cache-demo",
                            "kind": "root",
                            "provider": "local",
                            "branch": "main",
                            "source_type": "existing",
                            "depends_on": [],
                        },
                        {
                            "path": "services/api",
                            "repo": "cache-api",
                            "kind": "service",
                            "provider": "local",
                            "branch": "main",
                            "source_type": "existing",
                            "existing_path": "services/api",
                            "depends_on": [],
                        },
                    ],
                    "local": {
                        "remotes_dir": ".repo-fleet/remotes",
                        "operations_dir": ".repo-fleet/operations",
                        "lock_file": ".repo-fleet/lock",
                        "cache_dir": ".repo-fleet/cache",
                        "cache_retention": 3,
                        "default_jobs": 1,
                    },
                    "compose": {"engine": "podman", "cache_images": []},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.root / "README.md").write_text("# cache-demo\n", encoding="utf-8")
        git("add", "README.md", "repo-fleet.json", cwd=self.root)
        git("commit", "-m", "root initial", cwd=self.root)
        self.config = load_config(self.config_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _archive(self, name: str = "demo") -> Path:
        return self.root / f".repo-fleet/cache/{name}.rfm-cache.tar.gz"

    def _fake_engine(self) -> tuple[Path, Path, str]:
        bindir = self.base / "bin"
        bindir.mkdir(exist_ok=True)
        log = self.base / "engine.log"
        engine = bindir / "podman"
        engine.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            "if [ \"$1 $2\" = \"image inspect\" ]; then echo sha256:fake-image; exit 0; fi\n"
            "if [ \"$1 $2\" = \"image save\" ]; then\n"
            "  shift 2; [ \"$1\" = \"-o\" ]; out=$2; shift 2; image=$1; printf 'image:%s\\n' \"$image\" > \"$out\"; exit 0\n"
            "fi\n"
            "if [ \"$1 $2\" = \"image load\" ]; then\n"
            "  shift 2; [ \"$1\" = \"-i\" ]; printf 'load:%s\\n' \"$2\" >> \"$FAKE_ENGINE_LOG\"; exit 0\n"
            "fi\n"
            "echo unsupported >&2; exit 2\n",
            encoding="utf-8",
        )
        engine.chmod(0o755)
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{bindir}:{old_path}"
        os.environ["FAKE_ENGINE_LOG"] = str(log)
        return engine, log, old_path

    def test_export_verify_and_import_git_bundles(self) -> None:
        archive = self._archive()
        self.assertEqual(export_cache(self.config, self.root, output=str(archive), include_images=False, apply=True), 0)
        self.assertTrue(archive.is_file())
        self.assertEqual(verify_cache(archive, require_complete=True), 0)

        target = self.base / "imported"
        self.assertEqual(import_cache(archive, target, load_images=False, apply=True), 0)
        self.assertTrue((target / "repo-fleet.json").is_file())
        for name in ("cache-demo", "cache-api"):
            remote = target / f".repo-fleet/remotes/{name}.git"
            self.assertTrue(remote.is_dir())
            self.assertTrue(git(f"--git-dir={remote}", "rev-parse", "refs/heads/main"))

    def test_air_gapped_bootstrap_materializes_root_and_submodule(self) -> None:
        archive = self._archive("bootstrap")
        export_cache(self.config, self.root, output=str(archive), include_images=False, apply=True)
        target = self.base / "airgap"
        rc = bootstrap_from_cache(archive, target, load_images=False, apply=True)
        self.assertEqual(rc, 0)
        self.assertEqual(git("branch", "--show-current", cwd=target), "main")
        self.assertTrue((target / "services/api/.git").exists())
        self.assertIn("cache-api", (target / "services/api/README.md").read_text(encoding="utf-8"))
        origin = git("remote", "get-url", "origin", cwd=target)
        self.assertTrue(origin.startswith("file://"), origin)

    def test_image_archives_are_saved_and_loaded(self) -> None:
        _engine, log, old_path = self._fake_engine()
        try:
            archive = self._archive("images")
            rc = export_cache(
                self.config,
                self.root,
                output=str(archive),
                images=["example/api:1.0"],
                engine="podman",
                apply=True,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(verify_cache(archive, require_complete=True), 0)
            target = self.base / "images-import"
            rc = import_cache(archive, target, engine="podman", load_images=True, apply=True)
            self.assertEqual(rc, 0)
            self.assertIn("load:", log.read_text(encoding="utf-8"))
        finally:
            os.environ["PATH"] = old_path
            os.environ.pop("FAKE_ENGINE_LOG", None)

    def test_tampering_is_rejected(self) -> None:
        archive = self._archive("original")
        export_cache(self.config, self.root, output=str(archive), include_images=False, apply=True)
        extract = self.base / "tampered"
        extract.mkdir()
        with tarfile.open(archive, "r:gz") as source:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                source.extractall(extract)
        bundle = next((extract / "payload/git").glob("*.bundle"))
        bundle.write_bytes(bundle.read_bytes() + b"tampered")
        tampered = self.base / "tampered.rfm-cache.tar.gz"
        with tarfile.open(tampered, "w:gz") as output:
            for name in ("manifest.json", "CHECKSUMS.sha256", "payload"):
                output.add(extract / name, arcname=name)
        with self.assertRaisesRegex(OfflineCacheError, "checksum mismatch"):
            verify_cache(tampered)

    def test_missing_repository_requires_explicit_allow_missing(self) -> None:
        missing = self.root / "services/api"
        subprocess.run(["rm", "-rf", str(missing)], check=True)
        archive = self._archive("incomplete")
        with self.assertRaisesRegex(OfflineCacheError, "no local Git source"):
            export_cache(self.config, self.root, output=str(archive), include_images=False, apply=True)
        self.assertEqual(
            export_cache(
                self.config,
                self.root,
                output=str(archive),
                include_images=False,
                allow_missing=True,
                apply=True,
            ),
            0,
        )
        self.assertEqual(verify_cache(archive, require_complete=True), 2)
        with self.assertRaisesRegex(OfflineCacheError, "incomplete"):
            import_cache(archive, self.base / "incomplete-target", load_images=False, apply=True)


if __name__ == "__main__":
    unittest.main()
