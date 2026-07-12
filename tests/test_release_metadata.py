from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_release_version.py"


class ReleaseMetadataTests(unittest.TestCase):
    def run_checker(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), *args, "--root", str(ROOT)],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_versions_are_consistent(self) -> None:
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("release version 0.8.0", result.stdout)

    def test_expected_version_is_checked(self) -> None:
        result = self.run_checker("v0.8.0")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mismatched_release_version_fails(self) -> None:
        result = self.run_checker("9.9.9")
        self.assertEqual(result.returncode, 2)
        self.assertIn("expected release version", result.stderr)


if __name__ == "__main__":
    unittest.main()
