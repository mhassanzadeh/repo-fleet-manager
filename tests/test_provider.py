from __future__ import annotations

import unittest

from repo_fleet_manager.config import Provider
from repo_fleet_manager.provider import fork_command, source_identifier
from repo_fleet_manager.gitops import provider_create_command, provider_view_command


class ProviderWorkflowTests(unittest.TestCase):
    def test_source_identifier_supports_https_and_ssh(self) -> None:
        self.assertEqual(source_identifier("https://github.com/frappe/frappe.git"), "frappe/frappe")
        self.assertEqual(source_identifier("git@gitlab.com:group/project.git"), "group/project")

    def test_github_personal_and_org_fork_commands(self) -> None:
        personal = Provider("github", "alice", "git@github.com:{namespace}/{repo}.git", "gh", "github.com")
        self.assertNotIn("--org", fork_command(personal, "frappe/frappe", "frappe", active_user="alice"))
        org = Provider("github", "my-org", "git@github.com:{namespace}/{repo}.git", "gh", "github.com")
        command = fork_command(org, "frappe/frappe", "frappe-custom", active_user="alice")
        self.assertIn("--org", command)
        self.assertIn("my-org", command)

    def test_gitlab_fork_uses_official_project_forks_api(self) -> None:
        provider = Provider("gitlab", "my-group", "git@gitlab.com:{namespace}/{repo}.git", "glab", "gitlab.com")
        command = fork_command(provider, "frappe/erpnext", "erpnext-custom")
        self.assertIn("projects/frappe%2Ferpnext/fork", command)
        self.assertIn("namespace_path=my-group", command)

    def test_named_enterprise_hosts_are_preserved_in_provider_commands(self) -> None:
        github_view = provider_view_command("github", "gh", "bank", "core", "github.example.com")
        self.assertIn("github.example.com/bank/core", github_view)
        gitlab_create = provider_create_command("gitlab", "glab", "bank", "core", "private", "Core", "gitlab.example.com")
        self.assertEqual(gitlab_create[-2:], ["--hostname", "gitlab.example.com"])


if __name__ == "__main__":
    unittest.main()
