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


if __name__ == "__main__":
    unittest.main()
