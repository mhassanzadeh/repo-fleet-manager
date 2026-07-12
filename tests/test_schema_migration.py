from __future__ import annotations

import copy
import unittest

from repo_fleet_manager.schema import ConfigValidationError, migrate_config_data, validate_or_raise


class SchemaMigrationTests(unittest.TestCase):
    def base_config(self) -> dict:
        return {
            "project": {"name": "demo", "default_provider": "local"},
            "providers": {"local": {"type": "local", "namespace": ".repo-fleet/remotes"}},
            "repositories": [
                {"path": ".", "repo": "demo", "kind": "root"},
                {"path": "services/api", "repo": "demo-api", "depends_on": []},
            ],
        }

    def test_legacy_config_is_migrated_in_memory(self) -> None:
        migrated, changes = migrate_config_data(self.base_config())
        self.assertEqual(migrated["schema_version"], "1.0.0")
        self.assertTrue(changes)
        self.assertEqual(migrated["repositories"][0]["source_type"], "new")
        self.assertIn("operations_dir", migrated["local"])
        validate_or_raise(migrated)

    def test_secrets_are_rejected(self) -> None:
        config, _ = migrate_config_data(self.base_config())
        config["providers"]["github"] = {
            "type": "remote",
            "namespace": "demo",
            "url_template": "git@github.com:{namespace}/{repo}.git",
            "token": "must-not-be-here",
        }
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_or_raise(config)
        self.assertIn("secret-in-config", str(ctx.exception))

    def test_dependency_cycle_is_rejected(self) -> None:
        config, _ = migrate_config_data(self.base_config())
        config["repositories"][0]["depends_on"] = ["demo-api"]
        config["repositories"][1]["depends_on"] = ["demo"]
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_or_raise(config)
        self.assertIn("dependency-cycle", str(ctx.exception))

    def test_nested_repository_paths_are_rejected(self) -> None:
        config, _ = migrate_config_data(self.base_config())
        nested = copy.deepcopy(config["repositories"][1])
        nested["path"] = "services/api/plugins/x"
        nested["repo"] = "demo-plugin"
        config["repositories"].append(nested)
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_or_raise(config)
        self.assertIn("nested-path-collision", str(ctx.exception))


class LegacyShapeMigrationTests(unittest.TestCase):
    def test_short_06_schema_and_legacy_provider_type_are_migrated(self) -> None:
        legacy = {
            "schema_version": "0.6",
            "project_name": "erpnext-frappe-platform",
            "default_provider": "github",
            "providers": {
                "github": {
                    "type": "github",
                    "namespace": "mhassanzadeh",
                    "host": "github.com",
                    "cli": "gh",
                    "url_template": "git@github.com:{namespace}/{repo}.git",
                },
                "local": {
                    "type": "local",
                    "namespace": ".repo-fleet/remotes",
                },
            },
            "repos": [
                {"path": ".", "name": "erpnext-frappe-platform", "kind": "root"},
                {"path": "infra-compose", "name": "erpnext-frappe-infra-compose"},
            ],
        }

        migrated, changes = migrate_config_data(legacy)

        self.assertEqual(migrated["schema_version"], "1.0.0")
        self.assertEqual(migrated["project"]["name"], "erpnext-frappe-platform")
        self.assertEqual(migrated["project"]["default_provider"], "github")
        self.assertEqual(migrated["providers"]["github"]["type"], "remote")
        self.assertEqual(migrated["providers"]["github"]["driver"], "github")
        self.assertEqual(migrated["repositories"][0]["repo"], "erpnext-frappe-platform")
        self.assertNotIn("repos", migrated)
        self.assertTrue(any("repos renamed to repositories" in change for change in changes))
        validate_or_raise(migrated)

    def test_services_map_is_converted_to_repository_list(self) -> None:
        legacy = {
            "schema_version": "0.5",
            "name": "demo-platform",
            "providers": {
                "github": {
                    "type": "github",
                    "owner": "demo-user",
                }
            },
            "services": {
                "demo-platform": {"path": ".", "kind": "root"},
                "demo-api": {"path": "services/api", "lifecycle": "new"},
            },
        }

        migrated, _ = migrate_config_data(legacy)

        self.assertEqual(migrated["project"]["name"], "demo-platform")
        self.assertEqual(migrated["providers"]["github"]["namespace"], "demo-user")
        self.assertEqual(migrated["providers"]["github"]["url_template"], "git@{host}:{namespace}/{repo}.git")
        self.assertEqual(len(migrated["repositories"]), 2)
        self.assertEqual(migrated["repositories"][1]["source_type"], "new")
        validate_or_raise(migrated)


if __name__ == "__main__":
    unittest.main()
