import copy
import unittest

from distinctness_holds import apply_distinctness_holds
from evidence_holds import record_digest


class DistinctnessHoldTests(unittest.TestCase):
    def setUp(self):
        base = {"Supplier_ID": "SYNTHETIC-S", "Analytical_Taxonomy_ID": "TAX-12", "Primary_Eligible": 1,
                "Capability_Status": "supported", "Capability_Supported_Revised": 1,
                "BMW_Relationship_Status": "supported", "BMW_Relationship_Supported_Revised": 1,
                "Exact_BMW_Technology_Revised": 0, "Capability_Evidence_IDs": ["SYNTHETIC-E"],
                "BMW_Evidence_IDs": ["SYNTHETIC-B"], "Issue_Tags": []}
        self.rows = [{**base, "Link_ID": i, "Canonical_Link_ID": i} for i in ["SYNTHETIC-BROAD", "SYNTHETIC-NARROW"]]
        self.decision = {"Link_ID": self.rows[0]["Link_ID"], "retained_narrower_Link_ID": self.rows[1]["Link_ID"],
                         "expected_record_sha256": record_digest(self.rows[0]), "reason": "Synthetic umbrella contains narrower claim.",
                         "source_urls": ["https://example.org/synthetic"], "source_locator": "Synthetic passage"}

    def test_preserves_support_and_narrower_claim(self):
        before = copy.deepcopy(self.rows)
        result = apply_distinctness_holds(self.rows, [self.decision], "2026-09-10")
        self.assertEqual(self.rows, before)
        self.assertEqual(result[1], before[1])
        self.assertEqual(result[0]["Primary_Eligible"], 0)
        self.assertEqual(result[0]["Capability_Supported_Revised"], 1)
        self.assertEqual(result[0]["BMW_Relationship_Supported_Revised"], 1)
        self.assertTrue(result[0]["Finalisation_Distinctness_Hold"]["not_a_duplicate_merger"])

    def test_rejects_stale_record(self):
        self.rows[0]["Primary_Eligible"] = 0
        with self.assertRaisesRegex(ValueError, "Stale"):
            apply_distinctness_holds(self.rows, [self.decision], "2026-09-10")

    def test_rejects_different_supplier(self):
        self.rows[1]["Supplier_ID"] = "DIFFERENT"
        with self.assertRaisesRegex(ValueError, "same-supplier"):
            apply_distinctness_holds(self.rows, [self.decision], "2026-09-10")

    def test_rejects_duplicate_decision(self):
        with self.assertRaisesRegex(ValueError, "Duplicate distinctness"):
            apply_distinctness_holds(self.rows, [self.decision, self.decision], "2026-09-10")


if __name__ == "__main__":
    unittest.main()
