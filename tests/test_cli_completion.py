import unittest
from io import StringIO
from contextlib import redirect_stdout

from repo_fleet_manager.cli import main


class CompletionCommandTest(unittest.TestCase):
    def run_completion(self, shell: str) -> str:
        buffer = StringIO()
        with redirect_stdout(buffer):
            rc = main(["completion", shell])
        self.assertEqual(rc, 0)
        return buffer.getvalue()

    def test_bash_completion_contains_nested_commands(self):
        output = self.run_completion("bash")
        self.assertIn("complete -F _rfm rfm", output)
        self.assertIn("repos", output)
        self.assertIn("submodules", output)
        self.assertIn("github gitlab", output)
        self.assertIn("verify-backup", output)
        self.assertIn("render", output)
        self.assertIn("--profile", output)
        self.assertIn("--group", output)
        self.assertIn("init-project", output)
        self.assertIn("python-service", output)
        self.assertIn("bootstrap", output)
        self.assertIn("cache", output)
        self.assertIn("allow-incomplete", output)
        self.assertIn("wizard", output)
        self.assertIn("--non-interactive", output)
        self.assertIn("runtime", output)
        self.assertIn("--timeout", output)
        self.assertIn("--service", output)
        self.assertIn("logs", output)
        self.assertIn("jsonl", output)
        self.assertIn("--audit-log", output)
        self.assertIn("--run-id", output)
        self.assertIn("supply-chain", output)
        self.assertIn("--require-attestation", output)

    def test_fish_completion_contains_nested_commands(self):
        output = self.run_completion("fish")
        self.assertIn("complete -c rfm", output)
        self.assertIn("validate-links", output)
        self.assertIn("github gitlab", output)
        self.assertIn("restore", output)
        self.assertIn("render", output)
        self.assertIn("profile", output)
        self.assertIn("group", output)
        self.assertIn("init-project", output)
        self.assertIn("scaffold", output)
        self.assertIn("lock", output)
        self.assertIn("cache", output)
        self.assertIn("require-complete", output)
        self.assertIn("wizard", output)
        self.assertIn("session-file", output)
        self.assertIn("runtime", output)
        self.assertIn("interval", output)
        self.assertIn("logs", output)
        self.assertIn("jsonl", output)
        self.assertIn("audit-log", output)
        self.assertIn("run-id", output)
        self.assertIn("supply-chain", output)
        self.assertIn("require-attestation", output)


if __name__ == "__main__":
    unittest.main()
