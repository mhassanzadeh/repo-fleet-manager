from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from repo_fleet_manager.config import load_config
from repo_fleet_manager.graph import execute_levels, render_graph, topological_levels


class DependencyGraphTests(unittest.TestCase):
    def make_config(self, root: Path):
        payload = {
            "schema_version": "1.0.0",
            "project": {"name": "graph", "default_provider": "local"},
            "providers": {"local": {"type": "local", "namespace": ".repo-fleet/remotes"}},
            "repositories": [
                {"path": ".", "repo": "root", "kind": "root", "source_type": "new", "remote_mode": "create", "depends_on": []},
                {"path": "packages/contracts", "repo": "contracts", "source_type": "new", "remote_mode": "create", "depends_on": []},
                {"path": "services/api", "repo": "api", "source_type": "new", "remote_mode": "create", "depends_on": ["contracts"]},
                {"path": "clients/web", "repo": "web", "source_type": "new", "remote_mode": "create", "depends_on": ["api", "contracts"]},
            ],
            "local": {"default_jobs": 4},
        }
        path = root / "repo-fleet.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return load_config(path)

    def test_topological_levels_and_dot_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = self.make_config(Path(td))
            levels = [[repo.repo for repo in level] for level in topological_levels(cfg)]
            self.assertEqual(levels[0], ["root", "contracts"])
            self.assertEqual(levels[1], ["api"])
            self.assertEqual(levels[2], ["web"])
            self.assertIn('"contracts" -> "api"', render_graph(cfg, "dot"))

    def test_controlled_parallel_execution_preserves_level_order(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cfg = self.make_config(Path(td))
            results = execute_levels(cfg, lambda repo: repo.repo.upper(), jobs=4)
            self.assertEqual([repo.repo for repo, _ in results], ["root", "contracts", "api", "web"])


if __name__ == "__main__":
    unittest.main()
