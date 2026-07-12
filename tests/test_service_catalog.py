from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from repo_fleet_manager.cli import main
from repo_fleet_manager.service_catalog import load_service_catalog, summary


class ServiceCatalogTests(unittest.TestCase):
    @property
    def root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def test_catalog_has_domains_capabilities_and_prioritized_gaps(self) -> None:
        catalog = load_service_catalog(self.root)
        data = summary(catalog, self.root)
        self.assertGreaterEqual(data["domain_count"], 10)
        self.assertGreaterEqual(data["capability_count"], 40)
        self.assertGreaterEqual(data["gap_priority_counts"].get("P0", 0), 5)

    def test_declared_component_evidence_exists(self) -> None:
        catalog = load_service_catalog(self.root)
        self.assertEqual(summary(catalog, self.root)["missing_evidence"], [])

    def test_cli_tree_and_gap_views(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            rc = main(["catalog", "--root", str(self.root), "--view", "tree"])
        self.assertEqual(rc, 0)
        self.assertIn("Configuration and inventory", output.getvalue())
        self.assertIn("config.schema-validation", output.getvalue())

        output = StringIO()
        with redirect_stdout(output):
            rc = main(["catalog", "--root", str(self.root), "--view", "gaps", "--priority", "P0"])
        self.assertEqual(rc, 0)
        self.assertIn("GAP-001", output.getvalue())
        self.assertNotIn("GAP-008", output.getvalue())

    def test_markdown_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "catalog.md"
            rc = main([
                "catalog", "--root", str(self.root), "--view", "all",
                "--format", "markdown", "--output", str(target),
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(target.exists())
            self.assertIn("Prioritized logical gaps", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
