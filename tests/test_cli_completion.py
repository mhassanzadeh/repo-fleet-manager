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


if __name__ == "__main__":
    unittest.main()
