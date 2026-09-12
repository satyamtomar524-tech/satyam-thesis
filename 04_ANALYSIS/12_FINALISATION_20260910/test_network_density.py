"""Synthetic density boundary regressions; no thesis observations are loaded."""
from pathlib import Path
import json
import types
import unittest


class NetworkDensityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        path = root / "04_ANALYSIS/11_CORRECTION_REVIEW_V2/revision_calculations.py"
        cls.engine = types.ModuleType("density_regression_calculations")
        cls.engine.__file__ = str(path)
        # Load pure helpers without running their historical orchestration or
        # writing import caches beside preserved source files.
        exec(compile(path.read_bytes(), str(path), "exec"), cls.engine.__dict__)
        cls.c3, cls.c5, _ = cls.engine._helpers(root)

    @staticmethod
    def row(link, supplier, category):
        return {"Link_ID": link, "_canonical": link, "Supplier_ID": supplier,
                "_tax": category, "_family": "Synthetic family",
                "_category": category}

    def network(self, rows, method):
        return self.engine._network(self.c3, self.c5, "TEST", "synthetic", rows,
                                    method=method)

    def test_empty_network_density_is_undefined(self):
        for method in ("weighted_jaccard", "cosine"):
            with self.subTest(method=method):
                result = self.network([], method)
                self.assertEqual(result["supplier_n"], 0)
                self.assertEqual(result["possible_pair_n"], 0)
                self.assertIsNone(result["density"])
                self.assertEqual(json.dumps(result["density"], allow_nan=False), "null")

    def test_single_supplier_density_is_undefined_despite_multiple_claims(self):
        rows = [self.row("L1", "S1", "T1"), self.row("L2", "S1", "T2")]
        for method in ("weighted_jaccard", "cosine"):
            with self.subTest(method=method):
                result = self.network(rows, method)
                self.assertEqual(result["supplier_n"], 1)
                self.assertEqual(result["link_n"], 2)
                self.assertEqual(result["possible_pair_n"], 0)
                self.assertIsNone(result["density"])

    def test_nonoverlapping_suppliers_have_defined_zero_density(self):
        rows = [self.row("L1", "S1", "T1"), self.row("L2", "S2", "T2")]
        for method in ("weighted_jaccard", "cosine"):
            with self.subTest(method=method):
                result = self.network(rows, method)
                self.assertEqual(result["possible_pair_n"], 1)
                self.assertEqual(result["positive_edge_n"], 0)
                self.assertEqual(result["density"], 0.0)

    def test_density_counts_supplier_pairs_not_claim_weights(self):
        rows = [self.row("L1", "S1", "T1"), self.row("L2", "S2", "T1"),
                self.row("L3", "S3", "T2"), self.row("L4", "S1", "T1")]
        for method in ("weighted_jaccard", "cosine"):
            with self.subTest(method=method):
                result = self.network(rows, method)
                self.assertEqual(result["supplier_n"], 3)
                self.assertEqual(result["weight_sum"], 4)
                self.assertEqual(result["positive_edge_n"], 1)
                self.assertEqual(result["possible_pair_n"], 3)
                self.assertEqual(result["density"], 1 / 3)


if __name__ == "__main__":
    unittest.main()
