from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from repo_fleet_manager.config import load_config
from repo_fleet_manager.fingerprint import digest_path


class ConfigTests(unittest.TestCase):
    def test_load_sample_config(self) -> None:
        cfg = load_config(Path(__file__).resolve().parents[1] / "configs" / "repo-fleet.example.json")
        self.assertEqual(cfg.project["name"], "my-platform")
        self.assertEqual(len(cfg.submodules()), 3)
        self.assertEqual(cfg.provider_for(cfg.repositories[1]).expected_url("my-api-service"), "git@github.com:my-github-org/my-api-service.git")

    def test_digest_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
            first = digest_path(root)
            second = digest_path(root)
            self.assertEqual(first, second)
            self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
