"""Synthetic tests for a restricted, immutable-source amendment operation."""
import unittest
from apply_scope_amendments import apply_amendments


class ScopeAmendments(unittest.TestCase):
    def setUp(self):
        self.rows = [{"Link_ID": "L1", "Analytical_Technology_EN": "Old scope", "Primary_Eligible": 1,
                      "Needs_Student_Review": True, "Capability_Evidence_IDs": ["E1"]}]
        self.amendment = {"Link_ID": "L1", "expected_technology": "Old scope", "technology": "Narrow scope",
                          "source_url": "https://example.invalid/source", "source_locator": "section",
                          "reason": "Synthetic test", "paired_record": "L2", "review_status": "checked"}

    def test_only_wording_changes_and_no_student_approval(self):
        result = apply_amendments(self.rows, [self.amendment], "2026-09-10")
        self.assertEqual(self.rows[0]["Analytical_Technology_EN"], "Old scope")
        self.assertEqual(result[0]["Analytical_Technology_EN"], "Narrow scope")
        self.assertEqual(result[0]["Primary_Eligible"], 1)
        self.assertTrue(result[0]["Needs_Student_Review"])
        self.assertFalse(result[0]["Finalisation_Scope_Review"]["student_review_confirmed"])

    def test_stale_wording_rejected(self):
        self.amendment["expected_technology"] = "Wrong input"
        with self.assertRaises(ValueError):
            apply_amendments(self.rows, [self.amendment], "2026-09-10")

    def test_duplicate_amendment_rejected(self):
        with self.assertRaises(ValueError):
            apply_amendments(self.rows, [self.amendment, self.amendment], "2026-09-10")


if __name__ == "__main__":
    unittest.main()
